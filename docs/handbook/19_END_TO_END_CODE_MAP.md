# 19 完整调用链与源码地图

## 通用 Agent 请求链

```text
frontend useStream
→ thread_runs.stream_run
→ services.start_run
→ RunManager
→ run_agent
→ make_lead_agent
→ model / middleware / tool
→ StreamBridge
→ sse_consumer
```

## Coding Agent 链

```text
POST /api/code-change/projects/{id}/tasks
→ create_task
→ run_next_task / execute_task
→ prepare_workspace(source_commit)
→ scan_repo + retrieve_context
→ generate_patch_with_agent（agent mode）
→ typed submit
→ apply_patch_text
→ run_tests
→ write_reports + write_pr_handoff
→ HANDOFF_READY → review_task
```

## Anchored Branch 链

```text
UI selection
→ create_branch
→ Child Thread + BranchRecord
→ stream_branch_run
→ BranchContextBuilder
→ AnchoredBranchContextMiddleware
→ existing start_run + SSE
→ create BranchDecision
→ explicit Apply
→ Main Thread metadata
→ next Main Run
```

## 源码地图

- `deerflow/agents/`：Agent factory、Lead Agent、State 与 Middleware。
- `deerflow/runtime/`：Run、Checkpoint、Event、StreamBridge 与用户上下文。
- `deerflow/tools/`、`sandbox/`、`skills/`、`subagents/`：能力、执行环境与扩展机制。
- `deerflow/code_change/`：检索、Patch Agent、Workspace、Test、Task 与报告。
- `deerflow/anchored_branch/`：Anchor、Context、Middleware、Decision 与 Benchmark。
- `app/gateway/routers/`：HTTP、owner/auth 与运行时复用。
- `frontend/src/core/` 与 `components/workspace/`：请求封装与 UI。
- `backend/tests/code_change/`：个人新增部分的主要证据。

## 本章代码阅读任务

- 阅读顺序：按三条链逐个打开符号，最后回 `backend/app/gateway/app.py` 确认 Router 注册和 `lead_agent/agent.py` 的 Middleware 接入。
- 看到什么程度：能在白板上标出模型边界、确定性边界、持久化点、stream、人工门禁和安全检查。
- 暂不要求：不背行号，以稳定符号名为准。
- 验收动作：随机抽取五个符号，在 30 秒内说明输入、输出、调用者、失败分支和对应测试。

## 本章自测

1. 三条链共享了哪些上游能力？
2. 哪些属于个人新增？
3. 哪一步会真正修改 Main Thread metadata？

## 参考答案

1. Thread/Run、Agent factory、Tool/Middleware、Checkpoint、StreamBridge/SSE、Sandbox 等 DeerFlow 基础设施。
2. Code Change 领域链、受限 Patch Agent、Anchored Branch/Context/Decision、API 与控制台集成及其测试。
3. `apply_branch_decision`；创建 Branch、运行 Branch 或保存 Decision 都不等于 Apply。
