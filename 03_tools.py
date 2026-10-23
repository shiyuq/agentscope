"""第三课：让 Agent 调用本地 Python 乘法工具。"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import openai
from dotenv import dotenv_values

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import FunctionTool, Toolkit


DEFAULT_QUESTION = "请使用 multiply 工具计算 137 × 29，并根据工具结果回答。"


def multiply(a: int, b: int) -> int:
    """计算两个整数的乘积。

    Args:
        a (int): 第一个整数。
        b (int): 第二个整数。
    """
    result = a * b
    # print 给人看，return 才是交回框架和模型的工具结果。
    print(f"[工具执行] multiply(a={a}, b={b}) -> {result}")
    return result


async def main(question: str, check_only: bool = False) -> None:
    # 配置沿用前两课，不输出或修改密钥。
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
        # 1. 包装普通函数：自动从函数名、类型注解和文档生成工具说明。
        multiply_tool = FunctionTool(
            multiply,
            # 只允许这个无副作用的乘法函数，不开放其他工具权限。
            permission=PermissionDecision(
                behavior=PermissionBehavior.ALLOW,
                message="允许执行本地整数乘法，不涉及文件或外部服务。",
            ),
        )

        # 2. 将工具放入工具箱，再把工具箱交给 Agent。
        toolkit = Toolkit(tools=[multiply_tool])
        agent = Agent(
            name="Calculator",
            system_prompt=(
                "你是一位计算助手，请用中文简洁回答。"
                "计算整数乘法时，必须先调用 multiply 工具，"
                "收到工具返回结果后再回答，不要自行口算或编造工具结果。"
            ),
            model=model,
            toolkit=toolkit,
            # 限制本课的推理/工具迭代，避免模型反复调用。
            react_config=ReActConfig(max_iters=3),
        )

        if check_only:
            schemas = await toolkit.get_tool_schemas()
            print("离线自检通过：Agent 和乘法工具创建成功。")
            print("下面是自动生成的工具 schema，不是 Python 函数源码：")
            print(json.dumps(schemas, ensure_ascii=False, indent=2))
            print("未请求模型，也未执行乘法工具。")
            return

        if urlsplit(base_url).scheme == "http":
            print("注意：当前使用 HTTP，API Key 和对话内容会明文传输。")
        print("本例通常需要两次模型请求：决定调用工具，再根据结果回答。")
        print(f"\n用户：{question}")

        # 3. 一次 reply 内，框架负责模型调用、工具执行和结果回传。
        reply = await agent.reply(UserMsg(name="user", content=question))
        print(f"\nCalculator：{reply.get_text_content() or '模型未返回文字内容。'}")
        print("\n检查点：上方应出现 [工具执行] 提示，不能只看最终答案是否正确。")
    finally:
        await model.client.close()


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument("--check", action="store_true", help="查看工具 schema，不请求模型")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.question, check_only=args.check))
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
        raise SystemExit("已取消。") from None
