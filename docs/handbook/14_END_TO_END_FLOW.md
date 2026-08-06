# 14 一次完整调用链

这一章把前面的模块串起来。先看外部 Patch 模式，再看 Agent 模式。

## 0. 用户登录

浏览器登录 Gateway，获得 HttpOnly access token 和 CSRF cookie。后续状态变更请求通过前端 fetch wrapper 带上 `X-CSRF-Token`。

Gateway 从用户上下文得到 `user_id`，`get_code_change_store` 用它创建 owner-scoped Store。用户不能通过请求 Body 指定别人的 owner。

## 1. 登记 Project

```text
POST /api/code-change/projects
→ ProjectCreateRequest 校验
→ feature flag 检查
→ repo_path resolve
→ allowed roots 检查
→ test_profile 映射
→ CodeChangeStore.create_project
→ project.json + projects index
```

如果仓库不存在、越过允许根目录或 profile 未定义，请求在这里结束，不会创建半个项目。

## 2. 创建 Task

```text
POST /projects/{project_id}/tasks
→ Store 按 owner 读取 Project
→ new_task_dir
→ Task(CREATED)
→ 写可选 requested_patch.diff
→ QUEUED + queue record
→ 返回 task_id
```

HTTP 路由只创建并入队。CLI 的 `run_task_now` 和测试可以同步执行；公司部署应由持续运行的独立 Worker 消费。

## 3A. 外部 Patch 模式

Worker claim 后发现 `requested_patch.diff`：

```text
PLANNING
→ 扫描仓库
→ RETRIEVING_CONTEXT
→ PATCH_RECEIVED
→ VALIDATING_PATCH
```

外部 Patch 主要用于确定性测试、人工提供候选或回归基线。

## 3B. Agent 模式

没有外部 Patch且任务明确选择 Agent 生成：

```text
RETRIEVING_CONTEXT
→ GENERATING_PATCH
→ create_deerflow_agent
→ search/read tools
→ submit_patch tool
→ 保存 agent_thread_id/agent_run_id/agent_rationale/candidate
→ PATCH_RECEIVED
→ VALIDATING_PATCH
```

如果 Agent 没调用 submit、模型 API 失败或候选越界，进入 FAILED，不会继续测试原仓库。

## 4. 固定源码与 Workspace

Worker 记录 `git rev-parse HEAD` 为 source commit。`prepare_workspace` 将仓库复制到 Task
目录，真实仓库保持只读口径。

在公司方案中，Worker 会 checkout 固定 SHA 到容器 Workspace，避免源目录在执行中变化。

## 5. Patch 校验与应用

```text
extract_changed_files
→ validate_patch_paths
→ git apply --check
→ git apply
→ PatchResult
```

任何一步失败都记录日志、结束时间和 FAILED 状态。

## 6. 运行测试

Project 的 profile 在服务端映射为 argv。Worker 使用最小环境、Workspace cwd、超时和日志上限运行。退出码非 0 或超时都不能进入审阅成功路径。

## 7. 生成材料

测试通过后：

```text
RUNNING_TESTS
→ REVIEWING
→ write_pr_body
→ write_pr_handoff
→ write_reports
→ HANDOFF_READY
```

Task 保存 PatchResult、TestResult 和各文件路径。前端轮询 Task，终态时读取 Markdown 报告。

## 8. 人工决定

```text
POST /review {decision: approve}
→ 检查 owner
→ 检查 HANDOFF_READY
→ human_review.json
→ APPROVED
```

驳回则 `CHANGES_REQUESTED`，后续新 Patch/Agent attempt 必须重新测试。

## 9. claim 与 heartbeat 同时发生

执行期间后台 heartbeat 按 claim_id 续租。每次关键保存验证 fencing。任务结束时 finally 只有在
claim_id 仍匹配时才能 release。

如果续租失败，Worker 不能继续把结果写成成功。它应中止或让当前 attempt 标记为失去 ownership，等待新 Worker 从安全状态恢复。

## 一句话串起来

> Gateway 认证并创建 owner-scoped Task，Worker 用带 lease 和 fencing 的 claim 领取；外部 Patch 或最小权限 DeerFlow Agent 提交候选 diff；Worker 在固定源码的独立 Workspace 做路径检查、git apply 和服务端测试模板，写出报告后进入 HANDOFF_READY，再由当前 owner 审批。任何模型文字、日志声明或请求超时都不能跳过状态证据。

## 本章代码阅读任务

阅读顺序：从 Router 入口进入 Worker，再沿 Workspace、Agent/Patch、Test、Report、Review 顺序跟调用。

1. 从 `backend/app/gateway/routers/code_change.py` 开始，按 `ProjectCreateRequest/create_project`、`TaskRunRequest/run_project_task`、`run_worker_once`、`review_project_task` 的顺序读。为每个入口写出输入、领域函数和返回状态。暂不读其他 Gateway Router。
2. 跳到 `backend/packages/harness/deerflow/code_change/worker.py`，按 `create_task`、`run_next_task`、`execute_task`、`_generate_agent_patch`、`resubmit_patch` 的顺序读。用两种颜色标出外部模式与 Agent 模式，直到它们在 `VALIDATING_PATCH` 汇合。
3. 沿 `execute_task` 的调用顺序，只读每个被调模块的主函数：`workspace.py::prepare_workspace`、`repo_scanner.py::scan_repo`、`context_retriever.py::retrieve_context`、`patcher.py::apply_patch_text`、`test_runner.py::run_tests`、`pr_handoff.py::write_pr_handoff`、`report_writer.py::write_reports`。每个函数只记录输入、返回值和一个失败分支，不展开辅助函数。
4. 最后读 `review.py::review_task` 和 `store.py::save_task/release_task_claim`。确认审批发生在 Worker 完成后，Task 保存与释放都受 owner 或 claim 约束。

看到什么程度：不看文档，连续口述 requirement 到 `HANDOFF_READY`，至少说出 15 个真实函数或字段；外部和 Agent 两种模式都要能讲。

暂不要求：不展开各模块全部辅助函数，也不读上游所有 Gateway API；本章只负责把已经学过的主函数串成完整时序。

验收动作：分别录制外部模式与 Agent 模式的五分钟口述，回放时记录漏掉的状态、字段和失败路径，再回源码核对。

## 本章自测

1. Project 创建时怎样阻止任意仓库和任意命令？
2. 外部模式和 Agent 模式的输入有什么不同？
3. 两种模式在哪个状态汇合？
4. source commit 在什么时候确定，Workspace 怎样使用它？
5. 测试通过后为什么还要 `REVIEWING` 和 `HANDOFF_READY`？
6. heartbeat 失败后为什么不能照常保存成功？

## 参考答案

1. `ensure_repo_path` 要求 repo 位于 allowed roots；HTTP 只接 `test_profile`，Router 从服务端配置解析固定 `test_command`。owner 也来自可信用户上下文，不从请求 Body 读取。
2. 外部模式要求请求提供 unified diff；Agent 模式要求 `patch_mode="agent"`，不能同时传外部 Patch，并可指定配置中的模型名。两者都先创建 `QUEUED` Task。
3. 外部模式经 `PATCH_RECEIVED`，Agent 模式经 `GENERATING_PATCH`。两者都进入 `VALIDATING_PATCH`，共享路径检查、apply、test、report 和审批链。
4. `create_task` 用 `resolve_source_commit` 记录当前 HEAD。`prepare_workspace` 使用 `git archive` 导出这个固定 SHA，而不是复制可能已变脏的工作树。
5. 测试通过后，Worker 还要生成 PR body、handoff 和报告，才有完整人工审阅材料。`HANDOFF_READY` 表示可审，不等于业务正确或 PR 已创建。
6. heartbeat 失败说明 lease 可能过期且新 Worker 已接管。旧 Worker 若继续保存会覆盖新结果，所以最终 `assert_task_claim/save_task` 必须用原 claim_id 做 fencing。
