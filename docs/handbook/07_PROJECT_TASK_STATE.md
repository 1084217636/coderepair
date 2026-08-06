# 07 Project、Task 与状态机

## Project 为什么存在

Project 保存一次次任务共享的配置：仓库路径、默认分支、仓库 URL、测试模板和 owner。没有 Project，每个 Task 都要重新传仓库和命令，容易出现任务访问了不该访问的路径或使用不同测试口径。

核心类在：

```text
backend/packages/harness/deerflow/code_change/models.py
```

需要重点掌握的 Project 字段：

| 字段 | 作用 | 为什么需要 |
| --- | --- | --- |
| `project_id` | 稳定标识 | URL 和目录不依赖显示名 |
| `owner_id` | 所有者 | 防止跨用户读取 |
| `repo_path` | 已校验的本地仓库 | Worker 知道源码位置 |
| `repo_url` | 远端信息 | 生成 handoff 时使用 |
| `default_branch` | 基线分支 | 明确从哪里产生变更 |
| `test_profile` | 对外可见的服务端模板名 | 禁止用户注入任意命令 |
| `test_command` | Store 内保存的模板解析结果 | Worker 获得固定执行命令 |

HTTP 请求只允许 `test_profile`，Router 从服务端配置解析出 `test_command` 后再写入 Project。普通用户不能直接提交命令字符串。Store 同时保存模板名和解析结果，便于 Worker 执行与报告追踪。

## Task 为什么不能只是一行队列消息

Task 是整个业务生命周期。队列消息可能重复、过期或被消费，但 Task 要持续记录：需求、状态、上下文、Patch、测试结果、源码 commit、Worker claim、重试次数、Agent thread/run 和审批材料。

重点字段分组：

```text
身份：task_id, project_id, owner_id
输入：requirement
流程：status, steps, attempt_count, max_attempts
Agent：patch_mode, agent_model_name, agent_thread_id, agent_run_id, agent_rationale
执行：source_commit, workspace_path, sandbox_kind
结果：patch_result, test_result, error, last_error
调度：worker_id, claim_id, lease_expires_at
交接：pr_body_path, approval_path, approved_by
时间：created_at, queued_at, started_at, finished_at
```

## 状态机解决什么问题

如果状态只是随意字符串，任何函数都可能直接把失败任务写成成功，审批接口也可能跳过测试。`state_machine.py` 用允许迁移表限制下一步。

主成功路径：

```text
CREATED
→ QUEUED
→ PLANNING
→ RETRIEVING_CONTEXT
→ GENERATING_PATCH 或 PATCH_RECEIVED
→ VALIDATING_PATCH
→ APPLYING_PATCH
→ RUNNING_TESTS
→ REVIEWING
→ HANDOFF_READY
→ APPROVED 或 CHANGES_REQUESTED
```

只有未来真实 GitHub Provider 返回 PR 标识后，`APPROVED → PR_CREATED` 才能发生。

## 为什么需要 PATCH_REQUIRED

旧流程在没有 Patch 时直接运行原仓库测试。测试很可能通过，然后 Task 停在
`REVIEWING`，但代码根本没有变。安全口径是：

- 外部 Patch 模式没提供 Patch：明确 `PATCH_REQUIRED` 或失败原因。
- Agent 模式：进入 `GENERATING_PATCH`，Agent 必须通过 Tool 提交候选。
- Agent 没调用提交 Tool：任务失败，不能从普通回复里猜代码。

## 为什么每次迁移要写 TaskStep

最终状态只能告诉你现在是什么，不能说明怎样到达。`TaskStep` 记录状态名、摘要、错误和时间，报告才能还原调用链。故障排查时可以看任务卡在哪一步，而不是只看一个 `FAILED`。

## request changes 后怎么办

`CHANGES_REQUESTED` 不能是死状态。用户应提交新的 Patch 或重新触发 Agent attempt，再回到队列。旧 Patch、旧日志和旧审批不能覆盖，应保留 attempt 或至少在时间线里记录版本。

为什么不能直接把原 Task 改回 `CREATED` 并清空所有字段？因为这样会丢失审计证据。当前实现复用同一 Task 目录并增加 `attempt_count`，修订 Patch 会重新入队，但 Patch、Workspace、测试日志和报告仍可能被新 attempt 覆盖。这是明确边界。公司版本应使用 `task_attempts` 表和分 attempt artifact 目录。

## 状态与事实必须一致

判断一条迁移是否合理，可以问：“进入这个状态前，系统掌握了什么不可伪造的证据？”

- `PATCH_RECEIVED`：候选 Patch 文件确实存在。
- `APPLYING_PATCH`：路径校验和 `git apply --check` 已完成。
- `RUNNING_TESTS`：Patch 已在 Workspace 中成功应用。
- `HANDOFF_READY`：测试通过且报告、handoff 已写出。
- `APPROVED`：当前 owner 明确提交审批决定。

这就是状态机不只是画图的原因。

## 本章代码阅读任务

阅读顺序：先看数据字段，再看允许迁移，最后看 Worker 和 Review 怎样使用状态机。

1. 打开 `backend/packages/harness/deerflow/code_change/models.py`，按 `TaskStatus`、`PatchMode`、`Project`、`TaskStep`、`Task` 的顺序读。Project 至少记住 `owner_id`、`repo_path`、`test_profile`、`test_command`；Task 至少记住身份、Agent、执行、调度和审批五组字段。暂不背序列化函数。
2. 打开 `backend/packages/harness/deerflow/code_change/state_machine.py`，先看 `ALLOWED_TRANSITIONS`，再看 `transition`。你要能指出非法迁移在哪里被拒绝，以及合法迁移如何追加 `TaskStep`。第一遍不要求记住全部集合，先记主成功路径和三个终态。
3. 打开 `backend/packages/harness/deerflow/code_change/worker.py`，先看 `create_task` 如何设置 `source_commit`、`patch_mode` 和 Agent 标识，再看 `execute_task` 中外部模式与 Agent 模式的分叉。最后看 `retry_task` 和 `resubmit_patch` 分别接受哪些旧状态。
4. 打开 `backend/packages/harness/deerflow/code_change/review.py` 的 `review_task`。跟到 `transition(task, next_status, ...)` 和 `human_review.json` 写入，确认审批决定必须来自当前状态和 reviewer。

看到什么程度：闭卷写出主成功路径；随机给一个状态时，能说进入它需要什么证据、下一步允许到哪里、失败后怎样处理。暂不要求设计数据库表。

验收动作：手写一条外部 Patch 成功路径、一条 Agent 失败路径和一条 request changes 重入路径，再逐个对照 `ALLOWED_TRANSITIONS`。

## 本章自测

1. Project 为什么同时保留 `test_profile` 和 `test_command`？
2. Task 为什么不能只是一条队列消息？
3. `TaskStep` 比单独的 `status` 多提供了什么？
4. 外部 Patch 和 Agent Patch 在状态机哪里分开，哪里汇合？
5. `CHANGES_REQUESTED` 当前怎样重新进入执行？还缺什么？
6. 为什么不能直接写 `task.status = HANDOFF_READY`？

## 参考答案

1. `test_profile` 是普通用户选择的受控模板名，`test_command` 是 Router 从服务端配置解析出的执行值。这样 API 不接受任意命令，Worker 仍有可执行的固定命令。
2. 队列消息只负责唤醒，可能重复、丢失或过期；Task 要长期保存需求、状态、源码基线、结果、领取权、重试和审批证据。
3. `TaskStep` 记录每次迁移的名称、结果、摘要、错误和时间。它能还原任务怎样走到当前状态，而不仅是最终结果。
4. `RETRIEVING_CONTEXT` 后，外部模式进入 `PATCH_RECEIVED`，Agent 模式进入 `GENERATING_PATCH`。两者都在 `VALIDATING_PATCH` 汇合，再应用 Patch 和测试。
5. reviewer 选择 request changes 后进入 `CHANGES_REQUESTED`，`resubmit_patch` 接收修订 diff、清理当前结果并重新 `QUEUED`。当前同一任务目录会覆盖部分旧 artifact，完整方案需要独立 attempt 记录和目录。
6. 直接赋值会绕过允许迁移、进入证据和 TaskStep。`HANDOFF_READY` 必须在 Patch 可应用、测试通过、报告与 handoff 已生成后由 `transition` 进入。
