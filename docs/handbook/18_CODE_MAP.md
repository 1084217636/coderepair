# 18 必须掌握的类、字段和函数

这不是要求背下每一行，而是让你在面试官追问“具体写了什么”时能落到真实代码。

## 领域模型

路径：`backend/packages/harness/deerflow/code_change/models.py`

### Project

至少会说：`project_id`、`owner_id`、`repo_path`、`default_branch`、`test_profile`。

### Task

至少会说：`task_id`、`project_id`、`requirement`、`status`、`steps`、`contexts`、
`patch_result`、`test_result`、`source_commit`、`attempt_count`、`worker_id`、`claim_id`、
`lease_expires_at`、`patch_mode`、`agent_thread_id`、`agent_run_id`、`agent_rationale`。

### PatchResult / TestResult

PatchResult 记录路径、changed files、增删行、apply 结果和日志。TestResult 记录命令/profile、exit code、耗时、超时、截断和日志路径。

## 状态机

路径：`state_machine.py`

- `ALLOWED_TRANSITIONS`：允许迁移表。
- `transition(task, next_status, summary, error)`：验证迁移，更新时间，追加 TaskStep。
- `InvalidTransition`：非法跳状态时抛出。

追问：为什么不直接 `task.status = ...`？因为所有路径必须遵守同一约束并留下步骤证据。

## Store 与调度

路径：`store.py`

- `CodeChangeStore.__init__`：确定 owner 目录和允许仓库根。
- `create_project/get_project`：保存和读取 owner-scoped Project。
- `save_task/get_task/list_tasks`：Task 持久化。
- `enqueue_task/queued_items`：本地 JSONL 唤醒记录。
- `claim_next_task`：竞争执行权。
- `renew_task_claim`：按 claim_id heartbeat。
- `release_task_claim`：只释放自己的 claim。
- `_write_json`：临时文件 + `os.replace` 原子发布。

## Worker

路径：`worker.py`

- `create_task`：创建 Task 和候选 Patch artifact。
- `execute_task`：主状态机编排。
- `run_next_task`：claim、heartbeat、执行、release。
- `retry_task`：失败重试。
- 修订 Patch 入口：让 `CHANGES_REQUESTED` 进入新 attempt。

能从 `execute_task` 讲出 scan、retrieve、workspace、apply、test、report 顺序。

## Patch Agent

路径：`agent_patch.py`

- `build_code_change_tools`：创建请求级 Tool 和 PatchCapture。
- `_safe_repo_file`：防绝对路径和 repo escape。
- `create_code_change_agent`：调用 `create_deerflow_agent`。
- `generate_patch_with_agent`：运行图、附 thread/run/task metadata、要求 typed submit。
- `AgentPatchResult`：候选 Patch、理由、changed files 和运行关联。

## 检索

- `scan_repo`：后缀与目录过滤，生成 CodeFile。
- `retrieve_context`：路径/摘要/内容打分，取 Top-K。
- `tokenize`：中英文词项处理。

## Patch 与 Workspace

- `extract_changed_files`：从 diff header 提取路径。
- `validate_patch_paths`：拒绝 absolute/`..`。
- `apply_patch_text`：写 artifact、check、apply、返回 PatchResult。
- `prepare_workspace`：复制源码到 Task Workspace。

## 测试与策略

- `load_test_profiles`：服务端模板名转固定命令。
- `run_tests`：cwd、env、timeout、log 上限和 TestResult。
- `SandboxPolicy`：当前执行策略证据。

## 报告与审批

- `write_reports`：Markdown + audit。
- `write_pr_body`：PR 草稿正文。
- `write_pr_handoff`：生成交接材料，不是真实 GitHub PR。
- `review_task`：检查状态与 owner，记录批准/驳回。

## Gateway Router

路径：`backend/app/gateway/routers/code_change.py`

至少会讲：

- `get_code_change_store` 为什么读取当前 user_id。
- feature flag dependency。
- ProjectCreateRequest 为什么只有 test_profile。
- `/worker/run-once` 为什么需要 internal token。
- task/report/review 路由为什么都要 owner scope。

## Frontend

路径：

```text
frontend/src/app/workspace/code-change/
frontend/src/core/code-change/
```

页面用认证 fetch wrapper 调 Gateway；前端只展示和提交业务输入，不持有 Worker Secret，也不执行命令。

## 闭卷检查

随机挑上面 12 个函数，每个回答：输入、输出、调用谁、可能失败什么。如果只能说文件名，不能说字段与失败路径，还没达到面试要求。

## 本章代码阅读任务

阅读顺序：不要按文件树从上到下扫。按一次任务的调用顺序阅读，并为每个符号制作四格卡片：输入、输出或副作用、下游调用、失败路径。

1. 领域入口：读 `models.py::Project/Task`、`routers/code_change.py::TaskRunRequest/run_project_task`、`worker.py::create_task`。看到能从 HTTP JSON 讲到 `Task(QUEUED)`，并说出 `patch_mode` 与 source commit 的来源。
2. 调度：读 `store.py::enqueue_task/claim_next_task/renew_task_claim/save_task/release_task_claim`、`worker.py::run_next_task/_TaskClaimHeartbeat`。看到能说清 worker_id、claim_id、lease 与本地文件路径。
3. Agent：读 `agent_patch.py::build_code_change_tools/create_code_change_agent/generate_patch_with_agent`、`worker.py::_generate_agent_patch`。看到能说清三个 Tool、typed capture、Task Agent 字段和失败状态。
4. 执行：读 `workspace.py::resolve_source_commit/prepare_workspace`、`patcher.py::extract_changed_files/validate_patch_paths/apply_patch_text`、`test_runner.py::run_tests/build_test_environment`。看到能按固定 SHA、check、apply、test 顺序讲，并指出日志路径。
5. 治理：读 `report_writer.py::write_reports/render_task_report`、`pr_handoff.py::write_pr_handoff/build_commands`、`review.py::review_task`、`worker.py::resubmit_patch`。看到能区分 report、handoff、approve、request changes 和真实 PR。
6. 前端：读 `frontend/src/core/code-change/types.ts` 的 `CodeChangeProject/CodeChangeTask/CreateTaskInput`，再读 `api.ts` 的 create/get/review 函数，最后读 `code-change-console.tsx` 的 `handleCreateProject/handleRunTask/handleRefreshTask/handleReview`。只跟数据流和按钮条件，不学习 CSS。

看到什么程度：随机抽 12 个上述符号，30 秒内说出四格卡片；至少包含 3 个数据类、3 个 Store/Worker 函数、2 个 Agent 函数、2 个执行函数、1 个 Router 和 1 个前端 handler。

暂不要求：不背 UUID、时间格式、Markdown 模板和 React 样式。也不要求读完上游 DeerFlow 全仓，只精读 `create_deerflow_agent` 的参数与个人二开的调用点。

验收动作：关闭 IDE，让同学随机报函数名。每次回答后重新打开源码核对；任何答错的输入、状态或失败分支都补回自己的四格卡片。

## 本章自测

1. `create_task` 的主要输入、输出和失败路径是什么？
2. `execute_task` 的两种 Patch 模式怎样分叉和汇合？
3. `claim_next_task` 与 `save_task(expected_claim_id=...)` 分别解决什么？
4. `generate_patch_with_agent` 为什么必须返回 `AgentPatchResult`？
5. `prepare_workspace` 与 `apply_patch_text` 的职责边界是什么？
6. `run_tests` 至少记录哪些结果字段？
7. `write_pr_handoff` 为什么不等于创建 PR？
8. 前端 `handleRunTask` 为什么不能拿到 Worker token？

## 参考答案

1. 输入是 Store、project、requirement、可选外部 Patch、enqueue、patch_mode 和模型名；输出是带 source commit 与 artifact_dir 的 Task。仓库无 commit、模式与输入冲突、Patch 为空或过大都会失败。
2. 外部模式读取 `requested_patch.diff` 并进入 `PATCH_RECEIVED`；Agent 模式进入 `GENERATING_PATCH`，调用受限 Agent 写出候选。两者在 `VALIDATING_PATCH` 汇合，共用 apply、test、report 和 review。
3. `claim_next_task` 竞争当前执行权；`save_task(expected_claim_id)` 在最终写入时再次验证 ownership 和 lease，拒绝恢复后的旧 Worker 覆盖结果。
4. 结构化结果同时带 Patch、理由、changed files、final message、thread_id 和 run_id 关联值，Worker 才能持久化候选与追踪信息。当前这些是 Task 生成的 metadata，不是 Gateway 持久化 Run 记录；只返回自然语言还会丢失类型和协议边界。
5. `prepare_workspace` 从固定 commit 创建任务目录并记录 manifest；`apply_patch_text` 在这个目录中提取和校验路径，运行 check 与 apply，并返回 PatchResult。前者不理解 diff，后者不负责源码基线。
6. command、exit_code、duration_seconds、log_path、timed_out、log_truncated 和 policy_path。`passed` 由 exit code 是否为 0 计算。
7. 它只写 JSON 与可执行脚本，脚本里含将来手动运行的 Git/gh 命令。Python 函数没有调用 GitHub API，也没有保存 PR number 或 URL。
8. 浏览器是终端用户边界，只能创建和查询自己的 Task。Worker token 是服务身份，放进客户端 bundle 就会被任何用户提取并滥用计算资源。
