# Performance And Evolution Notes

本文档记录项目二每个版本的工程取舍、潜在瓶颈和后续优化方向，方便按真实公司项目演进方式讲述。

## V1：项目空间和任务报告

当前能力：

```text
project create -> repo scan -> context retrieve -> run tests -> task_report/audit/timeline
```

主要瓶颈：

```text
1. repo_scanner 默认最多扫描 500 个源码文件，大仓库会出现扫描耗时增加。
2. context_retriever 会读取候选文件全文做关键词统计，复杂度接近 O(file_count * file_size)。
3. test_runner 直接同步执行测试命令，长测试会阻塞当前任务。
```

优化方向：

```text
1. 建立持久化代码索引，只对 changed files 增量更新。
2. 从文件级召回升级到函数/类/符号级召回。
3. 引入 embedding 或 BM25，避免每次全量读取。
4. 将测试执行放入 worker 队列。
```

## V2：Patch/Test/PR 草稿

当前能力：

```text
unified diff -> git apply --check -> git apply -> run tests -> pr_body.md
```

主要瓶颈和风险：

```text
1. patch 和测试仍在本机仓库执行，隔离不足。
2. git apply 只验证 diff 能否应用，不保证业务正确。
3. test_command 由项目配置提供，需要超时、资源和命令白名单控制。
4. 当前 pr_body.md 是草稿，不直接创建 GitHub PR。
```

优化方向：

```text
1. 接入 DeerFlow sandbox 或 Docker workspace。
2. 对测试命令增加超时、CPU/内存限制和日志截断。
3. 失败任务保留 test.log，触发二次修复。
4. 后续接 GitHub API 创建 draft PR。
```

## V3：FastAPI 项目级 API

当前能力：

```text
把 CLI 闭环暴露为企业研发效能平台 API：
创建项目、列项目、运行任务、查看任务、读取报告、读取 PR 草稿、查看 timeline。
```

验证结果：

```text
FastAPI TestClient smoke 通过。
backend/tests/code_change 9 passed。
```

当前瓶颈：

```text
1. API 仍同步执行 run_task，patch/test 时间长时会占用请求线程。
2. JSON 文件存储适合 MVP，但并发写入能力有限。
3. timeline 读取当前是全量读 JSONL，数据多后需要分页。
```

优化方向：

```text
1. API 只创建任务，Redis/DB 队列交给 worker 执行。
2. 将 JSON 文件迁移到 DeerFlow persistence 或 PostgreSQL。
3. task 列表和 timeline 增加分页。
4. 增加 Prometheus 指标：任务数、耗时、失败率、测试耗时。
```

## V4：任务队列和 Worker

当前能力：

```text
API 创建 QUEUED 任务
  ↓
task_queue.jsonl 记录待执行任务
  ↓
worker run-once 消费一个 QUEUED 任务
  ↓
执行 scan / patch / test / report
  ↓
任务状态更新为 PR_CREATED 或 FAILED
```

相比 V3 的改进：

```text
1. API 不必直接执行长耗时 patch/test。
2. 任务状态可以停留在 QUEUED，便于前端轮询。
3. Worker 逻辑可单独测试，后续能替换成真正的后台进程。
```

当前瓶颈：

```text
1. task_queue.jsonl 是单机 append-only 队列，不适合多 worker 并发抢任务。
2. 当前没有任务租约，Worker 进程中途崩溃后无法自动恢复 RUNNING 中任务。
3. 当前没有重试次数、退避策略和死信队列。
4. patch/test 仍未进入 Docker 或 DeerFlow sandbox。
```

优化方向：

```text
1. 队列迁移到 Redis Stream、PostgreSQL row lock 或 DeerFlow persistence。
2. 增加 lease_until / attempt_count / last_error。
3. 增加 worker 心跳和超时回收。
4. 执行层接 Docker/DeerFlow sandbox，限制 CPU、内存、网络和文件系统范围。
5. 增加任务指标：queued_count、running_count、duration、failure_rate。
```

## V5：Worker 指标和失败重试基础

当前能力：

```text
任务执行前记录 attempt_count / started_at
  ↓
任务结束记录 finished_at / last_error
  ↓
FAILED 且 attempt_count < max_attempts 时允许显式 retry
  ↓
retry 后重新进入 QUEUED
  ↓
metrics 输出 status_counts / queue_depth / failed_count / retryable_failed_count
```

新增入口：

```bash
python -m deerflow.code_change.cli task retry <project> <task_id>
python -m deerflow.code_change.cli worker metrics --project <project>
```

HTTP 入口：

```text
POST /api/code-change/projects/{project_id}/tasks/{task_id}/retry
GET  /api/code-change/metrics?project_id=<project_id>
```

相比 V4 的改进：

```text
1. 失败任务不再只能停在 FAILED，可以显式进入下一次 QUEUED。
2. 每个任务记录 attempt_count / max_attempts / last_error，能解释重试边界。
3. API 和 CLI 都能查看队列深度、失败数和可重试失败数。
4. 测试覆盖成功任务、失败任务、retry、attempt exhausted 和 API metrics。
```

当前边界：

```text
1. retry 是手动触发，没有指数退避和自动重试调度。
2. task_queue.jsonl 仍不适合多 worker 抢占。
3. 没有 lease_until，worker 崩溃后不能自动回收执行中的任务。
4. patch/test 仍在本机仓库执行，下一版必须进入 sandbox。
```

下一步优化：

```text
1. 接 Docker 或 DeerFlow sandbox，所有 patch/test 在临时工作区执行。
2. 增加 lease_until / heartbeat / backoff / DLQ。
3. 将 task.json 和 queue_log 迁移到 PostgreSQL 或 Redis Stream。
4. metrics 对接 Prometheus，把任务失败率、测试耗时和重试次数可视化。
```

## V6：隔离 workspace 执行 patch/test

当前能力：

```text
读取原始 repo 做 scan / context retrieve
  ↓
复制 repo 到 task artifacts/workspace
  ↓
在 workspace 中 apply patch
  ↓
在 workspace 中运行 test_command
  ↓
task.json / audit.json 记录 source_repo_path、workspace_path、sandbox_kind
```

相比 V5 的改进：

```text
1. patch 不再直接应用到用户主仓库。
2. test_command 在 task workspace 中执行，失败日志和 workspace 路径一起留痕。
3. 原始仓库保持干净，便于人工 review、回滚和重复执行。
4. 测试覆盖 workspace copy、patch/test 成功、API 返回 workspace_path 和原仓库未被污染。
```

当前边界：

```text
1. local-copy sandbox 只做文件系统隔离，不限制 CPU、内存、网络和系统调用。
2. 大仓库复制成本高，后续需要 sparse checkout、git worktree 或缓存 workspace。
3. test_command 仍然 shell=True，生产化需要命令白名单和参数化执行。
4. workspace 暂不自动清理，因为它也是审计证据和复盘材料。
```

下一步优化：

```text
1. 接 Docker 或 DeerFlow sandbox，把 workspace 挂载进容器。
2. 对测试命令增加超时、CPU/内存限制、网络开关和日志截断。
3. 增加 workspace manifest，记录复制文件数、大小、忽略目录和执行耗时。
4. 接 GitHub API，把通过测试的 diff 创建成 draft PR。
```
