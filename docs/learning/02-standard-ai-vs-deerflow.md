# 02 标准 AI Agent 与 DeerFlow 的映射

| 标准概念 | 不用框架时要写什么 | DeerFlow 对应 | 本项目实际使用 |
| --- | --- | --- | --- |
| HTTP API | 路由、校验、响应 | Gateway FastAPI Router | `code_change.py`、`anchored_branch.py` |
| Conversation | 保存消息列表 | Thread + Checkpoint | Main Thread 与 Child Thread |
| 一次执行 | 生成 invocation id、记录状态 | Run + RunManager | Branch 通过 `start_run()`；Patch Agent 不持久化 Run |
| Agent State | messages、循环条件 | LangGraph graph state | Patch Agent 把 `messages` 交给 graph.invoke |
| Prompt | 拼 system、history、context | Agent Factory + middleware | `SYSTEM_PROMPT`、Retrieval/Branch Context |
| Function Calling | schema、解析、执行、ToolMessage | LangChain Tool + LangGraph ToolNode | search/read/typed submit 三个 Tool |
| Middleware | invoke 前后改 state | DeerFlow Middleware chain | Branch Context 注入；Patch Agent 明确使用空 middleware |
| Workspace | 临时目录、权限、清理 | SandboxProvider 抽象 | Code Change 使用 local-copy Workspace，不是强 Sandbox |
| Streaming | Token 事件、连接恢复 | StreamBridge + SSE consumer | Branch / 主聊天使用；Patch Task 不流式 |
| HITL | 人工确认状态 | DeerFlow 可承载交互 | 项目用 `HANDOFF_READY → APPROVED` 审核，不自动 PR |

## 最重要的理解

普通 LangGraph Demo 与 DeerFlow 不属于两套理论。前者让你自己拼装 messages、Tool Loop、状态和 HTTP；DeerFlow 将这些抽成可复用 Runtime。项目的价值不在“重新造 Runtime”，而在于在 Runtime 上做业务约束和上下文设计。

## 面试一句话

如果不用 DeerFlow，我需要自己管理 Thread、Run、SSE、Tool Loop 和状态持久化；本项目复用了这些上游能力，并在其上实现 Coding Agent 工作流和 Anchored Branch。
