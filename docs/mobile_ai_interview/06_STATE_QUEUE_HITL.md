# 06 状态机、任务领取、人工审核与 PR 边界

## 问题 1：为什么要显式状态机

### 面试官问

Task 保存一个 status 字符串不就行了吗，为什么还要定义状态迁移表？

### 30 秒回答

只有 status 字段不能阻止非法跳转。CodeRepair 用 `ALLOWED_TRANSITIONS` 明确规定 external 和 agent 的路径，例如 QUEUED 只能到 PLANNING 或 FAILED，测试通过只能到 REVIEWING，再到 HANDOFF_READY，不能直接写 PR_CREATED。`transition` 同时更新时间并追加 TaskStep。这样 API、Worker 和人工审核共享同一套业务约束，也方便故障定位和审计。

### 详细回答

状态机解决的是"当前事实允许发生什么"。如果各个 Handler 随意给 `task.status` 赋值，可能出现未测试就批准、失败任务直接变 PR_CREATED、两个执行分支使用错误状态等问题。

CodeRepair 的主链可以压缩成：

```text
CREATED
→ QUEUED
→ PLANNING
→ RETRIEVING_CONTEXT
→ PATCH_RECEIVED 或 GENERATING_PATCH
→ VALIDATING_PATCH
→ APPLYING_PATCH
→ RUNNING_TESTS
→ REVIEWING
→ HANDOFF_READY
→ APPROVED 或 CHANGES_REQUESTED
```

失败可以在多个阶段进入 FAILED。FAILED 在 attempt 未耗尽时可以重新 QUEUED。CHANGES_REQUESTED 接收修订 Patch 后也重新 QUEUED。APPROVED 只有在真实外部 GitHub 操作成功后才应进入 PR_CREATED。

`TaskStep` 当前记录的是每次迁入状态的时间、摘要和错误。它不是完整的事件溯源系统，但比只有最终状态更容易解释。

### 结合当前 CodeRepair 源码

- `models.py::TaskStatus` 定义状态枚举。
- `state_machine.py::ALLOWED_TRANSITIONS` 定义有向边。
- `transition` 遇到非法边抛出 `InvalidTransition`。
- `worker.py` 只通过 `transition` 推进执行状态。
- `review.py` 只允许 HANDOFF_READY 进入 APPROVED 或 CHANGES_REQUESTED。

### 技术选型与替代

简单系统可以在每个 Service 方法里写 `if status != ...`。状态多、入口多时容易漏。显式迁移表更适合单元测试。

公司版本可以把迁移写成数据库事务：`UPDATE task SET status=? WHERE id=? AND status=? AND version=?`，用影响行数判断竞争，并单独保存 Transition 表。这样能支持多进程并发和审计查询。

### 边界与追问

当前 TaskStep 在 `transition` 调用时写入 Task 对象，最终保存到文件。进程在迁移后、保存前崩溃，内存状态可能丢失。文件版本没有数据库事务那样的持久化保证。

## 问题 2：claim、lease、heartbeat 和 fencing 分别做什么

### 面试官问

两个 Worker 同时看到一个 QUEUED Task，会不会执行两次？一个 Worker 中途挂了怎么办？

### 30 秒回答

Worker 不能直接扫描后执行，它要先 claim。Store 在文件锁内用 `O_EXCL` 创建 claim 文件，只有一个 Worker 成功，并生成唯一 `claim_id`。lease 规定领取有效期，heartbeat 定期续期。Worker 保存最终结果前再次校验 worker id、claim id 和未过期时间，这个 claim id 就是 fencing token，防止旧 Worker lease 过期后又回来覆盖新 Worker 的结果。

### 详细回答

claim 表示任务当前归哪个 Worker。lease 表示这个所有权不是永久的，到期后其他 Worker可以重新领取。heartbeat 表示旧 Worker仍存活，会把到期时间往后延。fencing 解决更隐蔽的问题：旧 Worker发生长暂停，lease 已过期，新 Worker已经领取并执行；旧 Worker恢复后不能再保存结果。

当前领取过程先读取 JSONL 队列，跳过不存在或非 QUEUED 的任务。对候选任务获取 `.claim.lock` 的文件锁，重新读 Task 和现有 claim。如果没有有效 claim，用 `os.open(... O_CREAT | O_EXCL)` 创建 `.claim.json`，写入 worker id、随机 claim id、heartbeat 和 expires time。

`run_next_task` 启动后台 heartbeat 线程，间隔约为 lease 的三分之一，最长 5 秒。执行完成前调用 `assert_task_claim`，保存时也传 `expected_claim_id`。如果 claim 已过期或属于别的 Worker，抛出 `StaleTaskClaim`，旧 Worker 不能覆盖 `task.json` 中的新任务状态。

### 结合当前 CodeRepair 源码

- `store.py::claim_next_task` 遍历队列并调用 `_claim_task_file`。
- `_task_claim_lock` 使用 `fcntl.flock`。
- `_claim_task_file` 使用 `O_EXCL` 创建 claim 文件。
- `renew_task_claim` 刷新心跳和 lease。
- `_validate_claim` 比较 worker id、claim id 和到期时间。
- `worker.py::_TaskClaimHeartbeat` 用守护线程续期。
- `execute_task(... expected_claim_id=...)` 在写报告和保存前检查 fencing。

### 技术选型与替代

本机文件锁能处理同一共享文件系统上的多个进程，但不适合多机。生产实现可以用 PostgreSQL `SELECT FOR UPDATE SKIP LOCKED` 加 lease 字段，或使用 Redis Streams、Kafka Consumer Group、Celery 等成熟队列。

即使使用消息队列，也要考虑重复投递。业务处理最好有 task id 幂等，外部副作用要保存 operation id，不能假设消息绝对只消费一次。

### 边界与追问

当前 Worker API 是 run-once，不是完整常驻调度服务。文件 JSONL 队列会持续追加，也没有消费位点压缩。它能证明领取协议设计，但不能声称已经支持跨机器大规模 Worker 集群。Patch 和测试日志等 Artifact 也没有按 attempt 隔离，旧 Worker 在发现 claim 失效前仍可能写同一任务目录；生产版本需要独立 Attempt 目录解决这个窗口。

## 问题 3：重试和人工修改怎样避免旧结果污染新尝试

### 面试官问

Task 失败后怎么重试？审核要求修改后，旧 Patch 和结果怎么办？

### 30 秒回答

普通失败只能在 `attempt_count < max_attempts` 时 retry，状态从 FAILED 回到 QUEUED。缺少外部 Patch 的 `PATCH_REQUIRED` 不能空重试，必须 resubmit。审核要求修改时状态是 CHANGES_REQUESTED，也通过 resubmit 写入新 Patch。resubmit 会清空旧 PatchResult、TestResult、PR 材料、审批信息和 Agent 元数据，再排队下一次执行，避免页面继续展示旧成功结果。

### 详细回答

重试要区分"同样输入再执行"与"输入已经修改"。

系统性暂时错误，例如 Workspace I/O 失败，可以使用 retry 保留原输入再执行。但 Patch 本身缺失时，重复执行不会产生不同结果，所以 `PATCH_REQUIRED` 强制使用 resubmit。

人工审核选择 request_changes 后，说明旧候选虽然测试通过，但不接受。下一次必须提交修订 Patch。`resubmit_patch` 原子写 `requested_patch.diff`，把 mode 设为 external，并清空 Agent model、rationale、changed files、最终消息以及所有旧验证和审批字段。

当前默认 `max_attempts=2`。每次 `execute_task` 开始会增加 attempt count。限制次数可以避免无限重试消耗资源，但公司场景还要区分用户错误、系统错误和模型错误，设置不同策略。

### 结合当前 CodeRepair 源码

- `worker.py::retry_task` 检查 FAILED、error code 和 attempt 上限。
- `worker.py::resubmit_patch` 只接受 CHANGES_REQUESTED 或 PATCH_REQUIRED。
- `_write_requested_patch` 先写随机临时文件，再 replace 正式 Patch。
- `state_machine.py` 允许 FAILED 和 CHANGES_REQUESTED 回 QUEUED。

### 技术选型与替代

更完整的设计会把每次尝试建成独立 `TaskAttempt`，而不是在一个 Task 上清字段。这样能保留每一版 Patch、测试和审核对比，也更适合审计。当前字段清理实现较简单，早期 Artifact 文件可能仍在目录，但 Task 只引用最新结果。

### 边界与追问

当前没有指数退避、延时队列和错误分类自动重试。不能说已经实现成熟重试平台。

## 问题 4：HITL 和 PR_CREATED 为什么必须严格区分

### 面试官问

测试通过后为什么不自动开 PR？`HANDOFF_READY` 到底代表什么？

### 30 秒回答

HITL 是 Human in the Loop。测试通过后，Worker 只生成 task report、PR body、handoff JSON 和可执行脚本，状态是 HANDOFF_READY，表示材料可供人工检查，不表示批准，也不表示 GitHub 已有 PR。人工 approve 后才到 APPROVED；只有外部 GitHub 调用真实成功并返回 PR 身份，才能进入 PR_CREATED。当前项目没有自动执行这一步。

### 详细回答

测试通过不等于可以发布。测试可能覆盖不足，模型可能修改了需求外文件，代码风格和安全影响仍需人判断。人工审核至少要查看 diff、测试日志、变更范围和风险。

`review_task` 只允许在 HANDOFF_READY 状态操作。approve 会保存 reviewer id、时间和 note，状态变 APPROVED；request_changes 进入 CHANGES_REQUESTED。审核事实写入 `human_review.json`。

Worker 生成的 `create_draft_pr.sh` 只是建议命令。它包含检查干净工作区、切到固定 commit、创建分支、应用 Patch、commit，以及可选的 push 和 `gh pr create --draft`。生成脚本没有执行脚本。

因此当前流程的终点是人工批准和交接材料。状态机虽然定义了 APPROVED 到 PR_CREATED 的合法边，但代码没有 GitHub Provider 去执行并保存真实 PR number 或 URL。

### 结合当前 CodeRepair 源码

- `review.py::review_task` 写审核文件并推进状态。
- `pr_handoff.py::write_pr_handoff` 生成 JSON 和 shell 脚本。
- `state_machine.py` 只允许 APPROVED 进入 PR_CREATED。
- 当前 Code Change Router 没有 `create PR` Endpoint。

### 技术选型与替代

公司版本可以加入 GitHub App Provider。它应使用安装级短期 Token，检查 APPROVED、用 task id 作为幂等键，创建分支和 Draft PR，并在成功响应后保存 repo、PR number、URL 和 provider request id。失败时留在 APPROVED，允许安全重试。

### 边界与追问

简历上不能写"自动创建 PR"，只能写"生成 Draft PR 交接材料并等待人工审批"。如果现场演示手工运行脚本创建过一个 PR，也不等于系统已实现自动 GitHub 集成。
