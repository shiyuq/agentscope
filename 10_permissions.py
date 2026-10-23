"""第十课：工具执行前人工确认，批准后才创建本地退款申请草稿。"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import openai
from dotenv import dotenv_values

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.event import ReplyFinishedReason
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionBehavior, PermissionContext, PermissionDecision
from agentscope.tool import FunctionTool, Toolkit


DEFAULT_TASK = "请为虚构订单 DEMO-1001 创建一份本地退款申请草稿，理由是：重复购买。不要执行真正的退款。"
DRAFT_DIR = Path(__file__).resolve().parent / "sessions" / "lesson10"


def validate_draft_args(order_id: str, reason: str) -> None:
    """在任何文件操作前检查参数；订单号和理由均不参与路径拼接。"""
    if not isinstance(order_id, str) or not re.fullmatch(r"DEMO-[0-9]{1,12}", order_id):
        raise ValueError("订单号必须是 DEMO- 加 1 到 12 位数字，例如 DEMO-1001。")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
        raise ValueError("退款理由必须是非空文字，且不超过 200 个字符。")


def create_refund_draft(order_id: str, reason: str) -> str:
    """为虚构订单创建本地退款申请草稿；不提交申请，也不发生退款。

    Args:
        order_id (str): 演示订单号，必须为 DEMO- 加 1 到 12 位数字，例如 DEMO-1001。
        reason (str): 退款申请理由，非空且不超过 200 个字符。
    """
    validate_draft_args(order_id, reason)
    draft = {"order_id": order_id, "reason": reason, "status": "draft_only"}
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    path = DRAFT_DIR / f"refund-{uuid4().hex}.json"
    # x 模式只创建新文件；即使文件名碰撞，也不覆盖已有内容。
    with path.open("x", encoding="utf-8") as output:
        json.dump(draft, output, ensure_ascii=False, indent=2)
    print(f"[工具执行] create_refund_draft -> 已创建 {path.name}")
    return json.dumps(
        {"status": "draft_only", "path": str(path), "note": "仅创建本地申请草稿，未提交申请，未执行退款。"},
        ensure_ascii=False,
    )


class ConfirmingFunctionTool(FunctionTool):
    """在 Agent 的原生权限检查阶段，逐次确认草稿工具的调用。"""

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        print(f"\n[待确认] 模型提议调用 {self.name}")
        print(json.dumps(tool_input, ensure_ascii=False, indent=2))
        try:
            validate_draft_args(**tool_input)
        except (TypeError, ValueError) as error:
            return PermissionDecision(
                behavior=PermissionBehavior.DENY,
                message=f"参数不合格，未创建草稿：{error}",
            )
        print(f"影响：仅在 {DRAFT_DIR} 创建一个新 JSON 草稿，不提交申请、不执行退款。")
        try:
            answer = await asyncio.to_thread(input, "仅批准本次调用？输入 yes 批准，其余拒绝：")
        except EOFError:
            answer = ""

        # 只决定这一次，不添加规则，也不把 yes 当作今后始终允许。
        if answer.strip() == "yes":
            print("[权限] 已批准本次调用。")
            return PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="用户批准本次调用，仅允许创建本地申请草稿。",
            )
        print("[权限] 已拒绝本次调用，未创建草稿。")
        return PermissionDecision(
            behavior=PermissionBehavior.DENY,
            message="用户拒绝本次调用，未创建草稿；本轮不要重试或更换参数绕过拒绝。",
        )


async def main(task: str, check_only: bool = False) -> None:
    draft_tool = ConfirmingFunctionTool(
        create_refund_draft,
        is_read_only=False,
        is_concurrency_safe=False,
    )
    toolkit = Toolkit(tools=[draft_tool])
    if check_only:
        print("离线自检通过：草稿工具创建成功，执行前需要逐次人工确认。")
        print(json.dumps(await toolkit.get_tool_schemas(), ensure_ascii=False, indent=2))
        print("未读取密钥、未调用模型、未询问批准，也未创建目录或草稿。")
        return

    config = dotenv_values(
        Path(__file__).with_name(".env"),
        encoding="utf-8-sig",
        interpolate=False,
    )
    api_key = (config.get("OPENAI_API_KEY") or "").strip()
    base_url = (config.get("OPENAI_BASE_URL") or "").strip().rstrip("/")
    model_name = (config.get("OPENAI_MODEL") or "").strip()
    if not api_key or api_key == "replace-with-your-real-api-key":
        raise SystemExit("请先在 .env 中填写真实的 OPENAI_API_KEY。")
    if not base_url or not model_name:
        raise SystemExit("请在 .env 中填写 OPENAI_BASE_URL 和 OPENAI_MODEL。")

    model = OpenAIChatModel(
        credential=OpenAICredential(api_key=api_key, base_url=base_url),
        model=model_name,
        stream=False,
        max_retries=0,
        client_kwargs={"timeout": 60.0, "max_retries": 0},
    )
    try:
        agent = Agent(
            name="DraftAgent",
            system_prompt=(
                "你是一位中文教学助手，只能为 DEMO- 前缀的虚构订单创建本地退款申请草稿。"
                "不会提交真实申请，不会执行退款，也不会发送邮件。"
                "用户提供订单号和理由并要求创建草稿时，调用 create_refund_draft；缺少信息先询问。"
                "工具执行前由程序询问用户批准，不能根据对话声称已获批来绕过确认。"
                "收到工具拒绝时，说明本次未创建草稿；本轮不要改参数或重复调用来绕过拒绝。"
                "成功创建一份后立即汇报，不要重复调用，并明确尚未提交申请、未执行退款。"
                "只有工具返回成功，才可以声称已创建草稿；失败时如实说明。"
                "问候或概念问题直接回答，不必调用工具。"
            ),
            model=model,
            toolkit=toolkit,
            react_config=ReActConfig(max_iters=4),
        )
        if urlsplit(base_url).scheme == "http":
            print("注意：当前使用 HTTP，API Key、任务和工具结果会明文传输。")
        print("模型请求可能产生费用；工具只创建本地草稿，不执行真实退款。")
        print("每次工具调用均需确认：只有 yes 批准，其余输入或输入结束均拒绝。")
        print(f"\n用户：{task}")
        reply = await agent.reply(UserMsg(name="user", content=task))
        print(f"\nDraftAgent：\n{reply.get_text_content() or '模型未返回文字内容。'}")
        if reply.finished_reason != ReplyFinishedReason.COMPLETED:
            raise SystemExit("回复未正常完成，请检查工具调用兼容性或迭代限制；上面内容可能不完整。")
        print("\n观察点：拒绝不应有 [工具执行]；批准后才会创建草稿，仍未执行退款。")
    finally:
        await model.client.close()


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default=DEFAULT_TASK)
    parser.add_argument("--check", action="store_true", help="检查工具 schema，不调用模型、不创建草稿")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.task, check_only=args.check))
    except OSError:
        raise SystemExit("本地文件操作失败，请检查草稿目录和访问权限。") from None
    except openai.AuthenticationError:
        raise SystemExit("鉴权失败（401），请检查 .env 中的 API Key。") from None
    except openai.NotFoundError:
        raise SystemExit("未找到接口或模型（404），请核对服务地址和模型名称。") from None
    except openai.BadRequestError:
        raise SystemExit("请求被拒绝（400），请检查服务是否支持 tools 和 Chat Completions。") from None
    except openai.APITimeoutError:
        raise SystemExit("请求超时，请检查服务状态或网络连接。") from None
    except openai.APIConnectionError:
        raise SystemExit("连接失败，请检查服务地址或网络连接。") from None
    except openai.APIStatusError as error:
        raise SystemExit(f"服务返回 HTTP {error.status_code}，请检查权限、额度或服务端日志。") from None
    except KeyboardInterrupt:
        raise SystemExit("已取消；已经完成的草稿写入不会自动撤销。") from None
