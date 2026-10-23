"""第六课：把 Agent 状态保存到 JSON，下次运行时恢复对话。"""

import argparse
import asyncio
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import openai
from dotenv import dotenv_values
from pydantic import ValidationError

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.event import ReplyFinishedReason
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.state import AgentState


SESSIONS_DIR = Path(__file__).parent / "sessions"
DEFAULT_QUESTION = "我之前告诉你的学习语言和开发目标是什么？如果没有相关信息，请明确说不知道。"


def load_state(path: Path) -> tuple[AgentState, bool]:
    """只在文件不存在时创建新状态；损坏文件报错，不悄悄覆盖。"""
    try:
        json_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AgentState(), False
    return AgentState.model_validate_json(json_text), True


def save_state(state: AgentState, path: Path) -> None:
    """先写同目录临时文件，再替换最终文件，减少半份 JSON 的风险。"""
    json_text = state.model_dump_json(indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    temporary_path.write_text(json_text, encoding="utf-8")
    temporary_path.replace(path)


async def main(
    question: str,
    session_name: str = "lesson06",
    check_only: bool = False,
) -> None:
    # 名称只用字母、数字、下划线或连字符，不允许将路径当作会话名。
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", session_name):
        raise SystemExit("会话名须以字母或数字开头，仅包含字母、数字、下划线或连字符，最多 64 个字符。")
    session_path = SESSIONS_DIR / f"{session_name}.json"

    # 1. 在创建 Agent 之前，恢复该会话的状态。
    state, loaded = load_state(session_path)
    print(f"会话文件：{session_path}")
    print("已加载保存的会话。" if loaded else "尚无会话文件，将从空历史开始。")
    print(f"本次提问前，历史消息数：{len(state.context)}")

    # 模型配置仍从 .env 读取，不保存到会话文件。
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
        # 2. 新建 Agent 对象，但使用从文件恢复的 state，而不是空状态。
        agent = Agent(
            name="Tutor",
            system_prompt=(
                "你是一位学习助手。请用中文简洁回答，根据已有对话提供帮助。"
                "如果前文没有相关信息，就明确说不知道，不要猜测。"
            ),
            model=model,
            state=state,
        )

        if check_only:
            print("离线自检通过：会话状态已就绪，Agent 创建成功。")
            print("未请求模型，未写入或修改会话文件。")
            return

        if urlsplit(base_url).scheme == "http":
            print("注意：当前使用 HTTP，API Key 和对话内容会明文传输。")
        print(f"\n用户：{question}")
        reply = await agent.reply(UserMsg(name="user", content=question))
        if reply.finished_reason != ReplyFinishedReason.COMPLETED:
            raise SystemExit("回复未正常完成，没有覆盖已保存的会话。")
        print(f"\nTutor：{reply.get_text_content() or '模型未返回文字内容。'}")

        # 3. 只在本轮回复完成后保存，下一次运行可恢复这份状态。
        save_state(agent.state, session_path)
        print(f"\n已保存会话，历史消息数：{len(agent.state.context)}")
        print("会话文件含对话内容，请勿提交到代码仓库或公开分享。")
    finally:
        await model.client.close()


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--session", default="lesson06", help="会话名，默认 lesson06；同名会话恢复同一份历史")
    parser.add_argument("--check", action="store_true", help="检查初始化和已有会话，不请求模型、不保存")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.question, session_name=args.session, check_only=args.check))
    except ValidationError:
        raise SystemExit("会话 JSON 或状态格式不合法，未覆盖该文件。请检查文件，或用 --session 选择一个新会话。") from None
    except OSError:
        raise SystemExit("会话文件读写失败，请检查路径、权限或磁盘状态。") from None
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
