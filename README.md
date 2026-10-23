# AgentScope 入门：第一课，单 Agent 问答

本项目使用 Python 3.13.15、AgentScope 2.0.10，连接你自己的 OpenAI 兼容服务。依赖已经安装在 `.venv` 中，无需激活环境。

## 1. 填入 API Key

打开本目录的 `.env`，将以下占位值替换为你的真实密钥：

```dotenv
OPENAI_API_KEY=replace-with-your-real-api-key
```

不要把真实密钥发到聊天里或提交到版本库。`.gitignore` 已忽略 `.env`。

其他配置已经按你提供的信息填写：

- 模型：`gpt-6.1-sol`
- 已通过一次真实问答验证的 API 前缀：`http://ai.sit.mzhaozhao.com/v1`

**注意：HTTP 不加密，运行时 API Key 和对话内容会明文传输。** 如果服务提供 HTTPS，请先将 `.env` 中的 `OPENAI_BASE_URL` 改成确认可用的 HTTPS 地址。

2026-10-13 已使用本地配置完成一次真实问答，程序退出码为 0，并收到中文回答。当前 `/v1/chat/completions` 路径可用，因此保留 base_url 末尾的 `/v1`。

本次只验证了非流式文本问答；工具调用、流式响应和多轮对话尚未实测。如果以后更换服务，base_url 应填写接口前缀，而不是包含 `/chat/completions` 的完整路径。

程序不会自动尝试其他地址，避免将密钥发送到意外的接口。

## 2. 运行

在本目录的 Git Bash 终端运行：

```bash
.venv/Scripts/python.exe 01_chat.py
```

默认只问一个简短问题，不启用工具，不进行自动追问。真实运行会向你配置的服务发送 API Key 和示例问题，费用以你的服务计费规则为准。

也可以指定自己的问题：

```bash
.venv/Scripts/python.exe 01_chat.py "用一个例子解释 Python 列表"
```

PowerShell 中使用：

```powershell
.\.venv\Scripts\python.exe .\01_chat.py
```

## 3. 无网络自检

无需填写真实密钥，也不会请求模型：

```bash
.venv/Scripts/python.exe 01_chat.py --check
```

此命令只能确认依赖、配置格式和 Agent 对象能正常加载，不能证明服务地址、密钥、模型或协议兼容性正确。

## 4. 理解本课

代码将完成这几件事：

1. 从本地 `.env` 读取配置，不把密钥写进 Python 源码。
2. 用 `OpenAIChatModel` 连接你的服务，而不是 OpenAI 官方端点。
3. 创建一个 `Agent`，用 `system_prompt` 定义中文老师的角色。
4. 将用户问题交给 Agent，等待模型响应并显示答案。

**版本提醒：** 之前介绍的 `ReActAgent`、独立 `Formatter`、`InMemoryMemory` 是 1.x 风格。本项目已安装 2.0.10，使用新版接口，不要直接混用旧教程的构造参数。

| 1.x 教程写法 | 本项目 2.0.10 写法 |
| --- | --- |
| `ReActAgent` | `Agent` |
| `sys_prompt=` | `system_prompt=` |
| `OpenAIChatModel(api_key=..., model_name=...)` | `OpenAIChatModel(credential=OpenAICredential(...), model=...)` |
| `await agent(msg)` | `await agent.reply(msg)` |
| Agent 接收 `formatter=` | 模型默认使用 OpenAIChatFormatter |
| 显式传入 `InMemoryMemory()` | 对话历史保存在 `agent.state.context` |

核心调用是：

```python
question_msg = UserMsg(name="user", content="什么是 AI Agent？")
reply = await agent.reply(question_msg)
print(reply.get_text_content())
```

实际脚本已通过无网络自检、模拟响应的完整问答验证，以及一次使用本地真实 API Key 的服务调用。密钥未在输出中显示，`.env` 未被改写。

## 5. 常见错误

- 缺少 API Key：检查 `.env` 中是否仍为占位值。
- 401 / 403：检查密钥及其模型访问权限。
- 404：检查服务接口前缀及模型标识，结合服务返回信息判断。
- 400：查看服务是否支持 Chat Completions，或是否拒绝了某个请求参数。
- 连接失败 / 超时：检查地址、网络和服务状态。

反馈错误时不要附带密钥或带鉴权信息的完整请求日志。

## 6. 重建环境

以后需要重建时，在本目录执行：

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

## 7. 第二课：多轮对话与记忆

`02_memory.py` 复用现有 `.env` 和虚拟环境，不修改第一课代码。

先做离线自检（不请求模型）：

```bash
.venv/Scripts/python.exe 02_memory.py --check
```

再运行两轮真实对话（会向你的服务发送请求，可能产生费用）：

```bash
.venv/Scripts/python.exe 02_memory.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\02_memory.py
```

观察下面三个结果：

1. 第一轮告诉 Agent：学习语言是 Python，目标是开发报表助手。
2. 第二轮不重复这些信息，检查回答能否回忆出 Python 和报表助手。
3. 终端显示 `agent.state.context` 的消息数量和文字内容。在本例的普通问答中，数量应从 0 到 2，再到 4，每轮包括一条用户消息和一条助手回复。

关键是 **Agent 只创建一次，然后在同一实例上顺序调用两次 `await agent.reply(...)`**。框架保存历史，并在后续模型请求中带上相关上下文；这不代表模型的训练参数被修改。

本例的历史只保存在进程内存中，重新运行会创建新的 Agent，不会自动恢复上次对话。`--check` 只验证初始化，不能验证模型是否正确使用历史。

验证范围：已做离线初始化和模拟响应的两轮流程检查，尚未对第二课执行真实模型调用。

## 8. 第三课：工具调用

`03_tools.py` 给 Agent 注册一个本地 Python 乘法函数 `multiply`，仍使用现有 `.env` 和虚拟环境，不安装新依赖。

先做离线自检，查看自动生成的工具说明和参数 schema（不请求模型）：

```bash
.venv/Scripts/python.exe 03_tools.py --check
```

再运行真实工具调用示例：

```bash
.venv/Scripts/python.exe 03_tools.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\03_tools.py
```

默认问题是使用工具计算 `137 × 29`，正确结果为 `3973`。可以在命令末尾指定其他问题：

```bash
.venv/Scripts/python.exe 03_tools.py "请使用 multiply 工具计算 256 × 48。"
```

正常情况下的调用流程：

1. 框架把问题和工具的说明、参数 schema 发送给模型，不会把整个 Python 函数源码发送过去。
2. 模型返回一个工具调用请求，例如函数名 `multiply` 和参数 `{"a": 137, "b": 29}`。
3. AgentScope 在本地执行注册的函数，终端显示 `[工具执行] multiply(a=137, b=29) -> 3973`。
4. 框架把工具结果交给模型，模型再生成最终回答。

**一次 `await agent.reply(...)` 不一定只调用一次模型。** 这个示例通常需要两次模型请求：第一次决定调用工具，第二次根据结果回答；实际次数取决于模型行为，费用以你的服务规则为准。

判断成功不能只看最终数字是否正确，必须看到 `[工具执行]` 提示。若模型直接回答却没有这条提示，说明没有验证到真实函数执行。若服务拒绝 `tools` 参数，则需要确认其支持 OpenAI 兼容的工具调用，而不仅是普通聊天。

本例只给无副作用的乘法工具设置允许执行，不开放 Shell、文件操作或其他工具。真实项目中，发邮件、删除文件、付款等有副作用的工具应单独设计确认和权限控制。

验证范围：语法和离线自检已通过；模拟模型响应的完整流程已验证两次请求、一次真实本地乘法执行，以及结果 `3973` 对应原 `tool_call_id` 回传。尚未对第三课执行真实模型调用，因此你的服务是否支持工具调用仍需运行确认。

## 9. 第四课：两个 Agent 串行协作

`04_multi_agent.py` 使用两个角色完成一个讲解任务：`Writer` 生成草稿，`Reviewer` 检查并给出修订答案。复用现有配置和依赖，不使用工具，也不依赖服务的工具调用能力。

离线检查初始化（不请求模型）：

```bash
.venv/Scripts/python.exe 04_multi_agent.py --check
```

运行完整流程（依次发送两次模型请求，可能产生费用）：

```bash
.venv/Scripts/python.exe 04_multi_agent.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\04_multi_agent.py
```

也可以指定任务：

```bash
.venv/Scripts/python.exe 04_multi_agent.py "向 Python 初学者解释函数参数与返回值，给出简单例子。"
```

核心结构：

```python
writer = Agent(name="Writer", system_prompt="你负责撰写讲解。", model=model)
reviewer = Agent(name="Reviewer", system_prompt="你负责检查并修订草稿。", model=model)

draft = await writer.reply(UserMsg(name="user", content=topic))
review_input = UserMsg(
    name="user",
    content=f"原始任务：{topic}\n待审阅草稿：{draft.get_text_content()}",
)
review = await reviewer.reply(review_input)
```

两个 Agent 可以共用一个模型对象和一把密钥，但它们默认各自创建独立的 `state`。第二个 Agent 不会自动读取第一个的历史；代码必须显式把需要的信息传过去。

在这个无工具的短问答示例中，预期历史消息数是：

- 初始：`Writer=0，Reviewer=0`。
- 写作完成：`Writer=2，Reviewer=0`。
- 审阅完成：`Writer=2，Reviewer=2`。

审阅者的一条用户消息中包含原始任务和完整草稿，因此无需复制讲解者的整个 `state.context`。这是一种固定顺序的两步工作流，不是多个 Agent 自动讨论，也不是并行执行。审阅者输出不会自动回到讲解者；本例以审阅结果作为最终输出。

多 Agent 不保证答案一定更好：审阅者仍可能漏错、误判，尤其使用同一模型时可能重复相同错误。关键结论仍需要代码测试、外部事实或人工验证；增加角色也会增加请求次数、输入 token 和等待时间。

验证范围：语法检查、离线初始化、两次模拟响应的消息交接和独立历史检查通过；尚未对第四课执行真实模型调用，也未评估真实讲解与审阅的质量。

## 10. 第五课：结构化输出

`05_structured_output.py` 让 Agent 生成程序可读取的学习计划，而不是仅返回一段自然语言。沿用现有配置；Pydantic 已随依赖安装，无需安装新包。

格式由 `LearningPlan(BaseModel)` 定义：

- `topic`：非空字符串，表示学习主题。
- `steps`：恰好 3 个字符串步骤。
- `estimated_minutes`：严格整数，范围 1 到 60。
- 禁止额外字段。

离线查看 schema（不请求模型）：

```bash
.venv/Scripts/python.exe 05_structured_output.py --check
```

运行真实示例：

```bash
.venv/Scripts/python.exe 05_structured_output.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\05_structured_output.py
```

可以更换任务，但仍应符合既定 schema：

```bash
.venv/Scripts/python.exe 05_structured_output.py "制定一个 Python 函数入门计划，恰好 3 步，总时长 30 分钟。"
```

关键调用：

```python
reply = await agent.reply(
    UserMsg(name="user", content=task),
    structured_schema=LearningPlan,
)

if reply.structured_output is None:
    raise SystemExit("未生成结构化结果。")

plan = LearningPlan.model_validate(reply.structured_output)
print(plan.topic)
print(plan.steps)
print(plan.estimated_minutes)
```

在本项目的 AgentScope 2.0.10 中，`Agent.reply(structured_schema=...)` 为该次回复自动加入内置的 `GenerateStructuredOutput` 工具，让模型把字段作为工具参数提交；框架校验并把成功结果放到 `reply.structured_output`。这不是单纯在提示词中要求“返回 JSON”，也不是在本例中使用服务商原生 `response_format` 的严格解码模式。你的服务需要支持 OpenAI 兼容工具调用，普通文本问答成功并不能证明此功能兼容。

不合格数据不会作为成功结果直接交给业务代码；框架可能将校验错误交给模型再尝试，受迭代限制影响，也可能最终失败。`max_retries=0` 只关闭失败请求的重试，不禁止这种校验失败后的新一轮生成，后者可能产生额外费用。

**格式正确不代表事实正确。** 能检查类型、范围、字段数量，不意味着学习步骤一定合理或时长估计一定可靠，内容质量仍需独立评估。

验证范围：语法与离线自检通过；模拟结构化输出成功路径、90 分钟的无效输出被拒绝后修正为 45 分钟的流程通过；本地校验拒绝零分钟、字符串时长、错误步骤数量和额外字段。尚未执行第五课的真实模型调用。

## 11. 第六课：会话持久化与恢复

`06_session.py` 在每次完整回复后将 `AgentState` 保存到本地 JSON；下次运行时读取存档，再用 `state=` 创建 Agent。默认文件是本脚本旁的 `sessions/lesson06.json`，不受终端当前目录影响。

先做离线自检（加载已有状态，但不请求模型，也不写入文件）：

```bash
.venv/Scripts/python.exe 06_session.py --check
```

然后依次运行两条命令，每条都是新的程序进程，分别请求一次模型并保存状态，可能产生费用：

```bash
.venv/Scripts/python.exe 06_session.py "我正在学习 Python，目标是开发一个报表助手。请记住。"
.venv/Scripts/python.exe 06_session.py "我之前告诉你的学习语言和开发目标是什么？"
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\06_session.py "我正在学习 Python，目标是开发一个报表助手。请记住。"
.\.venv\Scripts\python.exe .\06_session.py "我之前告诉你的学习语言和开发目标是什么？"
```

默认空会话第一次运行应显示提问前历史为 0、保存后为 2；第二次应显示已加载、提问前为 2、保存后为 4。以前已用同名会话聊过时，数量会更大。

用不同的名称隔离会话，无需删除或覆盖旧存档：

```bash
.venv/Scripts/python.exe 06_session.py --session other "我正在学习 JavaScript。"
```

再次用 `--session other` 会继续该会话；不带此选项则继续默认 `lesson06`。本课限定会话名为简单的字母、数字、下划线和连字符，不接受任意路径。

核心 API：

```python
# 保存：状态对象 -> JSON 字符串 -> 文件
json_text = agent.state.model_dump_json(indent=2)
path.write_text(json_text, encoding="utf-8")

# 恢复：文件 -> JSON 字符串 -> 状态对象
json_text = path.read_text(encoding="utf-8")
state = AgentState.model_validate_json(json_text)
agent = Agent(name="Tutor", system_prompt=system_prompt, model=model, state=state)
```

这里保存和恢复的方法继承自 Pydantic，均为同步方法，不加 `await`；`model_validate_json` 接受的是 JSON 内容，不是文件路径。AgentScope 2.0.10 的 `AgentState` 没有本课可调用的 `save/load` 文件方法。

实际脚本在文件不存在时创建 `AgentState()`；存档损坏则报错，不静默清空。在回复正常完成后，先写同目录临时文件，再用 `Path.replace()` 替换最终文件，以减少写入中断产生半截 JSON 的风险。此做法不处理多个进程同时写同一会话，请不要并行运行同一个会话名。

存档保存的是状态数据，不是运行中的协程、模型训练参数、模型客户端或 `system_prompt`。模型配置和角色提示由程序重新提供，再把恢复的历史带入后续请求。本例只演示已完成回复的跨进程续聊，不演示在工具执行中途暂停和续跑。

会话 JSON 不加密，可能包含完整对话及其他状态数据。模型凭证不会因为传给 Agent 而自动写入 `AgentState`，但主动写入消息或工具结果的敏感信息仍可能被保存。`.gitignore` 已忽略 `sessions/`，只加载自己保存的存档，不要公开分享。

验证范围：语法和离线自检通过；临时目录中的两次模拟问答验证了状态保存、不同 Agent 实例恢复、原有历史进入第二次请求；`--check` 不改文件、损坏 JSON 不被覆盖、测试密钥未被保存、客户端正确关闭。尚未执行第六课的真实模型调用。

## 12. 第七课：流式输出与事件

`07_streaming.py` 让终端随着文字增量逐步显示回答。沿用现有配置，不注册工具、不保存会话、不安装新依赖。

离线检查初始化（不请求模型）：

```bash
.venv/Scripts/python.exe 07_streaming.py --check
```

运行真实流式回答（请求模型，可能产生费用）：

```bash
.venv/Scripts/python.exe 07_streaming.py
```

显示额外的生命周期事件：

```bash
.venv/Scripts/python.exe 07_streaming.py --events
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\07_streaming.py --events
```

也可以指定问题：

```bash
.venv/Scripts/python.exe 07_streaming.py "请用一个例子解释 Python 的 for 循环。"
```

核心是两处配合：

1. `OpenAIChatModel(..., stream=True)`：模型请求开启流式响应。
2. `async for item in agent.reply_stream(..., yield_final_msg=True)`：逐个消费 Agent 事件，并在最后获取完整 Msg。这里不在 `reply_stream(...)` 前加 `await`。

```python
final_reply = None
async for item in agent.reply_stream(message, yield_final_msg=True):
    if isinstance(item, TextBlockDeltaEvent):
        print(item.delta, end="", flush=True)
    elif isinstance(item, Msg):
        final_reply = item
```

`TextBlockDeltaEvent.delta` 是新增片段，不是累计全文；只打印它，避免重复。片段不一定是一个字或一个 token。`end=""` 避免每次打印换行，`flush=True` 及时刷新终端缓冲。

本版 `Agent.reply` 在内部消费同一条事件流并返回最终 Msg，因此仅开启模型 `stream=True`、但仍在最后 `await agent.reply(...)` 后打印，终端不会自动逐片段显示。`reply_stream` 即使配合非流式模型也可产生事件，但模型文字仍需等待完整响应后才能处理，两层开关不能混淆。

`--events` 显示 `REPLY_START`、`MODEL_CALL_START`、`MODEL_CALL_END`、`REPLY_END`。本例只打印生命周期类型和用户可见文字，不打印思考内容、请求头或整个对象。最终 Msg 供代码获取 `get_text_content()` 等信息，不再全文打印，否则会重复显示回答。

服务端须支持 Chat Completions 的 SSE（`text/event-stream`）响应，且当前适配器会发送 `stream_options={"include_usage": true}`。普通非流式聊天成功不意味着流式一定兼容。流式通常是一个 HTTP 请求分段传回，不是每个片段单独请求；不保证总生成时间更短，也不保证代理不会缓冲成批返回。

流式过程中已经显示的文字只是部分结果；连接中断或用户取消时可能不完整。本例在结束时检查最终 Msg 的完成状态。增量事件数不是输出 token 数，也不能直接用来估计费用。

验证范围：语法、自检、模拟 SSE 解析通过；验证 3 个增量合成最终历史文字、终端不重复显示、四类生命周期事件可见、响应流和客户端正确关闭。尚未执行第七课的真实模型调用，也未验证真实网络下的首段延迟和分段效果。

## 13. 第八课：本地资料问答（简化 RAG）

`08_rag.py` 在提问前从 `knowledge/lesson08/` 检索资料片段，再把问题和证据一起交给 Agent。本课自己实现简单检索器，不使用 AgentScope 内置 RAG 模块、向量数据库、Embedding API 或工具调用；目的是理解检索增强生成的基本流程。

本课的三份 Markdown 资料是虚构的“青禾报表”产品说明：

- `refund.md`：退款期限、条件和处理方式。
- `export.md`：导出格式、额度和说明。
- `support.md`：客服工作时间和占位联系方式。

所有政策和功能均为教学编写，不代表真实公司。程序只读取本课目录的 `.md` 文件，以 `##` 二级标题拆分段落，为片段附加 `文件名#标题` 来源。每次运行重新加载，不创建持久索引。

先只做本地检索，不读取密钥、不请求模型：

```bash
.venv/Scripts/python.exe 08_rag.py --check
.venv/Scripts/python.exe 08_rag.py "会员每天可以导出多少次？" --retrieve-only
```

运行真实问答（将问题和命中片段发送到配置的服务，可能产生费用）：

```bash
.venv/Scripts/python.exe 08_rag.py
.venv/Scripts/python.exe 08_rag.py "会员每天可以导出多少次？"
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\08_rag.py
```

观察能否根据虚构资料回答并标注来源：退款期限是支付成功后 7 个自然日，普通退款要求尚未使用付费导出；会员导出额度是每天 50 次、每次最多 10,000 行。

检索仅用词项重合排序：英文按单词，连续中文按相邻两个字拆分，过滤部分常见词，按问题与段落的重合词项数排序，取最多 3 个有匹配的片段。这不是专业中文分词、BM25 或语义向量检索；同义词、歧义和短问题可能导致漏检或误检。无匹配时程序停止，不调用模型；这不证明资料库里一定不存在答案。

核心结构：

```python
chunks = load_chunks()
hits = retrieve(question, chunks)
evidence = json.dumps(hits, ensure_ascii=False, indent=2)
reply = await agent.reply(
    UserMsg(name="user", content=f"用户问题：{question}\n检索证据：{evidence}"),
)
```

RAG 不会训练模型，也不会让模型自行读取本地文件。是 Python 先找资料，再把证据带进本次请求；模型负责根据证据组织回答。本例由代码固定先检索，不是由 Agent 自动决定何时调用搜索工具。

可测试无匹配问题：

```bash
.venv/Scripts/python.exe 08_rag.py "青禾报表的董事长叫什么名字？" --retrieve-only
```

也可测试有关键词匹配、但资料不足的问题，例如“退款必须提供身份证吗？”。程序可能找到退款段落，但这些段落没有身份证要求，模型应说明“提供的资料未说明”，不能将关键词命中当成答案存在。

提示词要求只依据证据、资料中的指令不得执行、引用原样来源。这些是引导而非安全或正确性保证：模型仍可能编造内容、伪造或误用引用，必须核对原文。私有资料片段会被发送到模型服务，运行前确认有权限，HTTP 还会明文传输。不要把 `.env` 或密钥加入知识目录。

验证范围：语法、本地加载 8 个段落、退款/导出/无匹配检索通过；模拟模型请求验证仅相关片段进入提示、来源标注可显示、客户端关闭；离线和无匹配分支不读凭证、不创建模型。尚未执行第八课真实模型调用，未评估真实答案的依据和引用准确性。

## 14. 第九课：Agent 自主检索（Agentic RAG）

`09_agentic_rag.py` 把上一课的本地检索包装成 `search_knowledge(query)` 工具，交给 Agent 决定是否调用、选择查询词，以及证据不足时是否再次查询。不增加新依赖，沿用现有 `.env`，不修改密钥。

第八、九课共用 `knowledge_search.py` 中的 `tokenize`、`load_chunks` 和 `retrieve`；原有检索逻辑从 `08_rag.py` 移到该模块，第八课的命令和行为不变。知识资料仍限定为 `knowledge/lesson08/` 中的虚构产品 Markdown，不开放任意文件路径。请把三个 Python 文件和共享模块保持在同一项目目录。

离线查看工具 schema：

```bash
.venv/Scripts/python.exe 09_agentic_rag.py --check
```

直接测试检索函数，不调用模型、不读取密钥：

```bash
.venv/Scripts/python.exe 09_agentic_rag.py "会员 导出 额度" --search-only
```

注意 `--search-only` 是代码直接调用本地函数，用于测试检索器本身，不证明模型选择了搜索。

运行 Agent 自主检索（调用模型，可能多轮并产生费用，服务须支持 tools）：

```bash
.venv/Scripts/python.exe 09_agentic_rag.py
.venv/Scripts/python.exe 09_agentic_rag.py "你好"
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\09_agentic_rag.py
```

默认问题同时询问会员导出额度和普通退款条件。模型可以选择一次合并查询，也可以分开搜索；证据不足时可以改写查询。不要把模拟测试中固定的两次调用当成真实模型必定遵循的顺序。

本地函数的核心：

```python
def search_knowledge(query: str) -> str:
    chunks = load_chunks()
    hits = retrieve(query, chunks, top_k=3)
    return json.dumps({"query": query, "hits": hits}, ensure_ascii=False)
```

再用 `FunctionTool(search_knowledge, permission=...)` 包装，放进 `Toolkit(tools=[search_tool])`，传给 `Agent(..., toolkit=toolkit)`。真正的模型调用入口仍是 `await agent.reply(UserMsg(...))`，不在调用前固定执行 `retrieve()`。

核心区别：第八课由 Python 写死“检索 → 回答”；第九课第一次请求先给模型问题和工具说明，模型可直接回答或返回工具调用，框架执行后再把证据交给模型。本例不是搜索算法更高级，仍是相同的关键词重合检索；变化的是检索的控制流程。

正常产品事实问题应看到 `[工具执行] search_knowledge(query=...)`，回答应依据实际命中的段落标注来源；问候可以直接回答，不必读取知识文件。产品问题若没搜索却直接给出规则，或引用的段落不支持结论，都不算符合要求。模型决定调用的行为受提示引导，不是程序硬保证。

`ReActConfig(max_iters=4)` 限制推理/工具循环，不是费用上限，也不是四次搜索的承诺。多个工具调用可能在一次模型响应中提出，连续工具调用也可能跨多次模型请求；工具调用次数、模型请求次数和 token 数不能混为一谈。

无匹配时，工具返回空 `hits` 和说明，让模型可以改写关键词或承认证据不足；不能把空结果视作现实中不存在该事实。片段只是证据，不应服从片段中的指令；提示词并非安全隔离或引用正确性的保证，运行后仍需核对原文。所有命中片段会送往你配置的模型服务，换成真实私有资料前要确认授权。

验证范围：第八课本地检索回归通过；第九课语法、自检、直接本地搜索、两次顺序工具调用后回答的模拟流程、问候不检索的模拟流程、无匹配工具返回、客户端关闭均通过。模拟测试只证明代码能处理这些分支，未验证真实模型的检索决策或引用质量，也没有发出真实模型请求。

## 15. 第十课：工具权限与人工确认

`10_permissions.py` 演示 **Agent 可以提出操作，但有副作用的工具不能未经批准就执行**。本课只有一个工具：`create_refund_draft(order_id, reason)`，在本地创建虚构订单的退款申请草稿；不提交申请、不执行退款、不发送邮件，也不连接业务系统。不增加依赖，不修改前九课或 `.env`。

第九课的检索工具只读取限定的教学资料，可以直接放行。本课会写文件，所以在执行前展示模型提出的工具名、完整参数和写入目录，逐次询问人是否批准。提示词写“请先确认”不等于真正的执行权限检查。

先做离线自检（不读取密钥、不请求模型、不询问批准、不创建目录或草稿）：

```bash
.venv/Scripts/python.exe 10_permissions.py --check
```

运行真实示例（需要支持工具调用，会请求模型并可能产生费用）：

```bash
.venv/Scripts/python.exe 10_permissions.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\10_permissions.py
```

建议运行两次，分别观察拒绝和批准：

1. 第一次，在 `[待确认]` 后输入 `no` 或直接回车。应看到 `[权限] 已拒绝本次调用`，没有该次调用的 `[工具执行]`，也没有该次调用产生的新草稿。模型会收到拒绝结果，应如实说明未创建。
2. 第二次，先检查参数，然后输入小写 `yes`。应先看到批准提示，再出现 `[工具执行]`；新 JSON 位于脚本旁的 `sessions/lesson10/refund-随机标识.json`，状态为 `draft_only`。已有草稿不会被覆盖，程序也不会把它当成退款成功。

默认任务使用虚构订单 `DEMO-1001` 和理由“重复购买”。也可换一个演示任务：

```bash
.venv/Scripts/python.exe 10_permissions.py "请为虚构订单 DEMO-1002 创建本地退款申请草稿，理由是误购，不要提交真实申请。"
```

模型不一定按预期调用工具；如果只返回文字，没有出现 `[待确认]`，就没有验证到人工审批链。输入 `y`、`YES`、空白或其他内容均拒绝，只有去除首尾空白后为 `yes` 才批准；输入结束（EOF）也默认拒绝。`Ctrl+C` 取消程序，但已经完成的写入不会自动撤销。

本课的核心是重写工具的原生权限方法：

```python
class ConfirmingFunctionTool(FunctionTool):
    async def check_permissions(self, tool_input, context):
        print(json.dumps(tool_input, ensure_ascii=False, indent=2))
        try:
            answer = await asyncio.to_thread(input, "仅批准本次调用？输入 yes 批准：")
        except EOFError:
            answer = ""
        allowed = answer.strip() == "yes"
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW if allowed else PermissionBehavior.DENY,
            message="用户批准本次调用。" if allowed else "用户拒绝本次调用，不得重试。",
        )


draft_tool = ConfirmingFunctionTool(
    create_refund_draft,
    is_read_only=False,
    is_concurrency_safe=False,
)
```

完整脚本还会展示工具名、影响及目录，并在询问前和实际写入前校验参数：订单号必须为 `DEMO-` 加 1 到 12 位数字，理由非空且不超过 200 个字符。工具不能接收文件路径，订单号和理由不参与路径拼接；只有获批并通过校验后才创建输出目录，使用随机文件名和 `x` 模式创建新文件。

在本项目的 AgentScope 2.0.10 中：

- `FunctionTool(permission=...)` 接收固定的 `PermissionDecision`，不是回调。这里通过继承并重写 `check_permissions` 实现交互，保持 `await agent.reply(...)` 的调用方式。
- 框架先解析、按 schema 校验参数，再检查权限；`ALLOW` 才执行函数，`DENY` 不执行，并将拒绝结果交回模型。`asyncio.to_thread` 让等待终端输入不占住事件循环，但仍会等待人输入。
- **必须使用 `is_read_only=False`**：默认权限模式会自动放行被声明为只读的工具，可能不进入自定义确认方法。这个标记是开发者声明，不是沙箱，也不会检查函数是否真的只读。
- 本例每次只批准当前调用，不添加“始终允许”的规则。新调用即使参数相同也要再次询问，同一次模型响应中的多个调用也分别确认。成功后若再次批准另一个调用，会再创建一份草稿，不保证每轮最多一份。
- 提示词要求拒绝后不重试、成功后停止，但模型仍可能再提议；不要因为它换了说法就忽略参数检查。`ReActConfig(max_iters=4)` 是循环护栏，不是工具调用次数、模型请求次数或费用上限。
- 原生 `ASK` 是等待宿主处理确认事件、再恢复的另一条路径，不会自动在终端调用 `input()`；本课在权限方法中读取人工决定后返回 `ALLOW/DENY`，不展开暂停与恢复协议。

权限边界在 **Agent 执行工具的流程** 中；直接运行 `create_refund_draft(...)` 或绕过 Agent 调用工具箱，不会自动触发这里的确认。这是单用户终端教学示例，不是生产级审批、幂等退款或文件系统隔离。不要把它换成真实付款/退款函数后直接投入使用。

真实运行会将任务、订单号、理由及工具结果中的本地路径发送给配置的模型服务；仅使用虚构数据，HTTP 连接会明文传输。草稿 JSON 本身不加密，`sessions/` 已被忽略但仍留在本机。

验证范围：语法与离线自检通过；真实 Agent 执行链搭配模拟模型响应验证了批准创建临时草稿、拒绝/空输入/非明确批准/EOF 不创建目录或文件、执行和拒绝结果按原调用 ID 回传、相同参数的新调用及同批两次调用分别确认、非法参数在询问前被拒绝、缺少必填字段被 schema 拦截。另验证了函数自身的参数校验、文件名碰撞不覆盖且不报告成功、初始化失败关闭客户端，以及确认中断不批准。所有草稿测试均限定在临时目录，未向真实模型发送请求，未验证真实模型是否正确申请及总结。

## 16. 第十一课：多 Agent 并行分析与汇总

`11_parallel_agents.py` 使用三个独立 Agent，演示 **没有相互依赖的任务可以并行，有依赖的任务必须等待**。第四课是“写草稿 → 审阅草稿”的串行流程；本课是两个分析同时进行，再将两份有效结果交给汇总者。不增加依赖，不使用工具、流式输出或会话持久化，不修改前十课或 `.env`。

默认任务是为虚构的 Python 报表助手设计最小可用原型（MVP）：上传 CSV、按日期筛选、查看销售总额、导出汇总 CSV，一名开发者在两周内完成，仅使用虚构数据，不连接真实系统。三个角色分别是：

- `FeatureAnalyst`：给出最小功能方案及实现顺序。
- `RiskAnalyst`：分析风险及对应验收方法，不需要读取功能分析员的结果。
- `Summarizer`：等待前两份有效结果，再结合原始需求汇总计划。

先做离线检查（不读取密钥、不创建模型客户端或 Agent、不写文件）：

```bash
.venv/Scripts/python.exe 11_parallel_agents.py --check
```

它只确认脚本能加载并展示角色定义和流程，不验证 Agent 初始化、服务兼容性或真实并发。

运行完整示例（向配置的模型服务发送请求，可能产生费用）：

```bash
.venv/Scripts/python.exe 11_parallel_agents.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\11_parallel_agents.py
```

也可以更换任务；两个分析员和汇总者都会使用这份新需求：

```bash
.venv/Scripts/python.exe 11_parallel_agents.py "为虚构的个人记账工具设计两周原型，仅手动录入收支并按月汇总，不连接银行。"
```

运行时观察：

1. 两个分析员各自出现 `[开始]`，然后各自出现 `[完成]`；完成顺序可能不同。
2. `Summarizer` 的 `[开始]` 必须在两个分析员都完成之后。
3. 在本例普通无工具的成功问答中，历史数量预期从 `0、0、0` 变为 `2、2、0`，汇总完成后再变为 `2、2、2`。数量只是观察点，状态独立由不同 Agent 实例各自创建默认 `state` 实现，不是靠数量相同证明。
4. 汇总方案应同时涵盖最小功能与风险验收，并保留“一人、两周、虚构数据”等原始限制。文字流畅不代表分析已验证。

核心代码是：

```python
results = await asyncio.gather(
    run_branch(agents["FeatureAnalyst"], task),
    run_branch(agents["RiskAnalyst"], task),
    return_exceptions=True,
)

failures = [result for result in results if isinstance(result, BaseException)]
if failures:
    # 完整脚本会记录停止原因并抛出异常，不调用汇总者。
    raise failures[0]

feature_text, risk_text = results
# 显式拼接：原始需求 + 功能分析 + 风险分析。
summary = await run_branch(agents["Summarizer"], summary_task)
```

这里 `run_branch` 会调用一次 `await agent.reply(UserMsg(...))`，检查回复是否正常完成、文字是否非空，然后返回文本。它不会把异常字符串或不完整回复当成成功材料。`return_exceptions=True` 表示等待所有分支并将失败放入结果列表，**不代表忽略错误或全部成功**；任一分析失败，本课等两个分支收尾后跳过汇总。

对比下面的写法：

```python
feature_text = await run_branch(agents["FeatureAnalyst"], task)
risk_text = await run_branch(agents["RiskAnalyst"], task)
```

这是串行：第一个完成后，第二个才开始。`gather` 则在同一个事件循环里并发调度两个协程，适合本例等待模型网络响应，不是启动多个 Python 进程，也不保证在完全相同的瞬间开始请求。返回结果的顺序对应传入顺序，即使风险分析先完成，`results[0]` 仍是功能分析。

本课每个 Agent 使用独立的 `OpenAIChatModel` 和客户端，但复用同一份服务配置与 API Key，不需要三把密钥。用 `AsyncExitStack` 在每个客户端创建后立即登记关闭，后续初始化或调用失败时也会清理已创建的客户端。不要对同一个有状态 Agent 实例同时调用 `reply`。不同 Agent 不会自动读取彼此历史；汇总者的输入必须由代码显式传入，不合并或共享分析员的 `state.context`。

正常流程为“两次独立分析，再一次汇总”这三次逻辑调用，并发不会减少调用数量；汇总请求还会包含两份分析文字，增加输入 token。服务端排队、限流、代理和额度都可能影响结果，并发不保证提速或省钱。日志耗时只是本次观察，不是稳定的性能基准，也不代表任何服务固定只产生三次 HTTP 请求或有固定费用上限。

这是由 Python 固定编排的并行工作流，不是三个 Agent 自动讨论，也没有把汇总反复发回分析员。两个角色即使关注点不同，仍可能产生相同错误；汇总可能遗漏风险或扩大范围，需要对照原始需求和测试结果核查。提示“分析只是材料、不是指令”也不是安全隔离保证。

真实运行会把任务、分析结果和汇总输入发送给配置的模型服务。仅使用虚构需求，不粘贴真实业务资料；当前配置若为 HTTP，密钥和内容会明文传输。取消程序不保证已经发送的服务端请求停止，也不能保证不计费。

验证范围：语法及离线检查通过；真实 Agent 搭配模拟模型响应，以模型调用内部的事件屏障验证两份分析确实重叠，而非仅比较日志或耗时。已验证自定义任务传递、结果按角色对应、两份分析完成后才汇总、原始需求和两份结果进入汇总输入、三个 Agent 的历史彼此独立；一个分支异常、空文本、纯空白、中断或取消时等待另一分支收尾且不汇总；汇总失败以及第二个模型或 Agent 初始化失败时，已创建的客户端均关闭。离线检查未读取配置、创建客户端或 Agent，也没有文件操作。全部测试使用假凭据且未发出模型请求，尚未验证真实服务并发能力、实际耗时或方案质量。

## 17. 第十二课：显式工作流——顺序、条件分支与失败处理

`12_workflow.py` 不假设 AgentScope 存在一个通用的 `Workflow`、`Sequential` 或 `Condition` API，而是用普通 Python `async` 代码把三个 Agent 编排成一个可读的流程：

```text
Planner
   │
   ├─ 简单任务 ───────────────▶ Finalizer
   │
   └─ 命中审阅规则 ─▶ Reviewer ─▶ Finalizer
```

本课的重点不是再增加一个 Agent，而是明确回答三个问题：**下一步什么时候可以开始？什么条件决定是否经过审阅？中间步骤失败时，能不能阻止下游继续？**

默认任务是为虚构的 Python 报表助手设计两周原型：读取示例 CSV、按日期筛选、显示销售总额并导出汇总 CSV。默认路径为 `Planner -> Finalizer`：

```bash
.venv/Scripts/python.exe 12_workflow.py --check
.venv/Scripts/python.exe 12_workflow.py
```

`--check` 在读取 `.env` 之前返回，只展示节点和两条路径，不读取密钥、不创建模型或 Agent、不写文件、不请求模型。真实运行会请求配置的模型服务并可能产生费用；当前配置若为 HTTP，任务和模型内容会明文传输。

也可以传入一个仅用于教学的虚构高影响任务，观察完整审阅路径：

```bash
.venv/Scripts/python.exe 12_workflow.py "为虚构报表设计支付记录删除功能，使用真实数据但不连接生产系统。"
```

这个任务会走 `Planner -> Reviewer -> Finalizer`，但代码不会执行支付、删除或任何外部操作。运行时应看到三个步骤按顺序开始和完成，最后的方案会明确提示它只是模型生成的文字。

### 1. 条件分支由代码决定

`needs_review(task, draft)` 位于 `12_workflow.py:66` 附近。它只检查**原始任务**：任务长度超过阈值，或包含“支付、付款、退款、删除、真实数据、真实系统、生产数据”等保守关键词，就进入 Reviewer。英文关键词也会先 `casefold()`。

Planner 草案中的“无需审阅”“这是安全的”等文字不会关闭审阅分支。模型不能通过自己的输出改变代码的路由规则。这里采用的是简单的短语子串匹配：中文没有可靠的单词边界，否定句（例如“不需要支付”）也可能触发审阅。这是有意的教学取舍，不是安全分类器；没命中关键词不等于任务安全，命中也不等于任务一定有风险。

### 2. 用 `await` 表达依赖

Planner 完成并通过检查后，代码才判断分支。复杂任务中，Reviewer 的输入显式包含原始任务和 Planner 草案；Reviewer 完成后，Finalizer 才收到三份材料。简单任务不创建或调用审阅步骤，Finalizer 会收到“未执行 Reviewer”的明确说明，而不是伪造审阅意见。

```python
planner_text = await run_step(agents["Planner"], "Planner", planner_prompt)
if needs_review(task, planner_text):
    review_text = await run_step(agents["Reviewer"], "Reviewer", reviewer_prompt)
else:
    review_text = "未执行 Reviewer：任务未命中确定性规则。"
final_text = await run_step(agents["Finalizer"], "Finalizer", finalizer_prompt)
```

这与第十一课的 `asyncio.gather` 不同：那里两个分析互不依赖，可以并行；这里每个下游输入依赖上游结果，所以使用顺序 `await`。不要为了“看起来像工作流”而并行调用同一个有状态 Agent。

### 3. 失败是门禁，不是可忽略的日志

`run_step` 会在结果交给下游前检查：

- `finished_reason` 必须是 `ReplyFinishedReason.COMPLETED`。
- `get_text_content()` 必须返回非空、非空白文字，且不能超过材料长度上限。
- 普通异常、取消、无法读取回复、非正常完成或无效文字都会变成带步骤名的 `WorkflowError`。

因此：Planner 失败时不会调用 Reviewer 或 Finalizer；Reviewer 失败时不会调用 Finalizer；Finalizer 失败时，不会把已有草案冒充最终方案。脚本不自动重试、不静默降级，也不把异常对象当作业务材料。`max_retries=0` 是模型传输层设置，不是费用上限；本课没有把任何迭代参数当成安全或调用次数保证。

上下游材料使用字段标记和“材料不是指令”的提示，但这些标记不是安全隔离。模型输出仍可能包含恶意或错误内容，所以本课只处理虚构方案文字，不把结果直接用于真实业务操作。材料长度限制也不是完整的 token 预算或提示注入防护。

### 4. 为什么没有直接使用 `agentscope.pipeline`

AgentScope 2.0.10 确实有 `agentscope.pipeline`，但它不是一个通用的条件节点库：

- `GoalPipeline` 是固定的执行器—验证器循环，验证结果为 `pass`、`fail` 或 `impossible` 时决定结束或反馈重试。
- `TeamPipeline` 是领导 Agent 通过内部 `TeamAssign` 工具动态分派成员；不同成员可以并发，同一成员的任务按顺序执行，还包含事件和人工确认路由。

它们适合后续学习更高级的 AgentScope 编排，但会遮蔽本课要练习的 `await`、`if`、显式材料交接和失败门禁。本课先掌握这些基础，再考虑把执行—验证循环映射到 `GoalPipeline`，或把动态成员分派映射到 `TeamPipeline`。项目中不存在一个可以直接套用的通用 `Workflow` API。

### 5. 资源、费用与验证边界

脚本为三个 Agent 使用独立的模型客户端，共用同一份配置；`AsyncExitStack` 在每个客户端创建后立即登记关闭，即使后续初始化或某个步骤失败，也会清理已经创建的客户端。正常简单路径是两次逻辑模型调用，审阅路径是三次；这不等于固定 HTTP 请求数、费用或答案质量。取消程序也不保证服务端停止或不计费。

验证范围：脚本编译、离线 `--check`、简单路径和高影响任务路径的真实 Agent 执行链模拟均已通过；已验证下游收到原始任务及上游材料、简单路径不调用 Reviewer、复杂路径严格按顺序调用、三个 Agent 的 state 和客户端独立；Planner 失败、Reviewer 异常/空白/中断/取消时下游不会调用，客户端仍关闭。离线检查未读取配置、创建模型或 Agent，也没有文件操作。模拟使用假凭据并拦截模型请求，未验证真实服务兼容性、模型内容质量、关键词规则的生产适用性或任何真实安全判断。

## 18. 第十三课：TeamPipeline 原生团队分派

第十二课的流程由 Python 代码固定写成 `Planner -> Reviewer -> Finalizer`。本课使用 AgentScope 2.0.10 自带的 `TeamPipeline`，让一个 `Leader` Agent 通过内部的 `TeamAssign` 工具选择成员并分派子任务，再根据成员返回结果生成最终回答。

```text
用户任务
    ↓
Leader ── TeamAssign(member, prompt) ──▶ FeatureAnalyst
     └── TeamAssign(member, prompt) ───▶ RiskAnalyst
    ↑                                      │
    └────────── 成员结果回到 Leader ────────┘
```

成员只看到 Leader 放进分派 `prompt` 的内容，不会自动读取 Leader 或其他成员的完整历史。成员的回答不是直接展示给用户的最终答案，而是由管线包装成 `TeamAssign` 工具结果交回 Leader。成员之间也不会自动互相对话。

### 1. 先做离线检查

```bash
.venv/Scripts/python.exe 13_team_pipeline.py --check
```

这一步只确认 `TeamPipeline`、`TeamMember` 可以导入，并展示两个成员的职责。它不读取 `.env`、不创建模型或 Agent、不写文件、不请求模型，也不验证你的服务是否支持工具调用。

### 2. 运行真实团队示例

```bash
.venv/Scripts/python.exe 13_team_pipeline.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\13_team_pipeline.py
```

默认任务使用虚构的 Python 报表助手需求。服务必须支持 OpenAI 兼容的 tools / function calling；一次 Leader 回复可能包括多次模型请求和多个成员任务，可能产生费用。当前配置若为 HTTP，API Key、任务及成员结果会明文传输。

自定义任务，例如：

```bash
.venv/Scripts/python.exe 13_team_pipeline.py "为虚构的个人记账工具设计两周原型，仅手动录入收支并按月汇总，不连接银行。"
```

### 3. 观察真正发生了什么

脚本会显示：

- `[开始] Leader`、成员的开始事件和完成事件。
- `[分派请求] TeamAssign`：Leader 实际提交的成员名和任务参数。
- `[分派返回] TeamAssign(...)`：成员结果已作为工具结果回到 Leader。
- `--- Leader 最终回答 ---`：仅在 Leader 的 `ReplyEndEvent.finished_reason` 为 `COMPLETED` 且收到了非空文字后打印。

如果你输入一个问候，Leader 可能直接回答而不调用成员；脚本会明确显示“未发生成功的成员分派”，不会把直接回答冒充团队协作验证。提示词鼓励分派也不是硬保证，真实模型可能选择不同的成员、只分派一个成员、重复分派，或不分派。

### 4. `TeamPipeline` 的核心接口

```python
from agentscope.pipeline import TeamMember, TeamPipeline

team = TeamPipeline(
    leader,
    members=[
        TeamMember(agent=feature_agent, description="负责最小功能方案"),
        TeamMember(agent=risk_agent, description="负责风险与验收"),
    ],
    reset_members=True,
)

async for event in team.reply_stream(UserMsg(name="user", content=task)):
    # 消费 AgentEvent；TeamPipeline 不直接提供普通 reply() 结果。
    ...
```

`TeamPipeline` 第一次运行时会自动把内部 `TeamAssign` 工具加入 Leader 的 toolkit。工具参数包含成员名和完整 `prompt`。同一轮中分派给不同成员的任务可以并行；发给同一成员的多个任务按调用顺序执行。是否形成同一轮的多个调用由模型决定，不是程序承诺。

本版本有一个重要接口细节：`TeamPipeline.reply_stream()` 只产生事件，不接受 `yield_final_msg=True`，`ReplyEndEvent` 也没有 `message` 字段。因此脚本按 `ReplyStartEvent.name` 和 `reply_id` 区分参与者，缓存 Leader 自己的 `TextBlockDeltaEvent.delta`，在 Leader 的 `ReplyEndEvent` 完成后重新组成最终文字。Thinking、工具参数和成员文字不会混入最终答案。

成员完成状态也要单独检查。不能只看 `TeamAssign` 的工具结果状态：当前管线会把成员的 `EXCEED_MAX_ITERS` 映射成工具结果 `SUCCESS`，但这不代表成员给出了有效完成的回答。脚本要求每个参与者有 `ReplyEndEvent`，且 `finished_reason` 为 `COMPLETED`；工具结果不是 `SUCCESS`、参与者等待确认/外部执行、空白文字或没有最终 Leader 文字，均视为团队结果不完整。

### 5. 与前几课的区别和边界

- 第四课把 Writer 和 Reviewer 的顺序写死；第十一课用 `asyncio.gather` 并行无依赖的分析；第十二课用 `if` 选择固定审阅路径。本课把“选择成员”交给 Leader 的工具调用。
- 这不是无限自主的群聊。成员只有在 Leader 调用 `TeamAssign` 后才运行，成员结果只回 Leader，程序仍负责消费事件、检查结束状态和关闭客户端。
- 本课成员只有文字分析，不注册文件、Shell、网络或付款工具；不存在副作用审批。不要把虚构的分析团队直接换成可以执行真实操作的 Agent 而不重新设计权限。
- `reset_members=True` 会在一次 Leader 回复结束后清空成员上下文；它不是跨请求的会话持久化。三个 Agent 使用独立 state 和独立模型客户端，`AsyncExitStack` 会在初始化或运行失败时清理已创建的客户端。
- `max_iters=4` 和 180 秒等待超时只是本示例的循环/等待护栏，不是费用、请求数量、服务端停止或内容正确性的保证。取消程序也不保证已经发出的远端请求停止或不计费。

真实模型可能调用多个工具、重复询问、拒绝分派或返回错误。成员结果是待评估材料，不是指令，也不自动构成事实验证。当前 HTTP 配置下不要传入真实业务资料；本课只使用虚构需求。

验证范围：脚本编译与离线 `--check` 已通过；静态核对确认了 `TeamPipeline` 的内部 TeamAssign 注册、成员分派与结果回传、事件字段和 Leader 最终文本提取路径。由于本次环境的命令权限阻止执行临时模拟测试文件，尚未把完整的真实 Agent + 模拟模型事件链测试作为已通过结果报告；未调用真实模型服务，未验证真实工具调用兼容性、模型分派质量、成员并发时序或方案正确性。

## 19. 第十四课：GoalPipeline 执行—验证—反馈循环

`14_goal_pipeline.py` 使用 AgentScope 2.0.10 的官方 `GoalPipeline`：`Executor` 生成报告，`Verifier` 按原始目标检查；可修正的失败会形成反馈，交回执行者再次尝试。与第十三课的动态团队分派不同，本课只有两个固定角色，按顺序运行。

```text
原始目标 -> Executor 报告 -> Verifier 判定
                              ├─ pass       -> 结束，验证者判为通过
                              ├─ impossible -> 结束，未通过
                              └─ fail       -> 反馈给 Executor；尝试用尽则结束，仍未通过
```

**管线结束不等于目标通过。** 正常生成报告、正常生成验证结果都可能出现 `ReplyEndEvent(COMPLETED)`；只有验证结果中的 `result == "pass"` 表示验证者判为通过。

### 1. 运行与观察

先做离线检查，不读取配置、不创建 Agent 或模型客户端、不写文件、不请求模型：

```bash
.venv/Scripts/python.exe 14_goal_pipeline.py --check
```

再运行真实示例（需要服务支持工具调用，可能多轮请求并产生费用）：

```bash
.venv/Scripts/python.exe 14_goal_pipeline.py
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\14_goal_pipeline.py
```

默认目标是为虚构的 CSV 报表助手生成两周 MVP 方案，包含最小功能、不做项，以及日期边界、金额计算、异常 CSV 的验收条件。本课的“执行”只是生成内存中的方案文字，不创建文件、不处理真实 CSV、不连接业务系统，也不实际测试代码。

终端应出现 `[报告 1]` 和 `[验证 1]`。如果判定 `fail`，管线会把具体反馈交回 Executor，随后可能出现第二份报告和第二次验证。默认最多允许两轮有效尝试；真实模型可以第一轮就通过，不必为了演示循环而故意犯错。

也可以更换目标：

```bash
.venv/Scripts/python.exe 14_goal_pipeline.py "为虚构记账工具写两周方案，包含手动录入、按月汇总、不做项和三条可检查的验收条件。只生成文字，不连接银行。"
```

### 2. 核心 API 与结构化字段

```python
from agentscope.pipeline import GoalPipeline

pipeline = GoalPipeline(
    executor=executor,
    verifier=verifier,
    verifier_reset_context=True,
    max_iters=2,
)

async for event in pipeline.reply_stream(UserMsg(name="user", content=task)):
    # 观察报告、验证结果与完成/等待事件。
    ...
```

`GoalPipeline` 内部为两个 Agent 指定不同的结构化输出：

- Executor：`{"report": "完整文字报告"}`。
- Verifier：`{"result": "pass 或 fail 或 impossible", "message": "理由或修改建议"}`。

报告必须包含实际要检查的方案，不要只写“已完成”，也不要编造文件路径。Verifier 看到原始目标和本轮报告；`fail` 时，它的 `message` 会作为反馈进入 Executor 的下一轮输入。Executor 保留自己的上下文，因此能结合原始目标和反馈修改；`verifier_reset_context=True` 则在失败后清空验证者的对话与摘要，下轮重新根据目标和新报告判断，不是清空所有状态或持久化会话。

这不是只在提示词里写“返回 JSON”。与第五课相同，当前 Agent 接口使用内置 `GenerateStructuredOutput` 工具提交并校验字段，因此普通文本问答成功不代表你的服务兼容这条路径。内置 schema 只约束报告、判定和理由的字段类型，不保证内容真实；本课另外拒绝空白报告、过长报告和空白判定说明。

### 3. 三种判定和两层迭代

- `pass`：验证者认为文字报告满足目标，结束。
- `fail`：目前未满足，但可以修正；尚有尝试预算时，把反馈交回执行者。
- `impossible`：验证者认为目标矛盾或本课能力无法满足，停止，不再尝试。这是模型判断，不是客观不可行证明。

`GoalPipeline(max_iters=2)` 与 `Agent` 的 `ReActConfig(max_iters=3)` 不是同一层。前者在收到有效 `fail` 时累计目标尝试；后者限制单次 Agent 回复的推理/工具循环。一次目标尝试内部仍可能多次请求模型来生成或修正结构化输出。

当前安装版本还有一个限制：`GoalPipeline.max_retries` 虽在构造接口中存在，但实现仅保存它，实际没有据此限制缺失结构化结果时的重启。本课不依赖这个参数，在非正常完成、无结构化结果或无效材料的结束事件处立即停止，并使用 180 秒总等待超时作额外护栏。字段格式错误可能先由单次 Agent 回复自行修正；最终仍无效时，课程代码不允许原生管线反复重启。所有这些限制都不是 HTTP 请求数、token、费用或内容正确性保证。

### 4. 不要照搬 TeamPipeline 的最终文本提取

`GoalPipeline` 使用 `reply_stream`，不能调用不存在的普通 `pipeline.reply(...)`。执行者的最终 `Msg` 可能向外产出，但验证者正常完成的 `Msg` 会被管线内部消费，不能等待它来取得最终判定，也不能从普通文字猜测 pass。

脚本通过 `ReplyStartEvent.name/reply_id` 找到对应 Agent，在 `ReplyEndEvent` 到达时立即复制其 `state.reply_context.structured_output`，检查事件与当前状态对应、结束原因正常、字段有效，再记录报告或判定。下一轮会重置回复状态，因此及时快照很重要。本课不导入下划线开头的私有 schema 类，也不把 `ReplyEndEvent` 当作携带最终消息的对象。

人工确认或外部执行请求表示流程停驻，不是成功。本课只提供文字分析和内置结构化工具，不处理这类请求的恢复；若出现 `RequireUserConfirmEvent` 或 `RequireExternalExecutionEvent`，明确停止并报告尚未完成。正式的恢复流程需要在同一个管线实例上提交相应确认或执行结果事件，不能用普通“yes”消息代替。

### 5. 验证与资源边界

Executor 和 Verifier 使用独立 Agent/state/模型客户端，共用现有配置；每个客户端创建后立即用 `AsyncExitStack` 登记关闭，初始化或执行失败也会清理。取消/超时保留取消语义，不把中断时生成的部分报告冒充成功；远端已经发出的请求仍可能继续处理或计费。

**结构化结果有效、Verifier 判 pass，都不代表真实功能已实现、测试已通过或安全审批完成。** 两个角色使用同一模型服务时也可能重复相同错误。报告和反馈是待评估材料，提示词不是安全隔离。真实运行会把目标、报告和反馈发送给配置的服务；HTTP 会明文传输密钥与内容，只使用虚构数据。

验证范围：脚本加载和离线 `--check` 通过；真实 Agent + 原生 GoalPipeline 搭配模拟模型响应验证了首轮 pass、fail 后反馈进入第二轮再 pass、impossible 停止、两轮 fail 仍未通过、报告与验证者状态交接、验证者失败后对话重置。另覆盖空白/过长报告、空白说明、非法判定枚举被框架拒绝后修正、只有普通文字而无结构化结果时停止、两角色异常/取消、真实注册的待确认测试工具、超时，以及第二个模型或 Agent 初始化失败后的客户端关闭。离线检查和空白目标拒绝不读取配置、不创建 Agent/客户端、不进行文件操作。全部测试使用假凭据，模型调用均被拦截，未发出 HTTP 请求；未验证真实服务兼容性或报告质量。超时测试曾发现取消结束事件遮蔽 TimeoutError，修正后全套回归通过。

## 20. 第十五课：Agent 评测与回归测试

`15_eval.py` 用四个固定问题评测一个教学资料问答 Agent，直接复用 `knowledge_search.py` 和 `knowledge/lesson08/` 的虚构资料。它不调用另一个模型给答案打分，而是用 Python 检查**完成状态、实际检索行为、关键文字和引用来源**。这不是 AgentScope 的内置评测平台，也没有增加依赖或修改第九课。

### 1. 默认离线，真实评测必须显式开启

以下两条命令等价，均只检查本地资料与评分器：

```bash
.venv/Scripts/python.exe 15_eval.py
.venv/Scripts/python.exe 15_eval.py --check
```

应看到“4 个正例、11 个反例和资料锚点检查”通过。反例包括：答案正确但没有搜索、搜索无命中、150 次冒充 50 次、错误时间单位、缺失引用、伪造来源、未正常完成、空答案和问候时乱搜。

**这是评分器自检，不是模型通过率。** 自检不读取 `.env`、不创建 Agent 或模型客户端、不请求模型，也不写评测文件。它会读取教学 Markdown，并检查关键事实是否仍与固定测试答案一致；资料发生变化时应同步检查题目和预期答案，不能盲目维持旧评分。

只有以下命令会运行四个真实用例，可能多轮请求并产生费用：

```bash
.venv/Scripts/python.exe 15_eval.py --live
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\15_eval.py --live
```

服务须支持 OpenAI 兼容的工具调用。四个用例不等于四次 HTTP 请求；每个问题可能先请求工具、取得证据后再次回答，也可能改写查询。当前配置若是 HTTP，密钥、问题和命中资料会明文传输。本课只使用虚构资料，不要随意换成私有文件。

### 2. 固定测试集

| 用例 | 行为要求 | 主要文字与引用要求 |
| --- | --- | --- |
| 会员每天导出额度 | 真实执行检索且有命中 | 每天或每日、50 次，引用 `[export.md#导出额度]` |
| 普通退款申请期限 | 真实执行检索且有命中 | 支付成功后、7 个自然日，引用 `[refund.md#申请期限]` |
| 是否支持 JSON 导出 | 真实执行检索且有命中 | 承认资料未说明，不能直接编造支持或不支持 |
| 你好 | 不调用检索 | 正常非空回答，不带资料引用 |

模型只收到问题、角色提示和工具说明，不会收到评分器中的参考答案。每个用例创建新的 Agent、工具闭包和调用记录，避免前一个问题的答案或搜索记录污染下一个用例。用例按顺序执行，共用一个模型客户端，结束或失败时在 `finally` 中关闭。

### 3. 记录的是函数执行，不是模型声称

评测版搜索工具只有 `query: str` 参数，不能指定文件路径。它调用共用检索器并成功生成返回结果后，记录查询与命中片段：

```python
hits = retrieve(query, chunks, top_k=3)
response = json.dumps({"query": query, "hits": hits}, ensure_ascii=False)
calls.append(SearchCall(query, [dict(hit) for hit in hits]))
return response
```

模型说“我查了资料”、在回答中写了一个来源，甚至提出了尚未执行的工具调用，都不等于实际执行过搜索。检索函数报错时不会登记成功记录。记录属于当前用例，不会自动持久化到文件。

### 4. 四类检查分别显示

`grade(case, observation)` 是纯 Python 函数，输入为用例与观测记录，输出 `PASS` 或 `FAIL` 及各项检查结果：

1. **完成状态**：回复必须为 `COMPLETED`，且文字去空白后非空；迭代超限不能当作成功。
2. **行为**：产品问题必须有真实执行和非空命中；问候不应搜索。
3. **关键文字**：用 NFKC 与空白规范化后执行固定正则检查，例如“50 次”“7 个自然日”；未知格式题还检查不确定表述及部分禁止措辞。
4. **来源**：必需的引用必须出现在答案里，且属于当前用例真正返回的片段；所有匹配 `[文件#标题]` 语法的引用都要检查，不能夹带一个正确引用后继续伪造其他引用。

这里只解析约定的方括号来源格式。其他引用写法不能自动当成有效来源，也不保证都被识别成伪造引用。

通过关键字检查**不代表完整语义正确**：回答可能同时出现正确数字和相反结论，也可能用规则未覆盖的措辞编造。来源出现在检索结果中，也不证明这段来源支持回答中的每一句话。未知格式题的禁止措辞检查同样是有限启发式，不是完整的“是否在编造”判断。

### 5. PASS、FAIL 与 ERROR

- `PASS`：本轮这个用例通过全部规则。
- `FAIL`：取得了回答，但至少一个行为、内容、引用或完成状态检查未通过。
- `ERROR`：初始化、请求或处理过程中出现异常，或等待超时，未完成正常评分。

一个用例的普通错误不会让它从统计中消失，而是记录 ERROR 后继续其他用例。汇总始终以四个问题为分母，例如 `规则通过 3/4；FAIL=0，ERROR=1`。任一 FAIL 或 ERROR 都使真实评测退出码为 1，全通过为 0，便于在修改提示词、工具或模型后做回归比较。认证或服务错误也按用例记录，因此同一配置错误可能让四例都成为 ERROR。

每例设置 90 秒等待超时，Agent 设有迭代护栏，但两者都不是费用上限。`Ctrl+C` 取消会停止后续请求，不伪造完整评测汇总；远端已经发出的请求不保证停止或不计费。

### 6. 如何解释评测结果

第十四课是“验证者模型认为目标达成了吗”；本课是“固定、可重跑的规则有没有通过”。二者都不能替代真实业务验收。四个教学问题不是有代表性的完整测试集，不能据此宣称 Agent 的总体准确率。每轮只运行一次也不能反映模型的不确定性。

实际回归时先固定资料、用例和规则，再改变提示词或模型，对比各项失败原因，而不是只追求一个总分。若新增反例，要检查评分器本身是否能拒绝它；正常的同义表达被误判时也应修正规则。当前评测的是本课独立构造的 Agent，并不是对前十四课所有功能的回归。

验证范围：默认与 `--check` 的四正例、十一反例及知识锚点检查通过；真实 Agent + 模拟模型响应验证四例工具执行、调用 ID 对应、独立 state、搜索记录隔离、全通过退出码 0，以及未搜索、伪引用、错误数字、空白回复、无命中、问候检索、迭代超限均记 FAIL。异常和超时记 ERROR，继续其他问题且固定四例分母；取消或中断不继续后续请求，模型客户端均关闭。另验证检索异常不登记成功记录、教学资料事实变更能被自检发现，以及离线模式不读取配置、不创建客户端或 Agent、不写文件。所有模型响应均由测试中间件拦截，使用假凭据，未发送真实 HTTP 请求；尚未运行 `--live`，没有真实模型通过率或服务兼容性结论。

## 21. 第十六课：Agent 可观测性——事件、耗时与用量

`16_observability.py` 沿用虚构产品资料问答，将“最后答得怎样”与“中间怎样运行”分开观察。本课只在终端打印本地运行元数据，不创建日志文件、不接入外部追踪平台、不安装新依赖，不修改前十五课。

### 1. 默认离线，真实运行需显式开启

以下两条命令等价，仅用合成事件检查观测代码：

```bash
.venv/Scripts/python.exe 16_observability.py
.venv/Scripts/python.exe 16_observability.py --check
```

应看到模型区间配对、未闭合、工具请求与实际执行区分，以及未知/零/部分用量检查通过。此模式不读取 `.env` 或知识资料、不创建 Agent 或模型客户端、不写文件、不请求模型。合成事件不是一次实际问答，也不是服务性能或 token 消耗数据。

真实运行一个资料问题：

```bash
.venv/Scripts/python.exe 16_observability.py --live
```

再用问候作对比：

```bash
.venv/Scripts/python.exe 16_observability.py --live "你好"
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\16_observability.py --live
```

真实运行会向配置的模型服务发送问题及命中资料，可能多轮请求并产生费用；当前配置若为 HTTP，API Key 和内容会明文传输。只使用虚构问题和教学 Markdown，不自动尝试其他接口。

### 2. 四个层次不能混淆

| 层次 | 本课如何观察 | 能说明什么 |
| --- | --- | --- |
| 一次 Agent 回复 | `ReplyStartEvent` / `ReplyEndEvent` | 整个回复的生命周期与完成状态 |
| 逻辑模型调用 | `ModelCallStartEvent` / `ModelCallEndEvent` | Agent 发起的一段推理调用，不是逐次 HTTP 尝试 |
| 工具请求与结果 | `ToolCallStartEvent`、`ToolResultStartEvent` / `ToolResultEndEvent` | 模型提出工具调用，以及框架产生的结果状态 |
| Python 函数实际执行 | 检索闭包入口及成功/异常计数 | 本地搜索函数是否真正进入、完成或抛错 |

普通检索问答可能出现“两次逻辑模型调用、一次工具请求、一次搜索函数执行”：先由模型请求搜索，Python 执行并返回资料，再由模型组织回答。但这只是常见路径，不是程序或模型的固定承诺；问候可以直接回答，也可能出现多次搜索、失败或未完成。

`ToolResultStartEvent` 不等于函数进入，因为拒绝、参数校验错误或取消也可能产生工具结果生命周期。即使最终回复为 `COMPLETED`，之前的工具结果也可能是 `ERROR` 或 `DENIED`。正常完成只说明回复结束，不能证明工具成功或事实正确。

### 3. 时间配对与未闭合区间

脚本消费普通 Agent 的事件流，并单独保留最终 `Msg`：

```python
async for item in agent.reply_stream(message, yield_final_msg=True):
    if isinstance(item, Msg):
        final_reply = item
    else:
        trace.observe(item)
```

`Trace` 使用单调时钟 `perf_counter()`，显示相对时间与每个已配对模型区间的时长。当前版本的模型 Start/End 只有 `reply_id`，没有独立的模型调用 ID，因此本例明确限于**单 Agent、顺序模型调用**，按事件顺序配对，不能直接拿去追踪多个并发 Agent。

模型 Start 发生在准备输入和调用模型之前；区间可以包含格式化、中间件、内部重试等时间，不是纯网络延迟。异常可能只产生 Start 而没有 End，此时摘要显示“未闭合”，不在 `finally` 中伪造正常完成或估算成功耗时。工具开始与结束使用 `(reply_id, tool_call_id)` 关联，保留无结果请求和未闭合结果数量。

搜索函数另有本地执行耗时，包含检索、序列化及本例的少量观测开销，不是整个工具事件区间。已观测总时长从 `Trace` 创建后开始，包含 Agent 构造和终端输出等开销，不含之前的资料/配置读取、模型客户端构造，也不是关闭客户端后的全进程耗时。模型区间和工具执行都包含在整体运行中，不可把所有嵌套耗时相加后再次当成总耗时。

### 4. 缺失 usage 不能记成零

当前 AgentScope 会在 `response.usage is None` 时，将 `ModelCallEndEvent` 的 token 字段填为 0。因此只看事件里的 0，无法区分“没有提供用量”和“真实返回零”。

本课增加被动模型中间件，读取响应后原样返回：

```python
response = await next_handler()
if isinstance(response, ChatResponse):
    trace.observe_response(response)
return response
```

本例固定 `stream=False`，正常返回一个 `ChatResponse`。若下游意外返回异步生成器，代码会原样交还并说明未观测其用量，不为了统计偷偷消费流。使用 `reply_stream` 消费 Agent 事件，不代表模型本身就开启了流式响应。

摘要显示模型响应数、缺少 usage 的响应数，以及每个字段的覆盖数量与已观测部分。比如两份响应中只有一份提供输入 token，就只能报告“已观测部分 100，覆盖 1/2”，不能称为整次问答总消耗。全部缺失显示“未知”；明确的零值才保留为 0。模型调用抛错没有返回响应时，另记中间件边界异常，不能凭空补出用量。

字段采用当前 `ChatUsage` 名称：`input_tokens`、`output_tokens`、`cache_input_tokens`、`cache_creation_input_tokens`。缓存字段可能由适配器默认填零，所以即使字段存在，也不证明服务提供了完整缓存计费信息。本课不自行把缓存数字与输入/输出相加，不计算价格，不推断账单。

一组模型事件可以包含 SDK 重试、Agent 内部尝试或 fallback；`on_model_call` 中间件也不是传输层 HTTP 抓包。即使本例关闭了配置中的重试，这些计数也不能充当真实 HTTP 请求数或服务端处理次数。真实账单仍应以服务方记录为准。

### 5. 只记录元数据不等于整个输出已脱敏

本例元数据不打印问题、工具参数、原始工具结果、思考块、请求头、凭证、完整异常或 `usage.metadata`，不输出完整消息/响应对象。工具名称由代码中的固定搜索函数提供。最终回答在独立区域展示，并标注“可能包含资料，不是脱敏日志”。分享截图或终端输出前，仍要检查回答和其他内容。

第三方 SDK、框架及用户自行添加的工具日志不受本例输出过滤控制；这不是生产级自动脱敏或安全审计系统。没有外发追踪数据，不代表真实模型请求没有向服务商传输资料。

### 6. 失败、取消和验证范围

真实分支使用 `try/finally`，正常、异常、超时或取消时都尽力展示已观测的部分轨迹，并关闭模型客户端。总等待 90 秒与迭代设置只是护栏，不是费用上限；已发出的远端请求不保证停止或不计费。没有完整正常回复时不会展示部分内容为最终答案；初始化失败也可能只有零条事件，这不是“零成本”的证明。

验证范围：默认与 `--check` 合成事件自检通过；真实 Agent + 内层模拟模型中间件验证了两次模型调用与一次本地搜索、问候不搜、工具成功/异常/拒绝的独立计数、模型区间配对及异常未闭合、usage 完全缺失/部分缺失/真实零值、模型异常/中断/取消/超时，以及 Agent 初始化失败后的客户端关闭。输出捕获检查确认本例元数据未泄露问题、查询参数、原始工具结果、思考、凭证、usage metadata、异常原文或最终回答；最终回答只在独立区域展示。全部模型调用被测试拦截，使用假凭据，未发送 HTTP 请求；尚未运行真实 `--live`，没有真实性能、token 账单或模型质量结论。

## 22. 第十七课：可靠性护栏——有界重试、超时、取消和预算

`17_reliability.py` 在第十六课的可观测性基础上，给只读资料问答加上可检查的停止规则。它不重跑整段 Agent、不自动重试工具，也不新增依赖或修改前十六课。目标不是保证请求一定成功，而是避免失败后无限等待、无限重试或重复执行操作。

### 1. 默认离线故障注入

```bash
.venv/Scripts/python.exe 17_reliability.py
.venv/Scripts/python.exe 17_reliability.py --check
```

两条命令等价，使用内存中的固定故障序列驱动同一个重试中间件。自检覆盖临时错误后恢复、永久错误不重试、重试耗尽、跨调用预算、工具预算、`Retry-After` 和取消。不读取配置或知识资料、不创建真实 Agent/模型/HTTP 客户端、不写文件、不发送请求。这不是实际服务的可用性或成功率测试。

只有显式开启真实模式才会读取本地配置并请求模型，可能产生费用：

```bash
.venv/Scripts/python.exe 17_reliability.py --live
.venv/Scripts/python.exe 17_reliability.py --live "你好"
```

PowerShell 中运行：

```powershell
.\.venv\Scripts\python.exe .\17_reliability.py --live
```

默认问题是虚构产品的会员导出额度，工具仅检索 `knowledge/lesson08/` 的教学 Markdown，不接受文件路径或执行写操作。HTTP 配置会明文传输密钥、问题和命中资料；只使用虚构数据。

### 2. 重试只放在一层

一次问答可能有多个可以重试的层次：SDK 的 HTTP 请求、模型包装器、Agent 模型配置、业务工作流和工具函数。如果每一层都设置重试，实际调用可能相乘，而不是只多一次。

本例明确关闭 SDK、模型和 Agent 自带重试，也不配置 fallback：

```python
model = OpenAIChatModel(
    ...,
    stream=False,
    max_retries=0,
    client_kwargs={"timeout": 10.0, "max_retries": 0},
)
agent = Agent(
    ...,
    model_config=ModelConfig(max_retries=0, fallback_model=None),
    middlewares=[RetryModelCalls(budget)],
)
```

唯一自动重试点在 `RetryModelCalls.on_model_call` 的 `await next_handler()`。失败后只重新尝试当前模型调用，不重新执行整段 `Agent.reply`、不重置历史，也不重放已经完成的搜索。一个逻辑模型调用最多 **2 次总尝试，即首次调用加 1 次重试**，不是额外重试两次。

本课允许重试连接错误、模型请求超时，以及 HTTP 429、500、502、503、504。401、400、其他状态或不认识的异常直接传出。这个白名单是教学策略，不代表所有 500 都是暂时故障，也不代表超时一定没有到达服务端。失败后的新响应可能不同，重复请求也可能产生费用。

### 3. 退避与 Retry-After

首次临时失败后，本例默认等待 0.5 秒再试。若服务返回可解析的 `Retry-After`（秒数或 HTTP 日期），等待至少相应时长；不把服务要求的长等待截短后提前请求。等待超过本课 3 秒重试等待上限、字段不合法或预算已耗尽时，直接停止。

这是短小的单用户教学策略，不是高并发限流系统。生产环境可能需要持久队列、随机抖动、熔断以及服务特定策略；不能让多个进程按同一固定间隔持续冲击一个限流端点。退避本身也位于总等待超时内，取消和超时可以中断等待，不使用 `shield` 继续后台重试。

### 4. 两个共享预算，失败也计入

| 限制 | 本例数值 | 检查位置 |
| --- | --- | --- |
| 单个逻辑模型调用 | 最多 2 次总尝试 | 每次 `next_handler()` 之前 |
| 整次 Agent 运行 | 最多 5 次模型边界尝试 | 共享预算，跨逻辑调用不重置 |
| 只读检索 | 最多 2 次检索执行许可 | `retrieve()` 之前 |

预算是**预先检查和消耗**的：失败、不可重试错误和工具执行异常不会返还已经消耗的许可。没有第六次模型边界调用，也没有第三次真正进入检索器的执行。第三次搜索工具包装函数可能被框架调用，但会在预算检查处失败，不进入 `retrieve()`。

框架可能把工具异常变为 `ToolResultEndEvent(ERROR)`，并允许模型继续推理；本课在消费到非成功工具结果时主动停止，不让模型通过换参数继续重试工具。错误、拒绝或预算用尽都不是可以忽略的普通回答。

计数针对本例单进程、单 Agent 的调用边界，不是组织级配额、token 预算或账单上限；也不统计服务端内部处理、用户重新启动脚本的累计调用或其他进程。同步预算检查到扣减之间没有 `await`，只适用于本例的事件循环用法，不能当成跨线程/进程的原子额度系统。

### 5. 超时、取消与幂等性

本例有不同层次的护栏：SDK 请求超时 10 秒、整个 Agent 等待 30 秒、小的 ReAct 迭代限制，以及上述调用预算。总超时覆盖 Agent 运行中的异步模型调用、退避和工具流程，不含之前的资料读取、客户端构造或之后的资源关闭。SDK 的 timeout 是客户端网络超时配置，不保证单次操作严格占用不超过 10 秒；整段异步等待再由外层约束。

`asyncio.timeout` 是协作式取消，不会抢占正在阻塞事件循环的同步代码。本地检索器很小，但如果以后换成长时间同步操作，必须另外设计可取消异步接口、隔离进程或服务端超时；仅把任务放入线程也不能强制停止已经运行的线程。

`CancelledError` 不视为暂时错误，不自动重试。Agent 配置 `interruption_raise_cancelled_error=True`，确保取消继续向外传播；取消收尾可能先产生工具中断事件，消费者让清理继续，保留外层 `TimeoutError` 的语义。中途失败时不展示部分文字为完整回答，`finally` 报告已经消耗的预算并关闭客户端。

**取消、超时或连接失败都不证明远端没有执行或不会计费。** 本课只读搜索可以有限重试；如果工具改成发邮件、创建订单或退款，不能照搬此策略。此类操作需要幂等键、操作状态查询、事务或补偿机制，以及恰当的人工授权，而不是重新执行整段 Agent。当前代码没有这些业务保障。

### 6. 运行结果怎样解释

正常资料问答可能用两次模型边界尝试和一次搜索。首个模型请求暂时失败后恢复，则可能是三次尝试和一次搜索；第二个模型调用失败后恢复，也不应重新执行已经完成的搜索。问候可以不搜索。具体路径由模型和失败情况决定，不承诺固定调用数。

只打印尝试序号、受控停止原因及预算摘要，不打印问题、工具参数、思考或完整异常；最终回答独立展示，可能含资料，不能把整段终端输出当脱敏日志。第三方框架自己的日志不受本例过滤控制。

验证范围：默认和 `--check` 的内存故障注入通过；真实 Agent 配合内层模拟模型验证正常问答、连接错误/429 后恢复、已完成工具后的模型调用失败不重复执行搜索、401 不重试、持续临时错误两次即停、过长 Retry-After 不提前重试、同批第三个工具请求不进入检索、跨逻辑调用最多五次模型边界尝试、工具异常后不继续模型、取消/中断、调用或退避时超时，以及 Agent 初始化失败后的客户端关闭。另验证退避期间直接取消不触发下一次尝试、SDK/模型/Agent 重试关闭且无 fallback、本例元数据不泄露请求或凭证。全部测试使用假凭据并拦截模型调用，没有真实 HTTP 请求；尚未运行真实 `--live`，没有真实可用性、故障恢复率或费用结论。
