# 项目二简历与面试包

## 1. 简历项目名

```text
基于 DeerFlow 二开的 AI 代码变更任务流平台
```

技术栈：

```text
Python / FastAPI / Pydantic / pytest / Git diff / DeerFlow / Agent Workflow / RAG / Sandbox / GitHub PR
```

项目描述：

```text
基于字节开源 DeerFlow Agent harness 二次开发项目级代码变更平台，支持项目空间、仓库扫描、上下文召回、Patch 应用、隔离测试、失败重试、审计日志和 PR handoff，形成从需求到 PR 审核材料的闭环。
```

## 2. 简历 bullet

可以直接放简历：

```text
- 基于 DeerFlow Agent harness 二次开发项目级 AI 代码变更平台，设计 project/task/timeline/audit 数据模型，将一次代码修改拆分为上下文召回、Patch 应用、测试验证、报告生成和 PR handoff 等可审计阶段。
- 实现代码变更任务状态机和 Worker 执行流，支持 `QUEUED、PLANNING、RETRIEVING_CONTEXT、PATCH_RECEIVED、VALIDATING_PATCH、APPLYING_PATCH、RUNNING_TESTS、HANDOFF_READY、FAILED` 等状态，并通过 JSONL 队列解耦 API 请求与长耗时测试执行。
- 构建轻量代码仓库 RAG 流程，通过仓库扫描、文件摘要和关键词 Top-K 召回定位相关代码，为后续升级符号索引、BM25 和 embedding 检索预留扩展点。
- 引入 workspace 隔离执行和 sandbox policy，避免 AI Patch 直接污染主仓库；测试命令使用 shell=False、命令白名单、超时和日志截断，提升执行边界和审计能力。
- 实现失败任务 retry、worker metrics、task_report、audit.json、pr_body.md、pr_handoff.json 和 draft PR 脚本生成，让代码变更从需求到人工审核材料形成完整闭环。
```

如果简历空间不够，可以压缩成 3 条：

```text
- 基于 DeerFlow 二次开发项目级 AI 代码变更平台，支持项目空间、上下文召回、Patch/Test、审计日志和 PR handoff，形成需求到 PR 审核材料闭环。
- 设计任务状态机与 Worker 队列，解耦 API 与长耗时执行流程，支持失败 retry、metrics、timeline 和 artifact 留存。
- 引入 workspace 隔离与 sandbox policy，使用 git apply --check、shell=False、命令白名单和测试日志提升 AI 代码变更的可验证性。
```

## 3. 1 分钟介绍

```text
我做的项目是基于 DeerFlow 的二次开发，不是重新写一个 Agent。DeerFlow 本身提供 Agent、memory、sandbox、tools 和 gateway 这些底座，我在它上面补了一个企业研发场景里的代码变更任务流。用户创建项目后绑定仓库和测试命令，提交需求或 patch，平台会扫描仓库、召回相关代码、在隔离 workspace 里应用 patch、执行测试、记录 timeline 和 audit，成功后生成 PR handoff。这个项目重点不是证明模型会写代码，而是把 AI 代码修改变成可追踪、可测试、可审核的研发流程。
```

## 4. 3 分钟介绍

```text
这个项目的起点是我不想做一个“聊天让 AI 改代码”的玩具，因为它很难和 Cursor、Copilot 区分。所以我选了 DeerFlow 作为开源 Agent 底座，只做一个明确的二开方向：项目级代码变更流程。

第一阶段我先读 DeerFlow 的 gateway、harness、memory、sandbox、tools 目录，确定不侵入主 agent 链路，而是在 backend/packages/harness/deerflow/code_change 下新增独立包。这样风险小，也符合公司里接手大项目做增量需求的方式。

第二阶段我把需求闭环做出来：project create 保存仓库和测试命令，task 创建后经过状态机，扫描仓库、召回上下文、应用 patch、跑测试、写报告。后面继续拆出 FastAPI router、队列 Worker、失败 retry、metrics、workspace 隔离、sandbox policy 和 PR handoff。

最后项目达到的效果是：AI 或人工给出的 patch 不直接污染主仓库，而是在任务 workspace 中验证；每一步都有状态、日志、报告和审计记录；测试通过后生成 PR 描述和创建 draft PR 的脚本，由人类审核后进入真实 GitHub 流程。
```

## 5. 高频面试问答

### Q1：这个项目和 Cursor / Copilot 有什么区别？

```text
Cursor / Copilot 偏个人 IDE 辅助，我做的是企业研发流程里的代码变更任务平台。重点不是让模型直接写代码，而是把需求、项目上下文、Patch、测试、审计、PR 审核串成闭环。
```

### Q2：为什么基于 DeerFlow 二开？

```text
因为 DeerFlow 已经有 Agent harness、memory、sandbox、tools、gateway 等基础能力。我不想重复造底座，而是模拟公司里接手复杂开源项目做增量需求：先理解架构，再选择低侵入扩展点，最后用测试和文档收口。
```

### Q3：你具体二开了哪里？

```text
主要新增 backend/packages/harness/deerflow/code_change 包，并接入 backend/app/gateway/routers/code_change.py。新增了 project/task 模型、状态机、仓库扫描、上下文召回、patcher、workspace、sandbox policy、test runner、worker、retry、metrics 和 PR handoff。
```

### Q4：怎么保证 AI 改的代码是对的？

```text
不能完全保证，所以平台不让变更直接进主分支。所有变更先经过 git apply --check，再在隔离 workspace 中应用 patch 和执行测试。测试结果、日志、diff、风险点和回滚建议都会保存，最后生成 draft PR 材料交给人审核。
```

### Q5：为什么要有状态机？

```text
状态机让 Agent 执行过程从黑盒变成可观察流程。比如 `PLANNING、RETRIEVING_CONTEXT、PATCH_RECEIVED、VALIDATING_PATCH、APPLYING_PATCH、RUNNING_TESTS、HANDOFF_READY、FAILED`，每个阶段都能保存产物和错误，便于前端展示、失败重试和审计复盘。`PR_CREATED` 只有真实 GitHub 操作成功后才能写入。
```

### Q6：为什么 V4 引入 Worker？

```text
V3 的 API 同步执行 patch 和测试，测试慢时会阻塞 HTTP 请求。V4 把 API 和执行解耦：API 只创建 QUEUED 任务，Worker 消费队列后执行长耗时逻辑。这更接近公司里的研发效能平台。
```

### Q7：为什么用 workspace？

```text
因为不能让 AI patch 直接改用户主仓库。workspace 是每个任务独立复制出来的执行目录，patch 和 test 都在里面跑。即使失败，也不会污染原仓库，并且 workspace 可以作为审计证据保留。
```

### Q8：为什么 shell=False 很重要？

```text
shell=True 会让测试命令被 shell 解析，容易引入命令串联、重定向和注入风险。V7 改成 shlex.split + shell=False + executable 白名单，降低执行任意命令的风险。
```

### Q9：当前 RAG 做到什么程度？

```text
当前是轻量代码 RAG，先做 repo scan、文件摘要和关键词 Top-K 召回，目的是跑通闭环。后续可以升级到函数级 chunk、符号索引、调用关系、BM25、embedding 和最近修改历史。
```

### Q10：为什么不直接自动创建 GitHub PR？

```text
自动 push 和开 PR 是高风险动作。当前 V8 生成 pr_handoff.json 和 create_draft_pr.sh，由人工审核后执行。这体现的是企业流程里的权限边界：AI 准备材料，人类审核合并。
```

### Q11：项目目前最大的不足是什么？

```text
当前还不是完整生产系统。存储是 JSON 文件，队列是 JSONL，sandbox policy 还不是 Docker 级隔离，RAG 也还不是符号级索引。后续会迁 PostgreSQL、Redis Stream、Docker sandbox、Prometheus 和 GitHub App。
```

### Q12：你怎么做测试？

```text
我用了 compileall 做语法验证，pytest 覆盖 store、state machine、patcher、worker、sandbox policy 和 router，FastAPI TestClient 验证接口，CLI smoke 验证端到端流程，提交前跑 git diff --check。
```

## 6. 不要踩的坑

不要这样说：

```text
我做了一个自动修代码的 AI。
我保证 AI 改出来的代码一定正确。
我复刻了 DeerFlow。
```

应该这样说：

```text
我做的是研发流程平台，AI 只是其中的 patch 生成或辅助环节。
我不保证 AI 一次正确，所以引入测试、审计、retry 和人工 PR 审核。
我基于 DeerFlow 做低侵入二开，重点是项目级代码变更闭环。
```

## 7. 简历项目边界

面试官追问生产化时，可以坦诚说明：

```text
当前版本是秋招可演示 MVP，不是完整企业生产系统。它已经把闭环、状态机、测试、审计和 PR handoff 做出来。真正生产化还需要把文件存储换成数据库，把 JSONL 队列换成 Redis Stream 或 PostgreSQL 队列，把 local-copy sandbox 换成 Docker/DeerFlow sandbox，并接入权限和 GitHub App。
```
