# 公司多服务器部署与面试口径

## 1. 先背目标架构

```text
Developer / CI
      |
LB / API Gateway / SSO
      |
FastAPI replicas ----------------------> PostgreSQL HA
      |                                      |
      `--> Redis Stream / queue <------------` task/status
                    |
              Worker replicas
                    |
       Sandbox scheduler / K8s Jobs
          |          |          |
       sandbox-1  sandbox-2  sandbox-3
          |          |          |
       Git clone -> patch -> test -> report
                    |
          Object storage / log platform
                    |
          human approval -> GitHub App -> Draft PR
```

一句话：API 层负责鉴权、项目和任务管理，不同步执行耗时修改；共享队列把任务交给 Worker 集群；每个任务进入独立短生命周期沙箱；状态、租约、审计存共享数据库，日志和产物存对象存储；通过人工审批后才由 GitHub App 创建 Draft PR。

## 2. 一个请求跨服务器怎样执行

1. 用户请求经过负载均衡到 API-2，SSO/JWT 得到用户身份。
2. API-2 校验用户是否有该 project 的权限，在 PostgreSQL 事务中创建 Task 和初始事件。
3. API 把 task_id 写入共享可靠队列后立即返回，不占用 HTTP 线程等待测试。
4. Worker-5 原子 claim 任务，写入 owner、lease_until，并周期 heartbeat。其他 Worker 不能同时执行。
5. Worker 从共享项目配置获得仓库、基线 commit、允许的测试命令和资源策略，创建独立 Sandbox/K8s Job。
6. 沙箱克隆指定 commit，进行上下文检索，接收结构化 patch，先 `git apply --check`，再应用并测试。
7. 测试日志持续写日志系统，patch、报告等产物写对象存储；数据库保存状态和产物 URI，而不是把大日志塞入任务行。
8. Worker 根据结果进入 `HANDOFF_READY` 或 `FAILED/RETRY_WAIT`。Worker 崩溃后 lease 过期，其他 Worker 回收任务；步骤必须幂等。
9. 人工审批后，受限 GitHub App 创建分支和 Draft PR。`PR_CREATED` 只在远端 API 成功后写入。

## 3. 为什么需要共享 PostgreSQL 和队列

多台 API/Worker 不能各自使用本地 JSON 文件，否则 API-1 创建的任务 Worker-3 看不到，且并发写、故障恢复和用户隔离难以保证。

生产方案中 PostgreSQL 保存 project、task、attempt、timeline、audit 和权限关系；队列使用 Redis Stream、Kafka 或 PostgreSQL `FOR UPDATE SKIP LOCKED`。选择依据是吞吐、运维成本、延迟和团队基础设施，而不是为了堆组件。

Worker 必须原子 claim：

```text
queued -> running(owner=worker-5, lease_until=T)
```

heartbeat 延长 lease；Worker 失联且 lease 到期后才能回收。重试要保留 attempt，使用指数退避，超过上限进入 DLQ/人工处理。

## 4. 沙箱为什么独立部署

代码和测试不可信，不能直接在 API 或 Worker 宿主机执行。生产沙箱至少限制：

- 独立文件系统和工作目录。
- CPU、内存、进程数和运行时间。
- 默认关闭网络，按项目策略开放依赖源。
- 非 root、只读基础镜像、临时凭据。
- 命令 allowlist，避免 `shell=True` 注入。
- 任务结束销毁，日志和产物外置。

Worker 是编排者，Sandbox 是执行者。把二者分开后，危险代码不会与平台控制面共享进程权限。

## 5. 多实例故障题

**API-2 返回前宕机？** 客户端用 request_id 重试；数据库唯一键返回已有任务，避免重复创建。

**Worker-5 测试中宕机？** heartbeat 停止，lease 到期后 Worker-7 回收。从明确 checkpoint 重试；patch 应用和产物写入需按 task_id/attempt_id 幂等。

**任务入库成功但队列发送失败？** 生产方案用 transactional outbox：Task 和 outbox 同事务提交，后台可靠投递队列。

**队列重复投递？** 队列通常至少一次；数据库状态机、owner/lease 和 attempt 幂等阻止同一阶段产生重复副作用。

**沙箱访问恶意仓库？** 使用网络默认关闭、资源限额、非 root、凭据最小权限、超时销毁和审计。

**两个用户使用同一仓库会串数据吗？** project/task 查询必须带 tenant_id/user_id，workspace 和对象存储路径按 tenant/project/task/attempt 隔离。

## 6. 当前仓库真实实现

当前已经实现：

- FastAPI code-change API。
- project/task/timeline/audit 模型。
- JSONL 队列、原子 claim 文件、lease、heartbeat 和过期回收。
- 独立 workspace、patch check/apply、测试、报告和 retry。
- `shell=False`、命令白名单、超时和日志限制。
- PR handoff、人工审批状态和固定任务评测。

当前没有完成：

- PostgreSQL HA 和真正共享的分布式存储。
- Redis Stream/Kafka 生产任务队列。
- K8s Job/Docker 强隔离沙箱。
- 对象存储、集中日志和完整 Prometheus/Grafana 部署。
- GitHub App 自动创建 Draft PR。

因此标准表述是：**当前代码验证了任务流、状态机、lease、隔离执行和交付闭环；公司多服务器架构是下一步生产化方案，不冒充已经上线。**

## 7. 90 秒背诵版

我基于 DeerFlow 的 Agent harness 二开了项目级代码变更平台。公司场景下，API 和 Worker 都是多实例：API 只负责鉴权、项目和任务创建，通过共享可靠队列把耗时任务交给 Worker；Worker 用原子 claim、lease 和 heartbeat 防止并发重复执行，再为每个任务创建独立沙箱，在指定 commit 上做上下文检索、patch check、应用和测试。任务状态与审计保存在 PostgreSQL，日志和 patch 等大产物进入对象存储。Worker 故障后 lease 到期可由其他实例恢复，重复消息依靠 task 和 attempt 幂等处理。测试通过只进入 HANDOFF_READY，人工审批后才允许 GitHub App 创建 Draft PR。当前仓库真实完成的是文件型 MVP，包括 FastAPI、JSONL 队列、claim/lease/heartbeat、workspace、测试和 PR handoff；PostgreSQL、Redis Stream、K8s 沙箱是明确的生产演进，不会说成已经上线。
