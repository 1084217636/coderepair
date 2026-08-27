# 02 LLM、Agent、Tool、LangGraph 与 DeerFlow

## 问题 1：LLM、Token、Prompt 和 Context 分别是什么

### 面试官问

你先解释一下大模型请求的基本组成，以及 Token 为什么会影响系统设计。

### 30 秒回答

LLM 根据已有 Token 序列预测下一个 Token。Prompt 是本次送给模型的输入，通常包含 system 指令、历史消息、工具描述和当前问题；Context 是模型当前能看到的完整信息集合。Token 是模型处理文本的基本单位，不等于一个汉字或一个单词。上下文窗口、费用和延迟都按 Token 受限，所以系统不能把整个仓库和全部对话无脑塞给模型，需要检索、截断、摘要和预算控制。

### 详细回答

模型接收的是消息序列，不是直接接收"业务对象"。系统需要把业务状态转换成模型能理解的消息。常见角色包括 system、user、assistant 和 tool。system 约束模型行为，user 表达需求，assistant 是模型输出，tool 保存工具执行结果。

Token 是分词器切分后的单位。英文单词可能拆成多个 Token，中文字符和标点也不保证一一对应。模型只能看到上下文窗口内的 Token。输入越长，一般延迟和费用越高，重要信息还可能被大量噪声稀释。

CodeRepair 有两个具体的预算问题。

Patch Agent 不能把整个仓库交给模型，所以先扫描文件，再用关键词检索返回少量路径和 snippet，模型需要时再调用 read Tool 查看不超过 400 行的区间。

Anchored Branch 不能把主对话所有历史复制到子分支，所以 `BranchContextBuilder` 固定保留 Anchor 和当前问题，对摘要、分支历史和代码上下文按预算截断。

### 结合当前 CodeRepair 源码

- `code_change/context_retriever.py` 对需求分词，按路径、摘要和内容命中计分。
- `code_change/agent_patch.py` 将读取结果限制为 `MAX_READ_CHARS = 24_000`，Patch 限制为 256 KB。
- `anchored_branch/context.py` 默认 `token_budget=6000`，当前实现用约四个字符估算一个 Token。
- `BranchContext.to_prompt()` 把 Anchor、摘要、历史、代码和当前问题放进带标签的上下文块。

字符除以四只是工程估算，不是精确 Tokenizer。它适合做本地预算保护，不适合用于精确计费。

### 技术选型与替代

精确方案可以调用模型对应的 tokenizer。缺点是不同模型分词器不同，有些 tokenizer 初始化还会访问网络或增加依赖。当前分支上下文更需要稳定的上限，而不是精确到个位数，所以采用字符估算。

检索也可以换成 Embedding 向量库或混合检索。当前项目先用可解释的关键词分数，便于固定测试和本地运行，代价是语义召回有限。

### 边界与追问

不能把 `estimated_tokens` 说成模型供应商返回的真实消耗。当前 Code Change 固定 20 case 也没有统计在线模型 Token。

## 问题 2：Tool Calling 是什么，模型真的执行了函数吗

### 面试官问

Agent 调工具的过程是什么？模型是怎么调用 Python 函数的？

### 30 秒回答

模型不会直接执行 Python。服务端把 Tool 名称、描述和参数 Schema 发给支持 Tool Calling 的模型，模型返回结构化的 tool call，Agent Runtime 校验参数并调用本地函数，再把 ToolResult 作为消息交回模型。CodeRepair 只暴露搜索、限量读文件和提交候选 Patch 三个 Tool，因此模型没有 shell 或直接写文件权限。

### 详细回答

一次 Tool Calling 循环可以概括为：

```text
用户需求和 Tool Schema
→ LLM 返回 tool name + arguments
→ Runtime 解析和校验参数
→ 执行 Python Tool
→ ToolResult 写回消息状态
→ LLM 根据结果继续推理
→ 结束或再次调用 Tool
```

类型化参数很重要。自然语言中写一个 Markdown diff，很难判断它是不是模型的最终产物，也可能把解释文字混进 Patch。CodeRepair 要求模型必须调用 `code_change_submit_patch(patch_text, rationale)`。如果 Agent 结束时没有调用这个 Tool，任务直接失败，不会从最终回答中用正则提取代码块。

Tool 的安全性不由模型承诺保证。Runtime 要在函数内再次验证路径、大小、读取范围和提交次数。模型说"我不会越权"没有约束力，代码里的检查才有约束力。

### 结合当前 CodeRepair 源码

`backend/packages/harness/deerflow/code_change/agent_patch.py` 使用 LangChain 的 `@tool` 定义：

- `code_change_search(query)` 返回相关文件上下文 JSON。
- `code_change_read_file(path, start_line, end_line)` 只读索引文件，最多读取 400 行，再截到 24,000 字符。
- `code_change_submit_patch(patch_text, rationale)` 只允许提交一次，检查大小和变更路径，将结果写入请求级 `PatchCapture`。

`generate_patch_with_agent` 调用 graph 后检查 `sink.patch_text`。为空就抛出 `Agent finished without calling code_change_submit_patch`。

### 技术选型与替代

最宽松的方案是给 Agent shell Tool。它能自主搜索、修改和测试，但攻击面和不确定性更大。当前项目把生成与执行拆开，Agent 只能提出 Patch，Worker 才有执行权限。

也可以要求模型直接输出符合 JSON Schema 的结构化结果，不经过 Tool。Tool 的优势是可以进行多轮 search/read，并在 Runtime 中记录每次调用。

### 边界与追问

typed submit 只能保证输出形状和初步路径安全，不能证明代码语义正确。后面仍需 `git apply --check` 和测试。

## 问题 3：Agent 和普通的一次 LLM 调用有什么区别

### 面试官问

为什么这个功能叫 Agent，不就是调了一次模型吗？

### 30 秒回答

一次 LLM 调用通常是输入 Prompt、得到文本。Agent 则让模型在状态和 Tool 之间形成循环：模型判断下一步，Runtime 执行 Tool，结果回到状态，模型再判断，直到提交结果或达到停止条件。CodeRepair 的 Agent 很受限，但仍然具备 search、read、submit 的多步决策循环。它的自主范围是"怎样找到并提出候选 Patch"，不是"随意执行系统操作"。

### 详细回答

Agent 的核心不是"模型更聪明"，而是模型能够根据中间结果决定下一步动作。比如修复一个函数时，模型先搜索关键词，看到三个候选文件，读取其中一个，发现接口定义在另一个文件，再读取第二个，最后提交 diff。这些动作次数和顺序不是业务代码提前写死的。

但 Agent 不能无限循环。生产系统要限制最大步骤、Token、时间、工具权限和失败策略。否则一次需求可能产生大量模型调用，带来费用和 DoS 风险。

CodeRepair 的 Patch Agent 采用一个很窄的循环。它不装载 DeerFlow 完整 Lead Agent 的 Sandbox、Memory、Subagent 等能力，也不让模型自己运行测试。这样的 Agent 能力较弱，但更适合解释和审计。

### 结合当前 CodeRepair 源码

`create_code_change_agent` 调用：

```python
create_deerflow_agent(
    model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[],
    name="code-change-patch-agent",
)
```

传入 `middleware=[]` 表示使用明确的空中间件列表，不自动装配通用 Agent 的完整功能。graph 接收 HumanMessage 后，在 LangGraph 编译图中执行模型和 Tool 节点循环。

Task 中的 `agent_thread_id` 和 `agent_run_id` 用于本次 Agent 调用的关联和追踪。当前扩展没有为这条受限 Agent 链创建持久化 Gateway Thread/Run，也没有配置 graph checkpointer。

### 技术选型与替代

如果需求固定、步骤固定，普通 Workflow 更可靠。例如"应用 Patch、执行测试、生成报告"没有必要让模型决定顺序，直接由 Worker 编排。

因此这个项目采用混合设计：需要语义判断的检索和 Patch 提案交给 Agent，路径校验、应用、测试和状态迁移交给确定性 Workflow。我认为这比"所有环节都 Agent 化"更合理。

### 边界与追问

不能说 `agent_thread_id` 代表 DeerFlow Gateway 中已经持久化的 Thread。它当前是 Task 元数据和 graph invocation correlation ID。

## 问题 4：LangGraph 和 DeerFlow 分别解决什么问题

### 面试官问

LangChain、LangGraph、DeerFlow 和你的二次开发是什么关系？

### 30 秒回答

LangChain提供模型、消息和 Tool 抽象；LangGraph提供有状态执行图、节点循环和 Checkpoint 能力；DeerFlow在其上封装通用 Lead Agent、Middleware、Sandbox、Memory、Subagent、Thread/Run、SSE 和前端。我没有从零写这些上游能力，而是在 DeerFlow 中新增受控 Code Change 工作流和 Anchored Branch，并复用 `create_deerflow_agent`、Thread、Run、Checkpoint 和 SSE。

### 详细回答

我把它们看成三层。

底层 SDK 层是 LangChain。它提供 ChatModel、HumanMessage、SystemMessage、BaseTool 和 `@tool` 等统一接口，减少不同模型供应商之间的适配工作。

执行图层是 LangGraph。Agent 不是单次函数调用，它有 messages state、模型节点、工具节点、循环和结束条件。LangGraph 负责执行这些状态转换，并可以用 Checkpointer 保存 Thread 状态。

产品框架层是 DeerFlow。它在 LangGraph 之上提供 Gateway Runtime、Lead Agent、Middleware 链、SandboxProvider、Memory、Skills、Subagents、StreamBridge、SSE 和 Next.js UI。

我的二次开发没有复制一套 Runtime。Patch Agent 通过 `create_deerflow_agent` 构建最小 graph；Anchored Branch 使用现有 ThreadStore、Checkpointer、RunManager、StreamBridge 和 SSE，只增加 Anchor、Main/Child 关系和有预算的 BranchContext。

### 结合当前 CodeRepair 源码

- `deerflow/agents/factory.py` 的 `create_deerflow_agent` 最终调用 LangChain `create_agent` 并返回编译后的 StateGraph。
- `deerflow/code_change/agent_patch.py` 传入三个受限 Tool 和空 Middleware。
- `app/gateway/routers/anchored_branch.py` 创建 Child Thread 和空 Checkpoint，调用现有 `start_run`，再通过 `sse_consumer` 返回流式结果。
- `deerflow/anchored_branch/middleware.py` 只在 Child Run 的模型调用前注入 request-scoped Branch Context。

### 技术选型与替代

可以不用 LangGraph，自己写一个 `while` 循环处理 tool call。小功能完全可行。但随着 Checkpoint、流式事件、中断恢复和多个节点增加，自研 Runtime 的维护成本会上升。二次开发 DeerFlow 的目的就是复用这套通用基础设施，把精力放到代码变更的安全边界和上下文分支。

### 边界与追问

简历应写"基于 DeerFlow 二次开发"，并明确新增模块。不能把上游的 Memory、Subagent、Sandbox 和整套前端都算成个人从零实现。

如果追问为什么不直接用通用 Lead Agent，我会回答：通用 Agent 权限和中间件较多，Patch 提案场景更适合最小 Tool 集和清晰权限边界，所以单独使用 `create_deerflow_agent` 构建受限 graph。
