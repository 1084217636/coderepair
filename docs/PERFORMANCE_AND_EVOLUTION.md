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
