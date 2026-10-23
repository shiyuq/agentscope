"""第一课：使用 AgentScope 2.0 创建一个中文问答 Agent。"""

import argparse
import asyncio
import sys
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit

import openai
from dotenv import dotenv_values

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel


DEFAULT_QUESTION = "什么是 AI Agent？它和普通的大模型聊天有什么区别？"
PLACEHOLDER_KEY = "replace-with-your-real-api-key"


def read_config(check_only: bool) -> tuple[str, str, str]:
    """只读取本脚本旁边的 .env，不使用其他项目的配置。"""
    env_path = Path(__file__).with_name(".env")
    if not env_path.is_file():
        raise SystemExit("缺少 .env 文件，请在本脚本所在目录创建它。")

    config = dotenv_values(env_path, encoding="utf-8-sig", interpolate=False)
    api_key = (config.get("OPENAI_API_KEY") or "").strip()
    base_url = (config.get("OPENAI_BASE_URL") or "").strip().rstrip("/")
    model_name = (config.get("OPENAI_MODEL") or "").strip()

    if not check_only and (not api_key or api_key == PLACEHOLDER_KEY):
        raise SystemExit("请先打开 .env，将 OPENAI_API_KEY 替换为真实密钥。")
    if not model_name:
        raise SystemExit("请在 .env 中填写 OPENAI_MODEL。")
    try:
        url = urlsplit(base_url)
        valid_url = url.scheme in {"http", "https"} and bool(url.hostname)
    except ValueError:
        valid_url = False
    if not valid_url:
        raise SystemExit("OPENAI_BASE_URL 必须是有效的 HTTP 或 HTTPS 地址。")

    # 自检使用假密钥；不会发送请求，也不输出真实密钥。
    return ("offline-check-key" if check_only else api_key), base_url, model_name


async def main(question: str, check_only: bool = False) -> None:
    api_key, base_url, model_name = read_config(check_only)

    # 1. 配置模型：请求发送到你的服务，而不是 OpenAI 官方端点。
    model = OpenAIChatModel(
        credential=OpenAICredential(api_key=api_key, base_url=base_url),
        model=model_name,
        stream=False,
        max_retries=0,
        client_kwargs={"timeout": 60.0, "max_retries": 0},
    )

    try:
        # 2. 创建 Agent：2.x 的 Formatter 已由模型配置，对话历史保存在 state 中。
        agent = Agent(
            name="Teacher",
            system_prompt=(
                "你是一位耐心的编程老师。请用中文回答，"
                "先给简短解释，再给一个简单例子。"
            ),
            model=model,
        )

        if check_only:
            print(f"离线自检通过：AgentScope {version('agentscope')}，Agent 创建成功。")
            print("未请求模型服务；尚未验证地址、密钥和模型兼容性。")
            return

        if urlsplit(base_url).scheme == "http":
            print("注意：当前使用 HTTP，API Key 和对话内容会明文传输。")
        print("正在请求你的模型服务……")

        # 3. 创建消息，等待 Agent 回复。
        question_msg = UserMsg(name="user", content=question)
        reply = await agent.reply(question_msg)

        # 4. Msg 不一定只有纯文字，使用此方法提取文字回答。
        print("\nTeacher：")
        print(reply.get_text_content() or "模型未返回文字内容。")
    finally:
        await model.client.close()


if __name__ == "__main__":
    # Windows 终端也能正确显示中文。
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--check", action="store_true", help="只检查配置和对象创建，不请求模型")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.question, check_only=args.check))
    except openai.AuthenticationError:
        raise SystemExit("鉴权失败（401），请检查 .env 中的 API Key。") from None
    except openai.PermissionDeniedError:
        raise SystemExit("权限不足（403），请检查密钥和模型访问权限。") from None
    except openai.NotFoundError:
        raise SystemExit("未找到接口或模型（404），请核对 /v1 前缀及 OPENAI_MODEL。") from None
    except openai.BadRequestError:
        raise SystemExit("请求被拒绝（400），请核对服务是否支持 Chat Completions 及消息格式。") from None
    except openai.RateLimitError:
        raise SystemExit("请求受限（429），请检查额度或稍后再试。") from None
    except openai.APITimeoutError:
        raise SystemExit("请求超时，请检查服务状态或网络连接。") from None
    except openai.APIConnectionError:
        raise SystemExit("连接失败，请检查服务地址、HTTPS 支持或网络连接。") from None
    except openai.APIStatusError as error:
        raise SystemExit(f"服务返回 HTTP {error.status_code}，请检查服务端日志。") from None
    except KeyboardInterrupt:
        raise SystemExit("已取消。") from None
