# 08 Queue、Worker、claim、lease 与 fencing

## 为什么要 Queue

Patch 应用和测试可能持续几十秒到几分钟。如果 Gateway 在 HTTP 请求中同步处理：

- 长请求会占用连接和线程。
- 客户端超时后不知道任务是否还在运行。
- Gateway 重启会打断工作。
- 多个测试同时到来会拖慢所有 API。

Queue 把“接收请求”和“执行耗时任务”解耦。Gateway 创建 Task、写入队列后即可返回 task_id；Worker 独立领取。

当前本地队列是 JSONL，用于把流程和产物展示清楚。它不适合多机并发；公司部署可替换为 Redis Streams、Kafka、RabbitMQ 或云任务服务。

JSONL 队列位于当前 owner 的 `owner_dir`。`/worker/run-once` 也只消费请求上下文对应的一个 owner Store；单独使用专用 Worker token 时，认证上下文是默认内部用户。当前没有一个自动扫描所有 owner 的全局 Worker 调度器。目标多租户队列应携带受信任的 owner/task 标识，由 Worker 回数据库做 owner 条件查询，不能让浏览器指定任意 owner。

## claim 是什么

两个 Worker 都看到同一个 `QUEUED` Task 时，只有一个能获得执行权。当前 Store 使用
`O_CREAT | O_EXCL` 原子创建 `.claim.json`。文件已经存在时，第二个 Worker 创建失败。

这是 POSIX 本机文件系统上的原型。`store.py` 使用 `fcntl.flock` 保护 claim 文件，并用 `O_CREAT | O_EXCL` 创建 `.claim.json`。它不能直接用于 Windows，也不代表跨主机或不同 Pod 本地磁盘有效。共享 NFS 也要单独确认锁与原子创建语义。

## lease 是什么

如果 Worker claim 后崩溃，永久 claim 会让任务永远卡住。lease 给执行权一个过期时间：

```text
worker-A claim，expires_at=10:05
→ A 正常执行时定期 heartbeat 续到 10:06、10:07...
→ A 崩溃后不再续租
→ 到期后 worker-B 可以重新 claim
```

lease 太短会让正常长测试被误抢；太长会让故障恢复变慢。应结合最长测试时间和 heartbeat 周期设置，例如 lease 60 秒、每 20 秒续租。

## heartbeat 是什么

heartbeat 是当前持有者主动续租。它必须比较 `claim_id`，不能只按 task_id 延长，否则旧 Worker 在任务已经被 B 接管后，还能继续把 lease 改回自己。

后台 heartbeat 线程也要在任务结束时停止。若续租失败，Worker 应停止提交最终结果，因为它可能已经失去所有权。

## fencing token 为什么还需要

lease 只能决定现在谁“应该”执行，无法立刻停止旧 Worker 的 CPU。场景：

```text
A claim 后发生长时间 GC/网络暂停
→ lease 过期
→ B claim 并完成
→ A 恢复，拿着旧结果写 task.json
```

如果保存结果只检查 worker_id，旧 A 仍可能覆盖 B。fencing 使用每次 claim 唯一的
`claim_id` 或单调递增 token。Store 写状态前再次比较当前 claim；不匹配就拒绝 stale writer。

## 为什么 release 也要带 claim_id

A 的 finally 执行得很晚时，任务可能已经归 B。若 A 只按 task_id 删除 `.claim.json`，就会删掉 B 的 claim。release 必须同时匹配 worker_id 与 claim_id。

## 原子 claim 不等于 exactly-once

即使 claim 完美，Worker 也可能在测试完成、保存状态前崩溃，导致 B 重新执行。因此执行链路应按“至少一次”设计：

- Workspace 每个 attempt 独立，重复执行不污染真实仓库。
- 报告使用 task/attempt 标识。
- 状态写入检查 fencing。
- 外部副作用必须幂等。

“一个任务绝对只运行一次”在分布式故障下代价很高，也通常没有必要。更实际的是允许重复计算，拒绝过期结果和重复外部副作用。

## 公司多机方案

```text
Gateway pods
   │ INSERT task + outbox（同一数据库事务）
   ▼
PostgreSQL ── outbox publisher ── Redis Streams/Kafka
                                      │
                                 Worker pods
                                      │ claim with token
                                      ▼
                              Sandbox execution
```

数据库保存事实状态，队列负责唤醒。只写数据库不发队列会漏任务；只发队列不写数据库会找不到任务。因此常用事务 Outbox 或队列支持的事务能力。

## 面试回答

> claim 防止同一时刻多个 Worker 都认为自己有执行权；lease 让崩溃持有者到期释放；heartbeat 让正常长任务续租；fencing 在最终写入时拒绝已经过期的旧 Worker。当前版本用本地原子文件验证这套协议，多机部署会迁到数据库条件更新或 Redis 脚本，并让 Task 状态成为持久化事实源。

## 本章代码阅读任务

阅读顺序：先读 Store 的领取协议，再读 heartbeat 线程，最后用并发测试验证。

1. 打开 `backend/packages/harness/deerflow/code_change/store.py`，按 `claim_next_task`、`_claim_task_file`、`renew_task_claim`、`save_task`、`release_task_claim` 的顺序读。每个函数都记录它比较的 `worker_id`、`claim_id` 和过期时间。暂不研究所有目录辅助函数。
2. 在同一文件中读 `_task_claim_lock`、`_claim_path`、`_validate_claim`。确认 `fcntl.flock` 只保护本机可见文件，`O_EXCL` 只在同一文件系统语义下竞争成功。看到这里就停止，不要把它类比成跨机分布式锁。
3. 打开 `backend/packages/harness/deerflow/code_change/worker.py`，读 `run_next_task` 和 `_TaskClaimHeartbeat` 的 `start`、`_run`、`stop`、`raise_if_failed`。画出主执行线程和 heartbeat 线程的并行时间线。
4. 打开 `backend/tests/code_change/test_worker.py`，精读 `test_store_claims_queued_task_for_only_one_worker`、`test_expired_task_claim_can_be_recovered`、`test_task_claim_can_be_renewed_only_by_current_owner` 和 `test_run_next_task_heartbeats_during_long_test`。每个测试只需说明输入竞争和断言，不要求掌握 pytest fixture。

看到什么程度：能用 A、B 两个 Worker 画出 claim、续租、A 暂停、lease 过期、B 接管、A 恢复被 fencing 拒绝的完整时间线。

暂不要求：不研究 Linux 文件锁内核实现，也不实现 PostgreSQL 或 Redis 分布式锁；第一遍只掌握本地协议与跨机边界。

验收动作：不看代码复述 A/B 时间线，再打开四个 Worker 测试逐个核对 claim_id、过期和 heartbeat 断言。

## 本章自测

1. Queue 为什么能减轻 Gateway 压力？
2. claim、lease、heartbeat、fencing 分别防什么？
3. 为什么 release 也必须比较 `claim_id`？
4. 为什么有 claim 仍不能承诺 exactly-once？
5. 当前本地 claim 为什么不能直接支持多 Pod？
6. Task 已写数据库但队列消息没发出去，目标架构怎样处理？

## 参考答案

1. Gateway 只持久化 Task 并返回 task_id，耗时的复制、Patch 和测试由 Worker 异步执行。客户端超时和长测试不会长期占住同一 HTTP 请求。
2. claim 竞争当前执行权；lease 让崩溃持有者自动过期；heartbeat 为正常长任务续租；fencing 在写结果和释放时拒绝已经失权的旧 Worker。
3. A 的 finally 可能在 B 接管后才运行。若只按 task_id 删除 claim，A 会删掉 B 的执行权，所以 release 必须匹配 worker_id 和 claim_id。
4. Worker 可能测试完成但保存状态前宕机，新 Worker 会重新执行。系统允许重复计算，用独立 Workspace 和 fencing 拒绝过期结果，并要求外部副作用幂等。
5. 当前实现依赖 owner-scoped 本地 JSONL、`fcntl.flock` 和 claim 文件。不同 Pod 的本地磁盘互相不可见，Windows 也没有相同的 `fcntl` 语义，专用 Worker token 也不会自动遍历全部 owner，因此它不是跨机多租户队列或锁。
6. 在同一 PostgreSQL 事务中写 Task 和 Outbox event。publisher 后续把 Outbox 发布到队列；即使重复发布，Worker 仍用 Task 状态和 claim 幂等领取。
