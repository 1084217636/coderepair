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
→ Child Checkpoint only
→ close Branch
→ Main Thread unchanged
```

## 源码地图

- `deerflow/agents/`：Agent factory、Lead Agent、State 与 Middleware。
- `deerflow/runtime/`：Run、Checkpoint、Event、StreamBridge 与用户上下文。
- `deerflow/tools/`、`sandbox/`、`skills/`、`subagents/`：能力、执行环境与扩展机制。
- `deerflow/code_change/`：检索、Patch Agent、Workspace、Test、Task 与报告。
- `deerflow/anchored_branch/`：Anchor、Context Isolation、Middleware、Store 与三策略 Benchmark。
- `app/gateway/routers/`：HTTP、owner/auth 与运行时复用。
- `frontend/src/core/` 与 `components/workspace/`：请求封装与 UI。
- `backend/tests/code_change/`：个人新增部分的主要证据。

## 本章代码阅读任务

### 三条主链必须分开追

一次只选择 Code Change、Anchored Branch 或通用 DeerFlow Run 中的一条：

> 我现在只追【主链名称】。请从用户动作开始，按当前仓库真实调用顺序逐文件、逐函数解释。每经过 HTTP、后台任务、模型、Tool、文件系统、测试、持久化、stream 或人工门禁，都要说明输入对象和输出对象怎样变化；失败沿哪条路径返回；对应测试在哪里。最后给出一版白板短链、五个必须记住的稳定符号、当前能力边界和 5 道带答案的面试追问。

一条链能闭卷画出后再追下一条，不要同时打开三个系统。

- 阅读顺序：按三条链逐个打开符号，最后回 `backend/app/gateway/app.py` 确认 Router 注册和 `backend/packages/harness/deerflow/agents/lead_agent/agent.py` 的 Middleware 接入。
- 看到什么程度：能在白板上标出模型边界、确定性边界、持久化点、stream、人工门禁和安全检查。
- 暂不要求：不背行号，以稳定符号名为准。
- 验收动作：随机抽取五个符号，在 30 秒内说明输入、输出、调用者、失败分支和对应测试。

## 本章自测

1. 三条链共享了哪些上游能力？
2. 哪些属于个人新增？
3. Branch 链中哪一步会修改 Main Thread？

## 参考答案

1. Thread/Run、Agent factory、Tool/Middleware、Checkpoint、StreamBridge/SSE、Sandbox 等 DeerFlow 基础设施。
2. Code Change 主链、Hybrid Retrieval、受限 Patch Agent、Anchored Branch/Context Isolation、API 与双栏控制台及其测试。
3. 没有。create、run、close 都不写 Main；可选总结回主线尚未实现。
