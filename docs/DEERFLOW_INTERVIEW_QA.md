# DeerFlow 二开面试问答

## 1. 你是不是复刻 DeerFlow？

不是。DeerFlow 本身已经是开源 SuperAgent harness，有 sub-agents、memory、sandbox、skills/tools 等能力。我做的是基于它的二次开发：

```text
补项目级研发任务助手能力，让 Agent 围绕一个代码仓库持续管理项目上下文、任务、测试结果和报告。
```

## 2. 为什么第一版没有直接让 Agent 自动改代码？

因为企业研发流程里，“能不能改代码”不是第一步，第一步是任务闭环和可验证性：

```text
创建项目空间
绑定仓库和测试命令
输入需求
召回相关上下文
运行测试
生成任务报告
保存 timeline / audit
```

这个闭环稳定后，再接 patch、sandbox 和 PR。

## 3. 你这次二开改了 DeerFlow 哪里？

新增独立包：

```text
backend/packages/harness/deerflow/code_change/
```

它不侵入 DeerFlow 原主链路，先提供 CLI 闭环，V3 已接入 Gateway API：

```text
backend/app/gateway/routers/code_change.py
/api/code-change/projects
/api/code-change/projects/{project_id}/tasks
```

## 4. 为什么用 JSON 文件存储，不直接用数据库？

第一版目标是最小闭环和可演示。JSON 文件有几个好处：

```text
无数据库依赖
容易看产物
适合面试演示
后续迁移到 DeerFlow persistence 成本低
```

## 5. 当前状态机有什么意义？

状态机把一次研发任务拆成可审计步骤：

```text
CREATED
PLANNING
RETRIEVING_CONTEXT
GENERATING_PATCH
APPLYING_PATCH
RUNNING_TESTS
REVIEWING
PR_CREATED / FAILED
```

这样面试时可以讲清楚：Agent 不是黑盒输出，而是每一步都有状态、产物和失败记录。

## 6. 当前 RAG 是不是太简单？

是轻量版。第一版只做关键词召回，目标是跑通闭环：

```text
路径匹配
摘要匹配
文件内容匹配
Top-K 上下文
```

后续可以升级成：

```text
函数级 chunk
符号索引
调用关系
embedding
最近修改历史
```

## 7. 怎么证明它真的跑了？

当前已验证：

```text
project create
task run
project status
FastAPI code-change router
patch.diff
pr_body.md
task_report.md
test.log
audit.json
timeline.jsonl
```

这证明它已经是一个项目级任务闭环，不只是文档计划。

## 8. 下一步怎么靠近最终简历项目？

当前 V2 已完成：

```text
1. 增加 patcher.py，支持 unified diff。
2. 增加 patch 路径安全校验，防止写出仓库。
3. 增加 patch.diff / patch_check.log / patch_apply.log。
4. 增加 pr_body.md。
5. task run 支持 --patch-file，完成 patch -> test -> PR draft 闭环。
```

当前 V3 已完成：

```text
1. 增加 FastAPI router。
2. 暴露 project/task/timeline/report/pr-body API。
3. 增加 router 级 TestClient 测试。
```

当前 V4 已完成：

```text
1. 将同步 API 执行改成 task queue + worker。
2. 增加 QUEUED 状态和 task_queue.jsonl。
3. CLI 支持 task enqueue / worker run-once。
4. API 默认创建 QUEUED 任务，并提供 worker/run-once。
```

下一步做 V5：

```text
1. 把 test_runner 接入 DeerFlow sandbox。
2. 增加任务租约、重试和死信队列。
3. 把项目历史接 DeerFlow memory。
```

最终简历叙事：

```text
基于 DeerFlow 二次开发项目级 AI 研发任务助手，支持项目空间、代码上下文召回、测试执行、任务报告、审计留痕，并逐步扩展到 Patch、PR 草稿和 IM 回推。
```

## 9. 你怎么保证 Agent 不乱改文件？

V2 先从 patch 安全边界做起：

```text
1. patch 必须是 unified diff。
2. 解析 diff 里的 changed files。
3. 拒绝绝对路径和包含 .. 的路径。
4. 先 git apply --check，通过后才真正 apply。
5. 所有 patch、日志、审计结果都保存到 task artifact 目录。
```

当前还没有宣称“完全安全”，因为真实生产还需要 Docker sandbox、权限隔离、资源限制和人工审核。这个口径比说“AI 自动改代码很安全”更工程化。

## 10. 和 Cursor / Copilot 的区别是什么？

Cursor / Copilot 更偏个人 IDE 辅助。我这个项目关注企业研发流程里的任务闭环：

```text
项目空间
仓库上下文
任务状态机
Patch 应用
测试验证
PR 草稿
审计记录
```

重点不是模型会不会写代码，而是把代码变更纳入可追踪、可测试、可审核的流程。

## 11. V3 API 为什么还不是最终生产形态？

V3 的价值是把 CLI 闭环升级成平台 API，但它仍然是同步执行：

```text
POST /api/code-change/projects/{project_id}/tasks
  ↓
run_task
  ↓
scan / patch / test / report
  ↓
返回 task
```

这适合演示和本地 MVP，不适合长耗时生产任务。生产化应该改成：

```text
API 创建任务
  ↓
任务入队
  ↓
Worker 在 sandbox 执行
  ↓
API 查询任务状态 / timeline / report
```

这个演进逻辑很重要，能说明我知道当前版本的边界和下一步架构优化方向。

## 12. V4 为什么要引入 Worker？

V3 的 API 会在 HTTP 请求里同步执行 patch 和测试，测试一慢，请求就会被长时间占用。V4 把它拆成：

```text
POST /api/code-change/projects/{project_id}/tasks
  ↓
创建 QUEUED 任务
  ↓
写入 task_queue.jsonl
  ↓
Worker run-once 消费任务
  ↓
执行 patch/test/report
```

这样更像公司里的研发效能平台：API 负责接需求和查询状态，Worker 负责长耗时执行。

## 13. V5 怎么处理失败任务？

V5 增加了显式 retry，而不是让失败任务停在 FAILED 后只能人工翻日志。

```text
FAILED
  ↓
POST /api/code-change/projects/{project_id}/tasks/{task_id}/retry
  ↓
QUEUED
  ↓
worker run-once
  ↓
PR_CREATED / FAILED
```

每个任务会记录：

```text
attempt_count
max_attempts
last_error
queued_at
started_at
finished_at
```

这样面试时可以讲：我没有假设 AI 一次就能改对，而是把失败、重试、审计和人工介入都纳入任务流。

## 14. V5 的 metrics 有什么用？

metrics 用来回答平台运维问题：

```text
当前积压多少任务？
失败任务有多少？
哪些失败还能重试？
哪些已经用完重试次数？
总共执行了多少次 attempt？
```

当前接口：

```text
GET /api/code-change/metrics?project_id=demo
```

它还不是 Prometheus exporter，但已经把数据结构准备好了，后续可以平滑接入 Prometheus/Grafana。

## 15. V5 还有哪些生产化不足？

当前 V5 仍是单机 MVP：

```text
1. task_queue.jsonl 不支持多 worker 分布式抢占。
2. 没有 lease 和心跳，worker 崩溃后的任务恢复还没做。
3. retry 是手动触发，没有退避策略和 dead-letter。
4. patch/test 仍未进入 Docker 或 DeerFlow sandbox。
```

下一步应升级成 Redis Stream / PostgreSQL 队列 + sandbox worker，这样更接近公司内部平台。
