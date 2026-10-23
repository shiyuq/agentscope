"""第七课：使用流式事件逐步显示 Agent 的回答。"""

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit

import openai
from dotenv import dotenv_values

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.event import (
    ModelCallEndEvent,
    ModelCallStartEvent,
    ReplyEndEvent,
    ReplyFinishedReason,
    ReplyStartEvent,
    TextBlockDeltaEvent,
)
from agentscope.message import Msg, UserMsg
from agentscope.model import OpenAIChatModel


DEFAULT_QUESTION = "请用中文按三个简短步骤解释如何定义和调用 Python 函数，并给出一个简单例子。"


async def main(
    question: str,
    show_events: bool = False,
    check_only: bool = False,
) -> None:
    # 沿用现有配置，不修改 .env，不打印密钥。
    config = dotenv_values(
        Path(__file__).with_name(".env"),
        encoding="utf-8-sig",
        interpolate=False,
    )
    api_key = (config.get("OPENAI_API_KEY") or "").strip()
    base_url = (config.get("OPENAI_BASE_URL") or "").strip().rstrip("/")
    model_name = (config.get("OPENAI_MODEL") or "").strip()

    if check_only:
        api_key = "offline-check-key"
    elif not api_key or api_key == "replace-with-your-real-api-key":
        raise SystemExit("请先在 .env 中填写真实的 OPENAI_API_KEY。")
    if not base_url or not model_name:
        raise SystemExit("请在 .env 中填写 OPENAI_BASE_URL 和 OPENAI_MODEL。")

    # 1. 模型端开启流式响应，不再等待整段回复才返回。
    model = OpenAIChatModel(
        credential=OpenAICredential(api_key=api_key, base_url=base_url),
        model=model_name,
        stream=True,
        max_retries=0,
        client_kwargs={"timeout": 60.0, "max_retries": 0},
    )

    try:
        agent = Agent(
            name="Teacher",
            system_prompt="你是一位耐心的编程老师。请用中文简洁回答，例子要简单准确。",
            model=model,
        )

        if check_only:
            print("离线自检通过：流式模型和 Agent 创建成功。")
            print("未请求模型，也未验证服务是否支持 SSE 流式响应。")
            return

        if urlsplit(base_url).scheme == "http":
            print("注意：当前使用 HTTP，API Key 和对话内容会明文传输。")
        print("正在请求流式回答；服务或代理缓冲时，内容可能成批出现。")
        print(f"\n用户：{question}")
        print("\nTeacher：", flush=True)

        final_reply: Msg | None = None
        delta_count = 0
        message = UserMsg(name="user", content=question)

        # 2. reply_stream 返回异步事件流，用 async for 逐个接收，不在前面加 await。
        async for item in agent.reply_stream(message, yield_final_msg=True):
            if isinstance(item, TextBlockDeltaEvent):
                # delta 是新增文字，只打印新增部分，避免累计内容重复显示。
                print(item.delta, end="", flush=True)
                delta_count += 1
            elif isinstance(item, Msg):
                # 3. 最终完整消息用于后续业务处理，不再打印一遍全文。
                final_reply = item
            elif show_events and isinstance(
                item,
                (ReplyStartEvent, ModelCallStartEvent, ModelCallEndEvent, ReplyEndEvent),
            ):
                # 只显示生命周期事件类型，不打印完整请求、鉴权信息或思考内容。
                print(f"\n[事件] {item.type}", flush=True)

        print()
        if final_reply is None:
            raise SystemExit("事件流未返回最终消息，请检查服务的流式响应兼容性。")
        if final_reply.finished_reason != ReplyFinishedReason.COMPLETED:
            raise SystemExit("回复未正常完成；上面已经显示的文字可能不完整。")

        print(f"\n完成：收到 {delta_count} 个文字增量事件。")
        print(f"当前历史消息数：{len(agent.state.context)}")
        # 需要完整文字时，使用 final_reply.get_text_content()，不是再发一次请求。
    finally:
        await model.client.close()


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--events", action="store_true", help="同时显示回复与模型调用的生命周期事件")
    parser.add_argument("--check", action="store_true", help="只检查初始化，不请求模型")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.question, show_events=args.events, check_only=args.check))
    except openai.AuthenticationError:
        raise SystemExit("鉴权失败（401），请检查 .env 中的 API Key。") from None
    except openai.NotFoundError:
        raise SystemExit("未找到接口或模型（404），请核对服务地址和模型名称。") from None
    except openai.BadRequestError:
        raise SystemExit("请求被拒绝（400），请检查服务是否支持 stream 和 stream_options.include_usage。") from None
    except openai.APITimeoutError:
        raise SystemExit("流式请求超时；已显示的内容可能不完整，请检查服务状态或网络。") from None
    except openai.APIConnectionError:
        raise SystemExit("连接失败或中断；已显示的内容可能不完整，请检查网络和服务地址。") from None
    except openai.APIStatusError as error:
        raise SystemExit(f"服务返回 HTTP {error.status_code}，请检查权限、额度或服务端日志。") from None
    except KeyboardInterrupt:
        raise SystemExit("\n已取消；已经显示的文字可能不完整。") from None
