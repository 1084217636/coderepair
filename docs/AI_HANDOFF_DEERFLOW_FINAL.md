# DeerFlow 二次开发最终项目上下文（给 AI 与本人）

> 更新日期：2026-07-17
> 项目目录：`agent-code-change-platform/`
> 项目性质：基于字节开源 DeerFlow 2.0 的低侵入二次开发。
> 项目方向：把通用 Super Agent 的一次性执行能力，扩展成项目级、可追踪、可验证、可审核的 AI 代码变更任务流。
> 使用方式：把本文完整交给其他 AI。其他 AI 必须区分“DeerFlow 上游能力”“当前已实现二开能力”和“最终目标”，不得把上游代码全部说成个人实现。

## 1. 项目最终定位

项目名建议统一为：

```text
DeerFlow CodeOps：项目级 AI 代码变更与 PR 交付平台
```

一句话介绍：

```text
我基于 DeerFlow 2.0 的 Agent、Skills、Tools、Sub-Agents、Memory 和 Sandbox 架构做低侵入二次开发，增加 Project/Task 控制面、代码上下文召回、隔离 Patch/Test、任务状态机、审计产物和 PR Handoff，把一次 AI 代码修改从对话行为变成可追踪、可测试、可人工审核的研发流程。
```

项目的正确主线是：

```text
读懂复杂开源 Agent 架构
  ↓
找到低侵入扩展点
  ↓
针对企业代码变更场景增加确定性控制面
  ↓
用状态、策略、沙箱、测试、审计和人工审批约束 AI 的不确定性
```

不要说成：

```text
我从零实现了 DeerFlow。
我自己实现了完整多 Agent 框架。
AI 可以保证自动修复任何代码。
平台已经自动创建并合并 GitHub PR。
```

## 2. 为什么选择 DeerFlow 二开

### 2.1 技术原因

DeerFlow 2.0 已经提供通用 Agent Harness 的关键能力：

- Lead Agent 和 LangGraph/LangChain Agent 执行循环。
- Middleware 形式的上下文、总结、记忆、工具错误、循环检测和安全控制。
- Skills 与 Tools 扩展机制，以及 MCP 外部工具接入。
- Sub-Agent 注册、委派、隔离执行和结果回收。
- Local/Container 等 Sandbox 抽象与文件、命令工具。
- Thread、Run、Checkpoint、事件流和持久化基础。
- FastAPI Gateway、LangGraph-compatible API、Next.js 前端和 IM Channels。

如果从零重写这些底座，时间会花在重复造 Agent 框架上，无法突出业务设计。基于 DeerFlow 二开，更接近真实公司里的工作方式：接手成熟系统、读懂边界、选扩展点、完成增量闭环。

### 2.2 业务原因

通用 Agent 擅长“完成一个开放任务”，但企业代码变更还需要一层确定性流程：

```text
这个任务属于哪个项目？
允许读取和修改哪些目录？
必须运行哪些测试？
每一步处于什么状态？
失败能否重试和复盘？
谁批准真正写仓库和创建 PR？
最终有哪些证据可供 Code Review？
```

因此二开的重点不是再造一个更会写代码的模型，而是给通用 Agent 增加“代码变更控制面”。

### 2.3 求职价值

这个项目能证明三种能力：

1. 能阅读并解释一个复杂 Python/Agent 开源项目，而不只会从零写小 Demo。
2. 能把不确定的 LLM 行为放进状态机、策略、测试和人工审批组成的确定性工程流程。
3. 能诚实区分开源底座、个人增量和生产化设想，并用测试与 artifact 证明实现。

## 3. 原版 DeerFlow 的结构

### 3.1 总体架构

```text
Next.js Frontend / TUI / IM Channels
                │
                ▼
        FastAPI Gateway
  Threads / Runs / Models / Memory / Skills / MCP
                │
                ▼
      Lead Agent / Agent Factory
                │
       ordered middleware chain
                │
                ▼
       Model <-> Tool Call Loop
         │       │       │
         │       │       ├── Skills / MCP Tools
         │       ├────────── Sandbox file/command tools
         └────────────────── Sub-Agent delegation
                │
                ▼
 Runtime / Checkpoint / Events / Persistence / Tracing
                │
                ▼
      streaming result back to client
```

### 3.2 各层职责

#### 接入层：Frontend、Gateway、Channels

- `frontend/`：Next.js 对话、任务进度和产物展示。
- `backend/app/gateway/`：FastAPI 入口，提供 models、threads、runs、memory、skills、MCP、uploads、artifacts、agents 和 channels 等 API。
- Gateway 兼容 LangGraph 的 thread/run 生命周期，并把事件流返回客户端。
- Channels 把飞书、Slack、Telegram、钉钉等消息转换为 Agent 任务。

#### Agent 编排层

- `deerflow/agents/lead_agent/`：面向应用配置构建 Lead Agent。
- `deerflow/agents/factory.py`：从 model、tools、features、middleware 和 checkpointer 组装 Agent Graph。
- `ThreadState` 保存一次 thread 的运行状态。
- Agent 本质上执行“模型决策—工具调用—工具结果—继续推理”的循环。

#### Middleware 层

DeerFlow 没有把所有逻辑硬编码进 Agent 节点，而是通过有顺序的 Middleware 增强运行时。典型能力包括：

```text
ThreadData / Uploads / Sandbox
Tool error handling
Guardrail
Context summarization
Todo / plan mode
Title generation
Long-term memory
Sub-Agent concurrency limit
Loop detection
Token budget
Clarification
```

理解重点：Middleware 的执行顺序会影响 prompt、tool、state 和错误处理，二开不能随意插入或打乱。

#### Tools、Skills 与 MCP

- Tool 是模型可以直接调用的函数能力。
- Skill 是带 `SKILL.md` 的任务知识与流程包，可声明允许的工具和所需 secrets。
- MCP 用统一协议接入外部工具或数据源。
- Tool/Skill 负责扩展“会做什么”，Middleware 负责扩展“运行时怎么约束和管理”。

#### Sub-Agent

- Lead Agent 可以把边界明确的子任务交给不同 Sub-Agent。
- Sub-Agent 可配置自己的模型、prompt、tool allowlist/denylist 和运行限制。
- 适合并行检索、独立分析和专项任务，但不能把所有简单步骤都拆成多 Agent。

#### Sandbox

- Sandbox 向 Agent 暴露受控文件系统和命令执行能力。
- Local Sandbox 适合开发；Container/远程 Sandbox 才能进一步隔离文件、进程、资源和网络。
- 对代码变更任务而言，Sandbox 是防止 AI 直接污染宿主机和主仓库的关键边界。

#### Memory、Runtime 与 Persistence

- Memory 保存跨会话的用户或 Agent 长期信息，并通过 Middleware 注入上下文。
- Runtime 管理 Run、事件、流式桥接、Checkpoint 和执行状态。
- Persistence 保存 thread/run metadata 等系统事实。
- Tracing 用来观察模型、工具和 Agent 的调用链。

### 3.3 一次 DeerFlow 原生任务如何运行

```text
用户在 Web/TUI/IM 输入任务
  ↓
Gateway 创建或继续 Thread，并创建 Run
  ↓
根据配置构建 Lead Agent、Model、Tools 和 Middleware
  ↓
Middleware 注入 thread、uploads、memory、skills、sandbox 等上下文
  ↓
模型决定直接回答、调用工具、请求澄清或委派 Sub-Agent
  ↓
工具在权限和 Sandbox 边界内执行
  ↓
工具结果回到模型，Agent 循环直到完成或触发终止条件
  ↓
Runtime 持久化状态并把事件流传给 Gateway/Frontend
  ↓
后台 Memory 更新器按需沉淀长期信息
```

面试不需要逐行背源码，但必须能解释上述链路以及 Agent、Middleware、Tool、Skill、Sub-Agent、Sandbox、Memory 的区别。

## 4. 我的二开到底做了什么

### 4.1 归属矩阵

| 能力 | 来源 | 面试时的准确说法 |
| --- | --- | --- |
| Lead Agent、Agent Graph、模型循环 | DeerFlow/LangChain 上游 | 我阅读并复用的 Agent 底座 |
| Middleware、Skills、MCP、Sub-Agent | DeerFlow 上游 | 我理解并计划用于深度集成的扩展机制 |
| DeerFlow Sandbox 抽象 | DeerFlow 上游 | 当前 MVP 尚未真正接入，最终版执行层应复用 |
| FastAPI Gateway | DeerFlow 上游 | 我在其中挂载了 code-change router |
| Project/Task 数据模型 | 我的二开 | 新增项目级代码变更控制面 |
| 状态机、Timeline、Audit | 我的二开 | 把黑盒执行变为可观察流程 |
| Repo Scanner、关键词 Top-K 召回 | 我的二开 | 当前轻量代码上下文检索 |
| Patch 校验与应用 | 我的二开 | `git apply --check` 后在 workspace 应用 |
| local-copy workspace、执行策略 | 我的二开 | 文件级隔离和命令约束，不等于容器沙箱 |
| JSONL Queue、Worker、Retry、Metrics | 我的二开 | 单机 MVP 的异步任务执行与恢复基础 |
| Report、PR Body、PR Handoff | 我的二开 | 生成审核材料和人工执行脚本，不自动创建 PR |

### 4.2 当前新增代码

核心包：

```text
backend/packages/harness/deerflow/code_change/
```

关键模块：

```text
models.py             Project / Task / TaskStatus / result models
store.py              JSON 项目与任务存储、JSONL timeline/queue、metrics
state_machine.py      合法状态迁移
repo_scanner.py       源码文件扫描与噪音目录排除
context_retriever.py  路径、摘要和内容关键词 Top-K 召回
workspace.py          每任务 local-copy workspace 与 manifest
patcher.py            路径校验、git apply --check、git apply、diff 统计
sandbox_policy.py     executable allowlist、timeout、日志上限
test_runner.py        shlex.split + shell=False 执行测试
worker.py             入队、消费、执行、retry 和产物编排
report_writer.py      task_report.md 与 audit.json
pr_handoff.py         pr_handoff.json 与人工 draft PR 脚本
cli.py                本地演示入口
```

API 接入：

```text
backend/app/gateway/routers/code_change.py
backend/app/gateway/app.py
```

测试：

```text
backend/tests/code_change/
```

## 5. 当前版本的真实完成度

### 5.1 已完成

- Project 保存仓库路径、仓库 URL、默认分支和测试命令。
- Task 保存需求、状态、上下文、Patch/Test 结果、attempt 和 artifact 路径。
- 合法状态机覆盖创建、排队、检索、应用 Patch、测试、审核、失败和重试。
- FastAPI API 与 CLI 均可创建项目、创建任务、查询报告、查询 metrics 和重试失败任务。
- API 默认只入队，由 Worker 执行长任务；`run_now` 仅用于本地演示。
- 轻量仓库扫描和关键词 Top-K 文件召回。
- 任务独立 local-copy workspace，Patch/Test 不直接修改源仓库。
- Patch 路径防穿越，先 `git apply --check`，成功后再 `git apply`。
- 外部 Patch 使用 `PATCH_RECEIVED -> VALIDATING_PATCH -> APPLYING_PATCH`，不会冒充模型生成行为。
- 测试命令使用 `shell=False`，带可执行文件白名单、timeout 和日志截断；允许白名单 `python3` 对应的受控版本名（如虚拟环境 `python3.12`），拒绝前缀伪装。
- 失败记录 error、日志、attempt，并在次数未耗尽时允许显式 retry。
- 生成 task、timeline、patch、test、policy、manifest、audit、report 和 PR handoff 等证据；成功终态为 `HANDOFF_READY`。
- `.github/workflows/code-change-platform.yml` 专门覆盖 `agent-code-change-platform` 分支，运行定向 Ruff、code_change pytest 和 import smoke；只有推送后真实 Actions run 才能称远端 CI 通过。

### 5.2 当前尚未完成或不能夸大

1. 当前 `code_change` 是挂在 DeerFlow 包和 Gateway 下的独立确定性工作流，尚未注册成 Lead Agent Tool/Skill，也没有进入原生 Thread/Run 事件流。
2. Worker 不调用 LLM 生成代码。当前 Patch 由 API/CLI 的 `patch_text/patch_file` 提供，并明确记录为 `PATCH_RECEIVED`；`GENERATING_PATCH` 只为未来真实 Agent 生成路径保留。
3. `local-copy` 只避免修改源仓库，不限制 CPU、内存、网络和系统调用，不等于 DeerFlow Container Sandbox。
4. `task_queue.jsonl` 是 append-only 单机队列，没有多 Worker 原子抢占、lease、heartbeat、backoff 和 DLQ。
5. JSON 文件存储没有事务与并发写保护，不是生产数据库。
6. 系统没有调用 GitHub API，也没有真的创建 PR；当前正确终态是 `HANDOFF_READY`。`PR_CREATED` 已保留为外部 GitHub 操作确认成功后的下一状态。
7. 代码召回是文件级关键词匹配，不是符号索引、调用图、BM25 或 embedding RAG。
8. 当前没有专门的二开前端页面。

因此最准确的完成度表述是：

```text
项目级代码变更控制面 MVP 已完成；
与 DeerFlow Agent/Skill/Sandbox/Runtime 的深度集成属于最终版 P0。
```

## 6. 我的二开设计框架

最终系统按五个平面设计，避免把所有职责塞进一个 Agent Prompt。

```text
                 ┌──────────────────────────────┐
                 │ 1. Control Plane             │
                 │ Project / Task / State       │
                 │ Policy / Approval / Retry    │
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │ 2. Agent Plane               │
                 │ Lead Agent / Skill / Tool    │
                 │ Plan / Context / Sub-Agent   │
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │ 3. Execution Plane           │
                 │ Sandbox / Workspace          │
                 │ Patch / Test / Resource Rule │
                 └──────────────┬───────────────┘
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
┌───────────────────────┐                 ┌───────────────────────┐
│ 4. Evidence Plane     │                 │ 5. Delivery Plane     │
│ Timeline/Log/Audit    │                 │ Review / PR Handoff   │
│ Metrics/Artifacts     │                 │ Human Approval        │
└───────────────────────┘                 └───────────────────────┘
```

### 6.1 Control Plane：确定性流程

- Project 定义仓库、默认分支、测试命令和安全策略。
- Task 定义需求、状态、attempt、审批和产物引用。
- 状态机决定下一步是否允许执行，Worker 负责调度，API 负责创建和查询。
- 这部分不能完全交给 LLM 决定，因为它承担一致性、权限和审计责任。

### 6.2 Agent Plane：处理不确定推理

- DeerFlow Lead Agent 理解需求、制定计划和决定需要哪些上下文。
- Code-change Skill 固化项目级代码变更流程和安全规则。
- Tools 提供项目查询、上下文检索、提交 Patch、运行验证、读取报告等能力。
- 可将检索、测试分析交给受限 Sub-Agent，但状态迁移仍由 Control Plane 负责。

### 6.3 Execution Plane：隔离副作用

- Patch 和测试必须在任务 Sandbox/Workspace 内执行。
- 执行前验证路径、命令、权限和资源策略。
- 测试失败只影响当前任务，不污染源仓库，也不能直接 push。
- 最终版优先适配 DeerFlow SandboxProvider，而不是长期维护另一套执行抽象。

### 6.4 Evidence Plane：让过程可解释

- 每次状态变化、工具调用、Patch、测试、失败和重试都有时间线。
- artifact 同时服务机器解析和人工审阅。
- 关键指标包括队列深度、各状态数量、成功率、测试耗时、重试次数和 Sandbox 失败率。

### 6.5 Delivery Plane：Human-in-the-loop

- 平台只在验证通过后生成 PR Handoff。
- 人类审核 diff、测试证据、风险和目标仓库后，才允许 push 和创建 draft PR。
- 自动创建 PR 必须通过 GitHub App 最小权限和显式审批；自动 merge 不属于当前项目目标。

## 7. 最终版本完整链路

```text
1. 用户创建 Project，配置 repo、branch、test commands、path policy。
2. 用户通过 CodeOps API 或 DeerFlow 对话创建 CodeChange Task。
3. Control Plane 持久化任务并进入 QUEUED。
4. Worker 获取 lease，创建 DeerFlow Thread/Run 或调用 CodeChange Skill。
5. Agent 读取 Project Context，生成计划并召回相关文件/符号。
6. Agent 生成候选 Patch；Control Plane 保存 Patch artifact，不直接写源仓库。
7. Execution Plane 创建 DeerFlow Container Sandbox/隔离 workspace。
8. 系统校验 Patch 路径并执行 git apply --check，再应用 Patch。
9. 按 Project Policy 运行格式化、静态检查和测试。
10. 失败时把结构化日志反馈给 Agent，最多执行有限次修复；每次 attempt 独立留痕。
11. 验证通过后进入 HANDOFF_READY，生成 diff、测试证据、风险、回滚和 PR body。
12. 人类批准后，由最小权限 GitHub App 创建 draft PR，状态变为 PR_CREATED。
13. 所有状态、事件、artifact 和审批记录可通过 API/前端查询。
```

设计原则：Agent 负责理解、计划和生成候选变更；平台负责权限、状态、执行、证据和交付。

## 8. 状态机最终设计

当前已实现的状态语义为：

```text
CREATED
  -> QUEUED
  -> PLANNING
  -> RETRIEVING_CONTEXT
  -> PATCH_RECEIVED（当前 API/CLI 外部 Patch 路径）
  -> VALIDATING_PATCH
  -> APPLYING_PATCH
  -> RUNNING_TESTS
  -> REVIEWING
  -> HANDOFF_READY

未来 Agent 生成路径：
RETRIEVING_CONTEXT
  -> GENERATING_PATCH
  -> VALIDATING_PATCH
  -> APPLYING_PATCH
  -> RUNNING_TESTS
  -> REVIEWING
  -> HANDOFF_READY

HANDOFF_READY -> PR_CREATED（只有 GitHub 返回真实 PR 后才能进入）

任意执行阶段 -> FAILED
FAILED -> QUEUED（attempt 未耗尽且满足 retry policy）
APPLYING_PATCH/RUNNING_TESTS -> ROLLED_BACK 或 FAILED
```

必须守住的不变量：

```text
任务状态只能按状态机迁移。
一个任务的副作用只发生在自己的 Sandbox/Workspace。
未经验证的 Patch 不能进入 HANDOFF_READY。
未经人工或策略审批不能 push 或创建 PR。
每次 attempt 都必须有独立日志和可追踪输入输出。
重试必须有上限；相同幂等键不能重复创建真实 PR。
Agent 无权绕过 path、command、secret 和 network policy。
PR_CREATED 必须保存真实 provider、repo、PR number 和 URL。
```

## 9. 从当前 MVP 到最终版的任务

### P0：让“基于 DeerFlow 二开”在运行链路上真正成立

1. 将 Code Change 暴露为 DeerFlow Skill + 一组受控 Tools，而不只是一组独立 API。
2. 把 Project/Task ID 注入 DeerFlow Thread/Run context，使 Agent 事件与任务 timeline 可关联。
3. 使用 DeerFlow SandboxProvider 执行 Patch/Test，替代仅 local-copy + 本机 subprocess。
4. 让 Agent 根据需求和召回上下文生成候选 unified diff；当前外部 Patch 输入保留为确定性测试入口。
5. 增加端到端用例：对话创建任务 -> Agent 生成 Patch -> Sandbox 验证 -> 人工批准 -> PR handoff。

### P1：平台工程化

- JSON 存储迁移到 PostgreSQL/DeerFlow Persistence。
- JSONL 队列迁移到 Redis Stream、PostgreSQL queue 或可靠任务系统。
- 增加 lease、heartbeat、指数退避、幂等和 DLQ。
- 增加二开前端：项目列表、任务状态、diff、test log、approval 和 artifact。
- metrics 接 Prometheus，trace 关联 DeerFlow Run 和 CodeChange Task。
- 接 GitHub App 最小权限 OAuth，审批后创建 draft PR。

### P2：检索与规模优化

- 文件级召回升级为 tree-sitter/LSIF/SCIP 等符号索引。
- 结合 BM25、embedding、依赖图和 Git history 做混合召回。
- 大仓库使用 git worktree、sparse checkout 或增量 workspace。
- 对多仓库任务增加依赖关系与分阶段审批，但不扩成无边界多 Agent 平台。

## 10. 最终验收标准

### 当前 MVP 验收

- `compileall` 通过。
- code_change pytest 全部通过；若环境缺少 pytest，必须明确记录“未执行”，不能写“通过”。
- 2026-07-17 本地实测：`backend/tests/code_change` 为 `22 passed`；锁文件对应的 Ruff 0.15.12 对 code_change 包、测试和 Router 共 25 个文件执行 `check` 与 `format --check` 通过；新增 workflow 通过 actionlint 1.7.12。测试环境另报告 1 条 Starlette/httpx 弃用警告，不影响用例结果。远端 GitHub Actions 尚未推送运行，不得提前称 CI 已绿。
- API 能创建 Project、入队 Task、查询状态、report、timeline、metrics 和 retry。
- Patch 在 local-copy workspace 应用，源仓库保持不变。
- 非法 Patch 路径和非白名单命令被拒绝。
- 成功任务生成 Patch/Test/Audit/Report/PR Handoff 全套 artifact。
- 失败任务保留证据并受 max_attempts 限制。

### 最终版验收

- DeerFlow 对话可以通过 Skill/Tool 创建并推进 CodeChange Task。
- Task ID、Thread ID、Run ID 和 trace ID 可以互相查询。
- Agent 能生成候选 Patch，但无法绕过状态机和策略直接修改源仓库。
- Patch/Test 在 DeerFlow Container Sandbox 内执行，并有资源、网络和 secret policy。
- 失败最多自动修复 N 次，每次 attempt 的 prompt、diff、日志和结果可审计。
- `HANDOFF_READY` 有完整 diff、测试、风险和回滚建议。
- 未批准时不能执行 push；批准后创建真实 draft PR，并保存 PR URL/number。
- 重复审批请求不会创建多个 PR。

## 11. 简历写法

### 11.1 当前代码可以真实使用的版本

```text
- 阅读 DeerFlow 2.0 的 Gateway、Agent Factory、Middleware、Skills/Tools、Sub-Agent、Memory 和 Sandbox 架构，并以独立 package + FastAPI Router 方式低侵入扩展项目级代码变更控制面。
- 设计 Project/Task/Timeline/Audit 数据模型和任务状态机，使用 JSONL 队列与 Worker 解耦 API 和 Patch/Test 长任务，支持失败留痕、有限重试和任务指标查询。
- 实现仓库扫描、关键词 Top-K 上下文召回、unified diff 路径校验及 git apply --check，并在任务独立 local-copy workspace 中应用 Patch，避免直接污染源仓库。
- 使用 shell=False、命令白名单、超时和日志截断约束测试执行，生成 task report、audit、test log、PR body 和 PR handoff，为人工 Code Review 提供可追踪证据。
```

### 11.2 P0 深度集成完成后的最终版本

```text
- 基于 DeerFlow 2.0 Agent Harness 二次开发 AI 代码变更平台，通过 CodeChange Skill/Tools 将 Project/Task 上下文接入 Lead Agent、Thread/Run 与事件流，保持对原主链路的低侵入扩展。
- 设计状态机驱动的代码变更控制面，将需求分析、上下文召回、Patch 生成、Sandbox 验证、失败修复、人工审批和 PR 交付拆成可追踪阶段，并关联 timeline、artifact 与 trace。
- 复用 DeerFlow SandboxProvider 隔离 Patch/Test 副作用，通过路径、命令、资源、网络和 secret policy 限制 Agent 权限；对失败任务实施有限 attempt、幂等和审计留痕。
- 构建面向人工审核的 PR Handoff，汇总 diff、测试证据、风险和回滚建议，在审批后通过最小权限 GitHub App 创建 draft PR，形成需求到 PR 的研发闭环。
```

当前没有完成 P0 前，不要使用第二组表述。

## 12. 面试介绍

### 12.1 一分钟版本

```text
我的第二个项目是基于 DeerFlow 2.0 的二次开发。DeerFlow 本身是一个通用 Super Agent Harness，已经有 Lead Agent、Middleware、Skills、Tools、Sub-Agent、Memory、Sandbox 和 Gateway。我没有重写这些底座，而是选择企业代码变更这个场景，增加 Project/Task 控制面和确定性任务流。需求进入后，平台会绑定项目上下文，扫描并召回相关代码，在独立 workspace 中校验和应用 Patch，按策略运行测试，记录状态、timeline、audit 和日志，最后生成 PR handoff 交给人审核。这个项目的重点不是说 AI 一定能写对代码，而是用状态机、沙箱、测试证据和人工审批约束 AI 的不确定性。
```

### 12.2 三分钟结构

按下面四段讲：

1. 原版理解：DeerFlow 用 Lead Agent + Middleware 组织模型、工具、记忆、沙箱和 Sub-Agent，通过 Gateway/Runtime 管理 Thread、Run 和事件流。
2. 问题发现：通用 Agent 能执行任务，但企业代码变更缺少项目归属、固定状态、强制测试、审计和 PR 权限边界。
3. 二开设计：不侵入 Lead Agent，先新增 Project/Task、Worker、Patch/Test、Workspace、Policy、Artifact 和 Gateway API，形成确定性控制面。
4. 边界演进：当前是可运行 MVP；最终通过 Skill/Tools、Thread/Run context 和 DeerFlow Sandbox 深度集成，PR 必须人工批准后创建。

### 12.3 为什么不直接做一个 Cursor

```text
Cursor 更偏个人 IDE 内的交互式编码体验，我做的是服务端研发流程控制。它关心任务属于哪个项目、执行到哪一步、Patch 在哪里验证、失败如何复盘、谁有权创建 PR，以及证据能否审计。两者不是同一个产品层次。
```

### 12.4 为什么不让 Agent 直接改仓库

```text
模型输出具有不确定性，而且仓库写入、命令执行和 push 都是高风险副作用。因此 Agent 只生成候选计划和 Patch，真正的路径校验、状态迁移、Sandbox 执行、测试和审批由确定性平台控制。测试通过也不等于业务一定正确，所以最终仍保留人工 Code Review。
```

## 13. 高频追问与回答要点

1. Agent、Tool、Skill、Middleware 有什么区别？
   - Agent 负责循环决策；Tool 是可调用动作；Skill 是任务知识和工具策略；Middleware 在运行时注入上下文、限制或处理错误。

2. 为什么状态机不能交给 LLM？
   - 状态决定副作用和权限，需要确定性、可重放、可审计；LLM 只能提出下一步，平台校验是否允许。

3. 为什么 API 与 Worker 分离？
   - Patch、依赖安装和测试耗时长，HTTP 只负责提交与查询，Worker 执行并通过状态暴露进度。

4. 为什么 `git apply --check` 后还要测试？
   - check 只证明 diff 能套用，不证明语法、单测、业务和安全正确。

5. `shell=False` 是否就绝对安全？
   - 不是。它降低 shell 注入风险，但执行程序仍可能读写文件、联网或消耗资源，所以还需要容器 Sandbox、资源和网络策略。

6. local-copy 为什么不算真正 Sandbox？
   - 它只隔离工作目录，没有隔离进程、系统调用、网络、CPU、内存和宿主机其他路径。

7. 为什么代码检索不能只用 embedding？
   - 代码还依赖符号定义、引用、调用关系、类型和 Git 变化，最终应混合路径/关键词、符号索引、BM25、embedding 和依赖图。

8. Retry 会不会反复生成错误代码？
   - 必须限制 attempt，并让每次修复基于结构化失败证据；同一错误重复时触发 loop detection 或转人工。

9. 如何避免创建重复 PR？
   - 审批操作带幂等键，数据库保存 task 到 PR 的唯一映射，创建后记录 provider PR number/URL，重试先查询远端状态。

10. 当前最明显的不足是什么？
    - 目前工作流尚未进入 DeerFlow 原生 Agent/Runtime/Sandbox，Patch 仍由外部提供，存储和队列也是单机 MVP；这正是最终 P0/P1 的演进方向。

## 14. 学习准备路线

### 第 1-3 天：DeerFlow 原架构

- 第 1 天：读 README、Gateway app 和目录结构，画客户端到 Gateway 的入口图。
- 第 2 天：读 `agents/factory.py`、`lead_agent/agent.py` 和 ThreadState，理解 Agent 如何组装。
- 第 3 天：选 5 个 Middleware，解释各自在模型前后做什么以及为什么有顺序。

### 第 4-5 天：扩展机制

- 第 4 天：读 Tools、Skills、MCP，分别举一个适合场景。
- 第 5 天：读 Sub-Agent、Sandbox、Memory，说明它们的边界和失败风险。

### 第 6-8 天：自己的二开

- 第 6 天：读 models/state_machine/store，手画状态机和 artifact 目录。
- 第 7 天：读 scanner/retriever/workspace/patcher，推演路径穿越和源仓库污染风险。
- 第 8 天：读 test_runner/worker/router，解释 `shell=False`、队列、retry 和 API 边界。

### 第 9-10 天：执行一次完整 Demo

- 自己创建临时仓库和 Patch。
- 跑成功、Patch 失败、测试失败、非法命令和 retry 五个场景。
- 逐个解释 task.json、timeline、audit、test.log、policy、manifest 和 pr_handoff。

### 第 11-12 天：生产化设计

- 学习 PostgreSQL 任务表、Redis Stream/数据库队列、lease、heartbeat、backoff 和 DLQ。
- 学习 Docker Namespace/Cgroup、网络隔离、Secret 注入和 GitHub App 权限模型。

### 第 13-14 天：面试表达

- 分别录制 1 分钟、3 分钟和 10 分钟讲解。
- 练习先说“原版是什么”，再说“缺什么”，最后说“我怎么低侵入扩展”。
- 每个能力都能指出代码位置和验证证据；不熟悉的上游模块不要假装自己实现过。

## 15. 代码阅读顺序

其他 AI 或本人应按以下顺序阅读：

```text
README_zh.md
docs/AI_HANDOFF_DEERFLOW_FINAL.md
backend/app/gateway/app.py
backend/packages/harness/deerflow/agents/factory.py
backend/packages/harness/deerflow/agents/lead_agent/agent.py
backend/packages/harness/deerflow/tools/
backend/packages/harness/deerflow/skills/
backend/packages/harness/deerflow/subagents/
backend/packages/harness/deerflow/sandbox/
backend/packages/harness/deerflow/runtime/
backend/packages/harness/deerflow/code_change/models.py
backend/packages/harness/deerflow/code_change/state_machine.py
backend/packages/harness/deerflow/code_change/store.py
backend/packages/harness/deerflow/code_change/worker.py
backend/packages/harness/deerflow/code_change/{workspace,patcher,test_runner}.py
backend/packages/harness/deerflow/code_change/{report_writer,pr_handoff}.py
backend/app/gateway/routers/code_change.py
backend/tests/code_change/
```

## 16. 给后续 AI 的执行指令

```text
1. 先区分 DeerFlow 上游能力、当前二开能力和最终目标。
2. 不要把 code_change 说成已经接入 Lead Agent；修改前先核对真实调用链。
3. 优先复用 DeerFlow 的 Skill/Tool/Sandbox/Runtime 扩展点，避免复制一套平行框架。
4. Control Plane 掌管状态、权限和审计，LLM 不得直接决定高风险副作用。
5. 所有 Patch 必须先做路径与格式校验，再在任务 Sandbox 内应用和测试。
6. 所有命令执行都要考虑 allowlist、timeout、资源、网络、secret 和日志上限。
7. PR 创建属于外部高风险操作，必须显式授权、最小权限、幂等和人工审批。
8. 修改状态机时同步更新模型、迁移、API、前端、测试和文档。
9. 不编造测试结果；环境缺依赖时明确写未执行及原因。
10. 完成任务后说明修改内容、架构影响、验证证据和剩余边界。
```
