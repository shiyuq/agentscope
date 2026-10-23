"""第五课：用 Pydantic 定义字段，让 Agent 返回经过校验的结构化数据。"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import openai
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel


DEFAULT_TASK = "请为 Python 初学者制定一个关于列表的入门学习计划，恰好 3 个步骤，总时长不超过 60 分钟。"


class LearningPlan(BaseModel):
    """程序希望收到的学习计划格式，不是已经生成的计划。"""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, description="学习主题。")
    steps: list[str] = Field(
        min_length=3,
        max_length=3,
        description="恰好 3 个学习步骤，每个步骤用一个字符串表示。",
    )
    estimated_minutes: int = Field(
        strict=True,
        gt=0,
        le=60,
        description="预计总学习分钟数，必须是 1 到 60 的整数。",
    )


async def main(task: str, check_only: bool = False) -> None:
    # 沿用现有配置，不修改 .env，也不输出密钥。
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
        agent = Agent(
            name="Planner",
            system_prompt=(
                "你是一位编程学习规划助手。请使用中文制定适合初学者的计划，"
                "按照要求的结构化格式提交最终结果。"
            ),
            model=model,
            react_config=ReActConfig(max_iters=3, structured_output_grace_iters=1),
        )

        if check_only:
            print("离线自检通过：Agent 和 LearningPlan schema 创建成功。")
            print(json.dumps(LearningPlan.model_json_schema(), ensure_ascii=False, indent=2))
            print("未请求模型，也未验证服务的工具调用兼容性。")
            return

        if urlsplit(base_url).scheme == "http":
            print("注意：当前使用 HTTP，API Key 和对话内容会明文传输。")
        print("本版本通过内置工具生成结构化输出，服务需要支持工具调用。")
        print("若输出未通过校验，框架可能再次请求模型修正，产生额外费用。")
        print(f"\n任务：{task}")

        # 1. 传入格式定义，由框架向模型提供字段规则并校验工具提交的数据。
        reply = await agent.reply(
            UserMsg(name="user", content=task),
            structured_schema=LearningPlan,
        )

        # 2. 结构化结果在这个属性里，不是 get_text_content() 的文字。
        if reply.structured_output is None:
            raise SystemExit("未生成符合要求的结构化结果，请检查服务是否支持工具调用。")

        # 3. 转为本地 Pydantic 对象，明确验证字段后再交给业务代码。
        plan = LearningPlan.model_validate(reply.structured_output)
        print("\n--- 经过校验的 JSON ---")
        print(plan.model_dump_json(indent=2))

        # 4. 不必从自然语言中寻找数字或拆分步骤，可以直接读取字段。
        print("\n--- 像普通 Python 对象一样使用 ---")
        print(f"主题：{plan.topic}")
        for index, step in enumerate(plan.steps, start=1):
            print(f"步骤 {index}：{step}")
        print(f"预计总时长：{plan.estimated_minutes} 分钟")
    finally:
        await model.client.close()


if __name__ == "__main__":
    for output in (sys.stdout, sys.stderr):
        if hasattr(output, "reconfigure"):
            output.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default=DEFAULT_TASK)
    parser.add_argument("--check", action="store_true", help="查看输出格式规则，不请求模型")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.task, check_only=args.check))
    except ValidationError:
        raise SystemExit("返回的数据未满足 LearningPlan 的字段规则，未继续处理。") from None
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
