# 10 十天源码阅读路线

每天只读 3 到 6 个文件；先画链，再追细节。

| 天 | 只读文件与函数 | 当天必须回答 | 明确跳过 | 产出 |
| --- | --- | --- | --- | --- |
| 1 | `code-change-console.tsx::handleCreateTask`，`api.ts::createCodeChangeTask`，`routers/code_change.py::run_project_task` | 浏览器怎样创建 Task？ | UI 样式 | 前端到 HTTP 图 |
| 2 | `worker.py::create_task/run_next_task/execute_task`，`models.py::Task` | Task 状态和 Worker 如何分工？ | lease 细节 | Task 状态图 |
| 3 | `workspace.py::prepare_workspace`，`repo_scanner.py`，`context_retriever.py` | 为什么先固定 commit 再检索？ | Embedding Provider HTTP 实现 | Workspace 到 Context 图 |
| 4 | `agent_patch.py::generate_patch_with_agent/create_code_change_agent`，`agents/factory.py` | LLM 到底在哪里被 invoke？ | 全部通用 prompt | Agent loop 图 |
| 5 | `build_code_change_tools`，`_safe_repo_file`，对应测试 | tool_call 怎样成为 Python 函数？ | ToolNode 内部源码细节 | Tool 三层图 |
| 6 | `patcher.py`，`test_runner.py`，`report_writer.py` | 谁产生副作用？失败如何落盘？ | 真实 PR 集成 | Patch/Test 图 |
| 7 | `anchored-branch-panel.tsx`，`anchored_branch.py::create_branch`，`models.py::AnchorSelection` | Anchor 如何变 Child Thread？ | 前端 CSS | Main 到 Branch 图 |
| 8 | `stream_branch_run`，`context.py::BranchContextBuilder`，`middleware.py` | Branch 为什么不污染 Main？ | XML prompt 格式细节 | Branch Context 图 |
| 9 | `services.py::start_run`，`runtime/runs/worker.py`，StreamBridge/SSE 入口 | 哪条链真的使用 Thread/Run/SSE？ | 上游未用 Subagent | Run/SSE 图 |
| 10 | `08-upstream-vs-custom.md` 的证据文件、测试目录 | 哪些是上游，哪些是我做的？ | DeerFlow 未使用模块 | 5 分钟项目讲稿 |

P0 必须理解：Task Worker、Retrieval Context、Patch Agent、Tool、Workspace/Test、Anchor/Branch Context、Child Thread/Run 的调用位置。

P1 知道动机：Checkpoint、RunManager、Middleware 框架、SandboxProvider、claim/lease。

P2 暂时跳过：未被项目真实调用的 Subagent、Skills、MCP、长时 Memory、其他模型 Provider、生产化多机部署。
