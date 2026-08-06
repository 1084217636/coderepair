# 17 故障场景与恢复

面试官问故障，不是想听“加重试”。要先说明故障发生在哪个不可原子的窗口，再说明系统依据什么证据恢复。

## 1. Gateway 创建 Task 后宕机

本地版本可能已经写 task.json，但还没追加 JSONL 队列，产生漏唤醒。单机可用定时扫描 QUEUED Task 补偿；公司版本使用事务 Outbox，让 Task 和待发布事件同事务提交。

## 2. 同一队列消息重复

Worker 先读取 Task 状态。不是 `QUEUED` 就跳过；是 `QUEUED` 还要竞争 claim。重复消息不会直接执行两次外部副作用。

注意：重复计算仍可能发生，所以 Workspace 和结果写入还要幂等/fencing。

## 3. Worker claim 后宕机

lease 到期后其他 Worker 重新 claim。若没有 lease，任务永久卡住；若只有 lease 没 heartbeat，长测试可能被误认为死亡。

## 4. 旧 Worker 暂停后恢复

新 Worker 已拿到新 claim_id。旧 Worker 的 heartbeat、save_task 和 release 都因 fencing 不匹配而拒绝。否则旧结果会覆盖新结果或删掉新 claim。

## 5. Agent 模型超时或 429

记录在 `GENERATING_PATCH` attempt。网络/限流可指数退避重试，次数受 `max_attempts` 限制；参数越界、无 submit Tool 等确定性协议错误不应盲目重试。

重试要复用固定 source commit，不能每次悄悄换最新代码。

## 6. 检索没有找到目标文件

Agent 可能提交错误 Patch或不提交。系统不会因为模型语气自信就继续。评测记录 Recall@5 和 submit/apply/test 指标；人工可以补充路径提示或直接提交外部 Patch。

## 7. Patch 无法应用

`git apply --check` 非 0，Task 进入 FAILED，保存 check log。常见原因是 baseline 变化、上下文不足或 diff 格式错误。恢复方式是基于同一 SHA 重新生成，而不是对真实仓库强制 apply。

## 8. 测试超时

POSIX 环境创建新 session，超时后 kill 整个进程组并记录 `timed_out=true`、exit code 124。非 POSIX 当前回退为终止直接子进程，仍有孙进程边界。不能把超时当跳过；容器方案会销毁整个 Sandbox。

## 9. 测试日志过大

按策略截断并标记。报告显示日志不完整，人工不能把它当作全部证据。更完整方案把流式日志写对象存储并设置总大小上限。

## 10. 测试通过，保存 Task 前宕机

新 Worker 可能重新执行。因为测试在独立 Workspace 且没有外部提交，重复计算可接受。最终 save 检查 claim_id；如果旧 Worker 已失权，结果不写入。

## 11. APPROVED 后创建 GitHub PR 成功，本地保存前宕机

这是外部副作用窗口。重试先按稳定 branch/task marker 查询已有 PR，存在则补写 number/URL，不重复创建。不能靠数据库事务回滚 GitHub。

## 12. PostgreSQL 不可用

Gateway 对创建/审批 fail closed，返回可重试错误；不能只写队列。Worker 保留当前执行结果到本地/对象存储，但没有持久化成功前不能宣告完成。连接恢复后按 claim/fencing提交。

## 13. Queue 不可用

事务 Outbox 仍记录事件，publisher 后续重发。Gateway 可以返回 Task 已创建/待调度；监控 outbox backlog 和最老事件年龄。

## 14. Sandbox 创建失败

任务不进入 APPLYING_PATCH。根据错误类型重试到其他节点或快速失败；必须有全局并发限制，避免故障时无限创建 Pod。

## 15. 用户 A 猜到用户 B 的 task_id

Store 和数据库查询都带 owner 条件。返回 404 或 403，不读取 B 的 task.json、report 或签名下载地址。仅靠 task_id 随机不可猜不是授权。

## 16. 专用 Worker 启动后只处理默认 owner

当前 JSONL 队列属于一个 owner Store，专用 Worker token 只提供服务身份，不会自动枚举全部 owner。如果没有受信任 owner 上下文，它消费默认内部用户的队列。目标架构使用统一可靠队列唤醒，并按消息中的受信任 task_id 回 PostgreSQL 查询 owner 与状态；浏览器不能传 owner 来扩大权限。

## 一个通用回答模板

```text
故障窗口在哪里？
系统已经持久化了什么？
消息/请求是否可能重复？
谁拥有当前写权限？
外部副作用怎样幂等？
恢复后依据什么状态继续？
用什么指标发现？
```

用这个模板比“加重试、加日志、加告警”更具体。

## 本章代码阅读任务

阅读顺序：按故障发生的时间线，从建任务、领取、Agent、Patch、测试、保存、审批和外部 PR 依次定位。

1. 打开 `backend/packages/harness/deerflow/code_change/worker.py`，读 `create_task` 中 `save_task` 与 `enqueue_task` 的先后顺序，再读 `run_next_task` 的 claim、heartbeat、execute、release。标出每两个副作用之间可能宕机的位置。
2. 打开 `store.py` 的 `claim_next_task`、`renew_task_claim`、`save_task(expected_claim_id=...)` 和 `release_task_claim`。为 Worker 崩溃、旧 Worker 恢复、重复消息三个场景找到实际判断条件。
3. 打开 `worker.py::execute_task` 的 Agent、Patch、Test 三个失败分支，记录 `AGENT_GENERATION_FAILED`、`PATCH_APPLY_FAILED`、`TEST_FAILED` 何时写入。再读 `retry_task` 的状态与 attempt 上限。
4. 打开 `test_runner.py::run_tests/_kill_process_tree`，确认 POSIX process group 与非 POSIX fallback；再看日志截断字段如何写入 `TestResult`。
5. 打开 `pr_handoff.py::build_commands`。把它视为未来外部副作用入口，思考 `gh pr create` 成功但 Task 未保存的窗口。当前脚本没有自动执行，所以这一场景属于目标接入设计。

看到什么程度：从本章 15 个故障中随机抽 8 个，回答必须包含“故障窗口、已持久化证据、是否重复、当前写权限、恢复动作、监控指标”至少四项。

暂不要求：不要求现在实现 PostgreSQL、Outbox、GitHub Provider 或告警系统。对于未实现组件，答案必须明确以“目标架构会”开头。

验收动作：自己画两条时序图。一条是 A Worker lease 过期后 B 接管；另一条是未来 GitHub 创建成功但本地保存前宕机。每条图都写出幂等键或 fencing 条件。

## 本章自测

1. Task 保存成功但入队前宕机，当前和目标架构分别怎样处理？
2. 重复队列消息为什么通常不会直接执行两次？
3. 旧 Worker 恢复后哪三个动作必须被 fencing？
4. Agent 429 与 Patch 越界为什么不能使用相同重试策略？
5. 测试通过但 Task 保存前宕机会发生什么？
6. GitHub PR 创建成功但本地保存前宕机怎样收敛？
7. PostgreSQL 不可用时为什么不能宣告完成？
8. 用户猜到别人的 task_id 为什么仍读不到数据？

## 参考答案

1. 当前文件版存在漏唤醒窗口，只能增加扫描 `QUEUED` Task 的补偿器；目标架构把 Task 与 Outbox 放入同一数据库事务，由 publisher 恢复发布。
2. Worker 先读取 Task，只对 `QUEUED` 状态竞争 claim；已有执行者或终态会跳过。重复计算仍可能发生，因此结果保存还要 fencing。
3. 旧 Worker 的 heartbeat、`save_task` 和 `release_task_claim` 都必须比较当前 worker_id 与 claim_id，保存还要检查 lease 未过期。
4. 429 或网络超时可能是暂时错误，可有限指数退避；越界和未调用 submit 是确定性协议或安全错误，盲目重试只会重复风险与成本。
5. 新 Worker 可能在 lease 到期后重跑。Workspace 没有外部提交，所以重复计算可接受；旧 Worker 若已失权，最终 save 会被 claim_id 拒绝。
6. 使用稳定分支名或 task marker 查询远端。若 PR 已存在，就把 number/URL 补写回 Task；不存在才创建，避免重复 PR。当前 handoff 尚未自动执行这一步。
7. Task 状态是完成事实。结果没有持久化成功时，其他 Gateway 和 reviewer 无法确认它，旧 Worker 也可能失去 claim，因此只能保留临时 artifact 并等待带 fencing 的持久化。
8. Store 由可信用户上下文创建 owner scope，读取 Task 后还调用 `_ensure_owner`；目标数据库查询也必须带 owner 条件。task_id 难猜只是一层便利，不是授权手段。
