"""第二课：复用同一个 Agent，观察多轮对话中的记忆。"""

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit

import openai
from dotenv import dotenv_values

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel


async def main(check_only: bool = False) -> None:
    # 配置沿用第一课的 .env；不修改文件，也不输出密钥。
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

    model = OpenAIChatModel(
        credential=OpenAICredential(api_key=api_key, base_url=base_url),
        model=model_name,
        stream=False,
        max_retries=0,
        client_kwargs={"timeout": 60.0, "max_retries": 0},
    )

    try:
        # 只创建一次 Agent。两轮对话都使用下面这个对象。
        agent = Agent(
            name="Teacher",
            system_prompt="你是一位耐心的编程老师。请用中文简洁回答，不知道的信息不要猜测。",
            model=model,
        )
        print(f"开始时，历史消息数：{len(agent.state.context)}")

        if check_only:
            print("离线自检通过：Agent 创建成功，未请求模型，未测试真实记忆效果。")
            return

        if urlsplit(base_url).scheme == "http":
            print("注意：当前使用 HTTP，API Key 和对话内容会明文传输。")
        print("本示例会连续发送两轮问答请求。")

        # 第一轮：告诉 Agent 两条信息。
        first_question = UserMsg(
            name="user",
            content="我正在学习 Python，目标是开发一个报表助手。请记住这两点，只回复‘记住了’。",
        )
        print(f"\n第一轮 / 用户：{first_question.get_text_content()}")
        first_reply = await agent.reply(first_question)
        print(f"第一轮 / Teacher：{first_reply.get_text_content()}")
        print(f"第一轮后，历史消息数：{len(agent.state.context)}")

        # 第二轮：只提问，不重复答案，检查它是否使用了前文。
        second_question = UserMsg(
            name="user",
            content="我正在学习什么语言？我的开发目标是什么？请根据刚才的对话回答。",
        )
        print(f"\n第二轮 / 用户：{second_question.get_text_content()}")
        second_reply = await agent.reply(second_question)
        print(f"第二轮 / Teacher：{second_reply.get_text_content()}")
        print(f"第二轮后，历史消息数：{len(agent.state.context)}")

        # 查看框架保存在内存中的历史，而不是依靠模型口头说“记住了”。
        print("\n--- agent.state.context 中的对话历史 ---")
        for index, message in enumerate(agent.state.context, start=1):
            print(f"{index}. [{message.role}] {message.get_text_content()}")
    finally:
        await model.client.close()


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只检查初始化，不请求模型")
    args = parser.parse_args()

    try:
        asyncio.run(main(check_only=args.check))
    except openai.AuthenticationError:
        raise SystemExit("鉴权失败（401），请检查 .env 中的 API Key。") from None
    except openai.NotFoundError:
        raise SystemExit("未找到接口或模型（404），请核对服务地址和模型名称。") from None
    except openai.BadRequestError:
        raise SystemExit("请求被拒绝（400），请检查服务的消息格式兼容性。") from None
    except openai.APITimeoutError:
        raise SystemExit("请求超时，请检查服务状态或网络连接。") from None
    except openai.APIConnectionError:
        raise SystemExit("连接失败，请检查服务地址或网络连接。") from None
    except openai.APIStatusError as error:
        raise SystemExit(f"服务返回 HTTP {error.status_code}，请检查权限、额度或服务端日志。") from None
    except KeyboardInterrupt:
        raise SystemExit("已取消。") from None
