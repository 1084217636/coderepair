# 15 多服务器公司部署与当前边界

## 先回答面试官默认的场景

面试官不会默认 Gateway、Worker、数据库都在一台电脑。公司场景通常是：

```text
Browser
  │
Load Balancer
  ├── Gateway-1
  ├── Gateway-2
  └── Gateway-3
         │
         ├── PostgreSQL
         ├── Queue
         └── Object Storage

Queue
  ├── Worker-1 → Sandbox cluster
  ├── Worker-2 → Sandbox cluster
  └── Worker-3 → Sandbox cluster
```

请求落到哪个 Gateway 都应得到同一项目状态。任务由哪个 Worker 执行也不应依赖本机目录。

## 当前文件 Store 为什么不能直接多机

当前 `CodeChangeStore` 把数据放在本地 `DEER_FLOW_HOME`，并依赖 POSIX `fcntl.flock` 保护 claim：

```text
Gateway-1 创建 task.json 在磁盘 A
→ Gateway-2 查询自己的磁盘 B
→ 404
```

同样，Worker-2 看不到 Gateway-1 的 JSONL 队列。`fcntl` 也不是跨主机分布式锁，Windows 不能直接使用这套实现。即使 K8s 启动 3 个副本，也只是三个互相不知道状态的实例，不叫高可用。

当前队列还按 owner 分目录。一次 `/worker/run-once` 只针对请求上下文中的一个 owner；它不是会发现所有租户任务的全局调度器。公司方案的队列消息应只携带受信任的 task/owner 定位信息，Worker 再用服务身份从 PostgreSQL 做带 owner 条件的查询和 claim。

本地 Store 的价值是结构透明、易测试、方便展示 artifact，不是替代数据库。

## 公司化数据模型

PostgreSQL 作为事实源：

```text
projects
tasks
task_attempts
task_steps
task_claims
reviews
outbox_events
```

关键更新使用条件语句：

```sql
UPDATE task_claims
SET lease_expires_at = now() + interval '60 seconds'
WHERE task_id = $1 AND claim_id = $2 AND lease_expires_at > now();
```

受影响行数为 0 表示 Worker 已失去执行权。数据库唯一约束和事务比多个本地文件更适合跨机器一致性。

## Queue 选什么

### Redis Streams

适合任务延迟低、消费组和 pending reclaim 场景，部署较轻。要处理消息持久化、内存和故障转移。

### Kafka

适合事件量大、需要长时间保留和重放。Code Change 单任务粒度较粗，Kafka 不是必须；使用时仍要让数据库 Task 成为事实源，处理重复消费。

### 专用任务队列

Celery、云任务服务等能提供 retry、visibility timeout 和调度，但仍要避免把业务状态只藏在队列内部。

选型依据是吞吐、保留、运维能力和一致性需求，不是项目里还缺哪个中间件名字。

## Task 写入和入队怎样避免丢失

危险窗口：数据库 Task 已提交，但发队列前 Gateway 崩溃。Task 永远是 QUEUED，却没人唤醒 Worker。

事务 Outbox：

```text
同一数据库事务：INSERT tasks + INSERT outbox_events
→ 独立 publisher 扫描 outbox
→ 发布队列
→ 标记 published
```

publisher 重复发布没关系，Worker 领取时使用 Task 状态与 claim 幂等判断。

## Artifact 放哪里

Patch、test.log、报告可能较大，不适合全塞数据库。公司方案将元数据和 URI 放 PostgreSQL，文件放 S3/OSS/MinIO。对象 key 包含 owner/project/task/attempt，下载使用短期签名 URL 并再次鉴权。

## Sandbox 怎样扩容

Worker 请求 SandboxProvider 创建短生命周期执行环境。K8s 可以按队列深度扩 Worker，Sandbox 用 Job/Pod 或专用池。扩容指标不是 HTTP QPS，而是：

- queue depth 和最老任务等待时间。
- 活跃 Sandbox 数量。
- CPU/内存配额。
- 平均测试时长与超时率。

## Gateway 无状态化

用户认证、Task 和 Report 元数据在外部持久层后，任意 Gateway 都能处理请求。负载均衡无需 sticky session。模型 SSE Run 是否需要粘性取决于上游 Runtime 的持久化方式，但 Code Change 查询 API 本身应无状态。

## K8s 在这里真正做什么

- Deployment 管理 Gateway/Worker 副本和滚动更新。
- Service 提供稳定服务发现。
- ConfigMap 放非敏感配置，Secret 放 token/key。
- readiness 决定是否接流量，liveness 发现卡死进程。
- HPA/KEDA 按 CPU 或队列深度扩容。
- Job/Pod 提供每任务 Sandbox。

K8s 不自动解决数据库一致性、消息幂等和应用状态设计。把本地文件应用部署成多个 Pod，问题反而更明显。

## 当前可说和不可说

可以说：已经实现单机可验证的 owner、状态机、claim/lease/fencing 协议，并给出数据库/队列/Sandbox 的公司化替换边界。

不能说：已经完成生产多机部署、共享文件强一致、真实 Kubernetes 弹性或跨机 Worker 压测，除非有实际部署和证据。

## 本章代码阅读任务

阅读顺序：先从当前本地状态位置出发，再把每个本地依赖映射到目标架构组件。

1. 打开 `backend/packages/harness/deerflow/code_change/store.py` 的 `CodeChangeStore.__init__`。记录 `base_dir`、`owner_dir`、`projects_index`、`queue_log` 和 `projects_dir` 都是本机 Path。继续读 `_task_claim_lock`，确认它使用 `fcntl.flock`。
2. 接着读 `create_project`、`save_task`、`enqueue_task`、`claim_next_task`。为每个函数写出目标架构替换：Project/Task 进 PostgreSQL，queue log 换可靠队列，claim 换数据库条件更新或带 fencing 的原子操作。
3. 打开 `workspace.py::prepare_workspace`、`report_writer.py::write_reports` 和 `pr_handoff.py::write_pr_handoff`。列出 Workspace、Patch、日志、报告当前写入的本机路径，并把长期 artifact 映射到对象存储 URI。
4. 打开 `backend/app/gateway/routers/code_change.py` 的 `get_code_change_store` 和所有只读 Task/Report 路由。判断第二个 Gateway 为什么无法从自己的本地 Store 读到第一个 Gateway 创建的 Task。

看到什么程度：能画出当前单机图和目标多机图，并逐项说明 Store、Queue、claim、artifact、Sandbox 在两张图中的实现差别。

暂不要求：本章不要求部署真实 PostgreSQL、Redis Streams、Kafka 或 Kubernetes，也不要求写完整建表 SQL。要掌握的是替换边界和故障窗口。

验收动作：面试者任选 Gateway-2 查询、Task 入队宕机、Worker 抢占、日志下载、Sandbox 扩容中的一个场景，你能沿目标架构说出数据经过的组件和一致性措施。

## 本章自测

1. 为什么当前文件 Store 增加多个 Pod 后反而会出错？
2. PostgreSQL 在目标架构中保存什么，队列保存什么？
3. 为什么 Task 与 Outbox 要在同一事务？
4. Redis Streams 和 Kafka 怎样按需求选择？
5. artifact 为什么不全塞 PostgreSQL？
6. K8s 能解决什么，不能自动解决什么？
7. 当前 claim 为什么不能称为跨机分布式锁？

## 参考答案

1. 每个 Pod 的本地 `DEER_FLOW_HOME` 不同。Gateway-1 写出的 task.json 和 JSONL 队列对 Gateway-2、Worker-2 不可见，副本之间会返回不同状态。
2. PostgreSQL 是 Project、Task、attempt、step、claim 和 review 的事实源；队列只负责通知有任务可执行。消费端仍要回数据库检查状态和领取权。
3. 若 Task 提交后发队列前宕机，会出现永远无人唤醒的 QUEUED Task。同一事务写 Outbox 后，publisher 可恢复重发，重复消息由 Worker 幂等处理。
4. Redis Streams 部署较轻，适合低延迟消费组与 pending reclaim；Kafka 适合更大事件量、长期保留和重放。Code Change 任务粗粒度，不为堆技术名词强上 Kafka。
5. Patch、Workspace 日志和报告体积可能很大。数据库保存结构化元数据和 URI，对象存储保存文件，并用 owner/task/attempt key 与短期签名 URL 控制访问。
6. K8s 管理副本、滚动发布、Service、健康检查、Secret 和扩容。它不会自动提供数据库事务、消息幂等、任务 fencing 或业务状态一致性。
7. 当前 claim 依赖本机 JSONL、claim 文件、`O_EXCL` 与 POSIX `fcntl.flock`。不同主机的本地磁盘不共享这些状态，Windows 语义也不同；跨机版要用数据库条件更新或真正共享的一致性服务。
