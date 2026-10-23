"""第十八课：同一请求重复调用只创建一份本地草稿；幂等不替代人工授权。"""

import argparse
import asyncio
import json
import re
import sqlite3
import sys
from contextlib import aclosing, closing
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import openai
from dotenv import dotenv_values

from agentscope.agent import Agent, ModelConfig, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.event import RequireExternalExecutionEvent, RequireUserConfirmEvent, ToolResultEndEvent
from agentscope.message import Msg, ToolResultState, UserMsg
from agentscope.middleware import MiddlewareBase
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionBehavior, PermissionContext, PermissionDecision
from agentscope.tool import FunctionTool, Toolkit
from agentscope.types import ReplyFinishedReason


DB_PATH = Path(__file__).resolve().parent / "sessions" / "lesson18" / "drafts.sqlite3"
DEFAULT_ORDER = "DEMO-1001"
DEFAULT_REASON = "重复购买"
SYSTEM_PROMPT = (
    "你是中文教学助手，只能通过 create_refund_draft 创建虚构订单的本地申请草稿。"
    "原样使用用户提供的订单号和理由，不改写理由；缺少信息时先询问。"
    "宿主程序管理请求标识并逐次询问人工批准，你不能生成请求标识或绕过批准。"
    "工具返回 replayed=true 表示复用原草稿，不是又创建了一份。"
    "拒绝、参数冲突或工具失败后停止，不换参数反复申请。成功后直接说明结果，不重复调用。"
    "只有工具成功返回才能声称草稿存在；没有真正提交申请、退款、发信或连接业务系统。"
)


class LessonError(Exception):
    """本课的参数、权限或完整性检查失败。"""


class IdempotencyConflict(LessonError):
    """同一请求标识已经用于另一组参数。"""


def validate_request(request_id: str, order_id: str, reason: str) -> None:
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", request_id):
        raise ValueError("请求标识须为 1 到 64 位字母、数字、下划线或连字符，并以字母或数字开头。")
    if not isinstance(order_id, str) or not re.fullmatch(r"DEMO-[0-9]{1,12}", order_id):
        raise ValueError("订单号须为 DEMO- 加 1 到 12 位数字。")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        raise ValueError("理由必须是非空文字，且不超过 200 个字符。")


def save_draft(connection: sqlite3.Connection, request_id: str, order_id: str, reason: str) -> dict:
    """草稿就是这一行数据；创建与去重在同一个 SQLite 事务中完成。"""
    validate_request(request_id, order_id, reason)
    if connection.in_transaction:
        raise LessonError("保存函数需要独立事务，不能接管调用方已有事务。")

    # 先获得写事务，再查询；并发调用不能同时看见“尚不存在”后各自创建。
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS drafts ("
            "request_id TEXT PRIMARY KEY NOT NULL, "
            "draft_id TEXT UNIQUE NOT NULL, "
            "order_id TEXT NOT NULL, reason TEXT NOT NULL)"
        )
        row = connection.execute(
            "SELECT draft_id, order_id, reason FROM drafts WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is not None:
            draft_id, original_order, original_reason = row
            if (original_order, original_reason) != (order_id, reason):
                raise IdempotencyConflict("同一请求标识已用于不同订单或理由，未修改原草稿。")
            replayed = True
        else:
            draft_id = f"draft-{uuid4().hex}"
            connection.execute(
                "INSERT INTO drafts (request_id, draft_id, order_id, reason) VALUES (?, ?, ?, ?)",
                (request_id, draft_id, order_id, reason),
            )
            replayed = False
        connection.commit()
    except BaseException:
        connection.rollback()
        raise

    # 只有提交成功后才向调用方报告成功；replayed 是本次调用的附加标记。
    return {
        "request_id": request_id,
        "draft_id": draft_id,
        "order_id": order_id,
        "reason": reason,
        "status": "draft_only",
        "replayed": replayed,
    }


def save_local_draft(request_id: str, order_id: str, reason: str) -> dict:
    validate_request(request_id, order_id, reason)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 固定路径，每次调用独立连接；同步短事务里不询问用户、不调用模型。
    with closing(sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)) as connection:
        return save_draft(connection, request_id, order_id, reason)


class ConfirmingDraftTool(FunctionTool):
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.receipts: list[dict] = []

        def create_refund_draft(order_id: str, reason: str) -> str:
            """为虚构订单创建或复用本地申请草稿，不提交申请或执行退款。

            Args:
                order_id (str): DEMO- 加 1 到 12 位数字的演示订单号。
                reason (str): 用户提供的原始理由，非空且不超过 200 个字符，不要改写。
            """
            try:
                receipt = save_local_draft(self.request_id, order_id, reason)
            except IdempotencyConflict:
                print("[冲突] 同一请求标识的参数不同，未覆盖原草稿。", flush=True)
                raise
            self.receipts.append(receipt)
            action = "复用原草稿" if receipt["replayed"] else "创建新草稿"
            print(f"[工具结果] {action}：{receipt['draft_id']}", flush=True)
            return json.dumps(receipt, ensure_ascii=False)

        super().__init__(create_refund_draft, is_read_only=False, is_concurrency_safe=False)

    async def check_permissions(
        self, tool_input: dict[str, Any], context: PermissionContext,
    ) -> PermissionDecision:
        try:
            validate_request(self.request_id, **tool_input)
        except (TypeError, ValueError):
            return PermissionDecision(behavior=PermissionBehavior.DENY, message="参数不合格，未打开数据库。")
        print(f"\n[待确认] create_refund_draft；宿主请求标识：{self.request_id}")
        print(json.dumps(tool_input, ensure_ascii=False, indent=2))
        print(f"影响：仅在 {DB_PATH} 创建或复用一条虚构草稿；不提交申请、不执行退款。")
        try:
            answer = await asyncio.to_thread(input, "仅批准本次调用？输入 yes 批准，其余拒绝：")
        except EOFError:
            answer = ""
        if answer.strip() == "yes":
            return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="用户批准本次本地草稿操作。")
        print("[权限] 已拒绝本次调用，未打开数据库。")
        return PermissionDecision(behavior=PermissionBehavior.DENY, message="用户拒绝本次操作，不得换参数重试。")


class StopAfterFailure(MiddlewareBase):
    """先让当前工具事件流收尾，再阻止后续模型或同批工具继续执行。"""

    def __init__(self) -> None:
        self.failed = False

    async def on_model_call(self, agent, input_kwargs, next_handler):
        if self.failed:
            raise LessonError("工具被拒绝、发生冲突或执行失败，未继续请求模型。")
        return await next_handler()

    async def on_check_permission(self, agent, input_kwargs, next_handler):
        if self.failed:
            return PermissionDecision(behavior=PermissionBehavior.DENY, message="此前工具已失败，本轮不再执行新操作。")
        return await next_handler()


async def run_agent(agent: Agent, order_id: str, reason: str, guard: StopAfterFailure) -> str:
    task = "请按以下原始参数创建一份本地虚构申请草稿，不执行真实退款：\n" + json.dumps(
        {"order_id": order_id, "reason": reason}, ensure_ascii=False,
    )
    final_reply = None
    async with aclosing(agent.reply_stream(UserMsg(name="user", content=task), yield_final_msg=True)) as items:
        async for item in items:
            if isinstance(item, Msg):
                final_reply = item
            elif isinstance(item, ToolResultEndEvent) and item.state != ToolResultState.SUCCESS:
                current = asyncio.current_task()
                if item.state == ToolResultState.INTERRUPTED and current is not None and current.cancelling():
                    continue
                guard.failed = True
            elif isinstance(item, (RequireUserConfirmEvent, RequireExternalExecutionEvent)):
                raise LessonError("收到本例未处理的外部交互事件，停止流程。")
    if guard.failed:
        raise LessonError("本轮工具结果不成功，未采纳模型总结。")
    if final_reply is None or final_reply.finished_reason != ReplyFinishedReason.COMPLETED:
        raise LessonError("模型回复未正常完成；已提交的草稿不会自动撤销。")
    text = final_reply.get_text_content()
    if not isinstance(text, str) or not text.strip():
        raise LessonError("模型未返回有效文字；已提交的草稿不会自动撤销。")
    return text


def offline_check() -> None:
    """仅在内存数据库中检查幂等规则，不建目录、不使用模型或凭据。"""
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise LessonError(f"离线自检失败：{message}")

    with closing(sqlite3.connect(":memory:", isolation_level=None)) as connection:
        first = save_draft(connection, "demo-request-001", DEFAULT_ORDER, DEFAULT_REASON)
        repeated = save_draft(connection, "demo-request-001", DEFAULT_ORDER, DEFAULT_REASON)
        require(not first["replayed"] and repeated["replayed"], "首次与重复标记")
        require(first["draft_id"] == repeated["draft_id"], "重复请求改变了草稿标识")
        for order, reason in (("DEMO-1002", DEFAULT_REASON), (DEFAULT_ORDER, "误购")):
            try:
                save_draft(connection, "demo-request-001", order, reason)
            except IdempotencyConflict:
                pass
            else:
                raise LessonError("离线自检失败：冲突没有被拒绝。")
        require(connection.execute("SELECT COUNT(*) FROM drafts").fetchone()[0] == 1, "重复/冲突增加了记录")
        require(save_draft(connection, "demo-request-001", DEFAULT_ORDER, DEFAULT_REASON) == repeated, "冲突修改了原记录")
        second = save_draft(connection, "demo-request-002", DEFAULT_ORDER, DEFAULT_REASON)
        require(second["draft_id"] != first["draft_id"], "不同请求标识应是独立操作")
        try:
            save_draft(connection, "bad/path", DEFAULT_ORDER, DEFAULT_REASON)
        except ValueError:
            pass
        else:
            raise LessonError("离线自检失败：非法请求标识未被拒绝。")
        require(connection.execute("SELECT COUNT(*) FROM drafts").fetchone()[0] == 2, "非法请求修改了数据")
        require(not connection.in_transaction, "事务未收尾")

    print("离线自检通过：首次创建、同参复用、异参冲突、独立请求和参数检查。")
    print("仅使用 :memory: 数据库；未建目录或持久文件、未读配置、未建 Agent/模型、未发请求。")
    print("真实示例需 --live --request-id demo-request-001，并在工具执行前逐次输入 yes。")


async def main(request_id: str | None = None, order_id: str = DEFAULT_ORDER, reason: str = DEFAULT_REASON, live: bool = False) -> None:
    if not live:
        offline_check()
        return
    if request_id is None:
        raise LessonError("真实运行必须由宿主提供 --request-id；不要为同一操作的每次重试换新标识。")
    validate_request(request_id, order_id, reason)
    config = dotenv_values(Path(__file__).with_name(".env"), encoding="utf-8-sig", interpolate=False)
    api_key = (config.get("OPENAI_API_KEY") or "").strip()
    base_url = (config.get("OPENAI_BASE_URL") or "").strip().rstrip("/")
    model_name = (config.get("OPENAI_MODEL") or "").strip()
    if not api_key or api_key == "replace-with-your-real-api-key":
        raise LessonError("请先在 .env 中填写真实的 OPENAI_API_KEY。")
    if not base_url or not model_name:
        raise LessonError("请在 .env 中填写 OPENAI_BASE_URL 和 OPENAI_MODEL。")

    model = OpenAIChatModel(
        credential=OpenAICredential(api_key=api_key, base_url=base_url),
        model=model_name, stream=False, max_retries=0,
        client_kwargs={"timeout": 60.0, "max_retries": 0},
    )
    try:
        tool = ConfirmingDraftTool(request_id)
        guard = StopAfterFailure()
        agent = Agent(
            name="DraftAgent", system_prompt=SYSTEM_PROMPT, model=model,
            toolkit=Toolkit(tools=[tool]),
            middlewares=[guard],
            model_config=ModelConfig(max_retries=0, fallback_model=None),
            react_config=ReActConfig(max_iters=4, interruption_raise_cancelled_error=True),
        )
        if urlsplit(base_url).scheme == "http":
            print("注意：HTTP 会明文传输 API Key、任务与草稿回执。")
        print("真实模型请求可能收费；本例只有本地 SQLite 草稿，不执行真实退款。")
        print("同请求同参复用；同请求异参报冲突。每次工具调用都要人工批准。")
        answer = await run_agent(agent, order_id, reason, guard)
        print(f"\n--- Agent 回答 ---\n{answer}")
        if tool.receipts:
            print(f"工具成功返回 {len(tool.receipts)} 次；不同草稿数 {len({item['draft_id'] for item in tool.receipts})}。")
        else:
            print("本轮没有成功工具回执，不能据此声称已创建或复用了草稿。")
    finally:
        print("提示：模型回复失败、取消或重试不会撤销已提交的本地草稿；可用同请求标识和同参数取回。")
        await model.client.close()


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="仅在内存中检查幂等性（默认）")
    mode.add_argument("--live", action="store_true", help="请求模型并逐次审批本地草稿操作，可能产生费用")
    parser.add_argument("--request-id", help="宿主分配的业务请求标识，同一操作的重试必须保持不变")
    parser.add_argument("--order-id", default=DEFAULT_ORDER)
    parser.add_argument("--reason", default=DEFAULT_REASON)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.request_id, args.order_id, args.reason, live=args.live))
    except openai.APIStatusError as error:
        raise SystemExit(f"模型服务 HTTP {error.status_code}；停止，已提交草稿不自动撤销。") from None
    except openai.APITimeoutError:
        raise SystemExit("模型请求超时，未自动重跑 Agent；已提交草稿不自动撤销。") from None
    except openai.APIConnectionError:
        raise SystemExit("模型连接失败，未自动重跑 Agent；已提交草稿不自动撤销。") from None
    except (LessonError, ValueError) as error:
        raise SystemExit(str(error)) from None
    except sqlite3.Error:
        raise SystemExit("本地数据库操作失败或被锁定，未报告创建成功。") from None
    except OSError:
        raise SystemExit("本地文件操作失败，请检查草稿目录和权限。") from None
    except KeyboardInterrupt:
        raise SystemExit("已取消；已提交草稿不自动撤销，远端请求仍可能计费。") from None
    except Exception as error:
        raise SystemExit(f"运行异常（{type(error).__name__}）；已提交草稿不自动撤销，不公开完整请求或异常。") from None
