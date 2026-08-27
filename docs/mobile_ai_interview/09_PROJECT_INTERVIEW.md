# 09 项目介绍、简历口径与高频追问

## 问题 1：请用两分钟介绍 CodeRepair

### 面试官问

介绍一下你这个基于 DeerFlow 二次开发的项目。

### 30 秒回答

这是我基于 DeerFlow 二次开发的 Anchored Branch Context 项目。我复用上游 Thread、Run、Tool、Checkpoint、SSE 和前端工作台，新增局部 Anchor、Main/Child 隔离、受预算 Context Builder、双栏 UI 和三策略实验。用户围绕长回答中的一句或代码片段创建 Child Thread，Branch 的多轮讨论和工具调用不写 Main。Code Change 是展示 Tool/Sandbox 能力的 Demo，不是核心创新。

### 详细回答

项目起因是我发现通用聊天 Agent 能回答代码问题，但"模型说修好了"和"代码确实可以交付"之间缺少一条工程链。模型输出有概率性，代码变更又有权限和副作用，所以我没有让通用 Agent 直接拿完整 shell 操作仓库，而是设计了模型提案、程序验证、人工审批的三段边界。

用户先登记 Project，包括仓库和服务端 test profile，再创建 external 或 agent 模式的 Task。Task 固定当前 Git commit并进入队列。Worker 用 claim、lease、heartbeat 和 claim id 领取任务，在 Task Artifact 下导出 Workspace。

Agent 模式会构建一个最小 DeerFlow graph，只暴露代码搜索、限量读文件和类型化 Patch 提交三个 Tool。模型提交 unified diff 后，流程与 external 模式汇合。系统检查变更路径，执行 `git apply --check`，在 Workspace 中应用 Patch，运行白名单测试命令，并保存 Patch、日志、报告和审核材料。测试通过只到 HANDOFF_READY，人工批准才到 APPROVED。

用户选择主回答的一段文本后，系统保存 message ID、offset、Anchor 原文和可选代码引用，校验后创建 Child Thread。每次 Run 按预算组合主任务摘要、Anchor、相关主线内容和 Branch History。关闭 Branch 只结束 Child，Main 不变。

当前版本适合本地演示和面试验证。Store 与队列是单机文件实现，Workspace 是 local-copy，没有生产容器隔离，也没有自动创建真实 PR。我会把这些限制和目标架构分开讲。

### 结合当前 CodeRepair 源码

介绍时只需要记住六个入口：

- HTTP 控制面：`app/gateway/routers/code_change.py`
- Worker 编排：`deerflow/code_change/worker.py`
- Patch Agent：`deerflow/code_change/agent_patch.py`
- Workspace 和测试：`workspace.py`、`patcher.py`、`test_runner.py`
- 状态与领取：`state_machine.py`、`store.py`
- Anchored Branch：`routers/anchored_branch.py`、`anchored_branch/context.py`

### 技术选型与替代

项目的主要取舍是自主性和可控性。直接给通用 Agent shell 权限更像完整 Coding Agent，但个人项目很难证明权限、安全和回滚。我选择最小 Tool 加确定性 Worker，方便说明每个失败阶段和证据。

### 边界与追问

不要在两分钟介绍里展开所有 DeerFlow Middleware。面试官对哪个点感兴趣，再进入对应答案。开场一定先区分上游复用和个人新增。

## 问题 2：为什么选择二次开发 DeerFlow，而不是从零写 Agent

### 面试官问

这个项目为什么非要基于 DeerFlow？自己写一个 ReAct 循环不是更能体现能力吗？

### 30 秒回答

自己写最小 ReAct 循环并不难，但 Thread、Run、Checkpoint、流式事件、Tool、中间件、Sandbox 接口和前端交互会重复造轮子。我的目标不是证明能写一个 while 循环，而是研究如何把代码变更接入真实 Agent Runtime，并处理状态、权限、执行和审核。基于 DeerFlow 二开还能体现我阅读复杂开源项目、识别扩展边界和复用已有基础设施的能力。

### 详细回答

我先区分学习目的和项目目的。为了理解 Agent Loop，我需要能解释 messages state、模型节点、Tool 节点和停止条件，甚至可以手写最小循环。但项目要提供完整交互和持久运行，只写循环不够。

DeerFlow 已经有 Gateway、Lead Agent、Thread/Run、Checkpoint、StreamBridge、SSE、Tool 和 Middleware 链。Anchored Branch 如果另建消息表和流式系统，会与上游状态重复。复用 Child Thread 和现有 Run 后，新增代码只关注 Anchor、Context Isolation 和 Context Engineering。

Code Change 也没有直接复用全权限 Lead Agent，而是使用上游提供的 `create_deerflow_agent` 工厂构建最小 Agent。也就是说，复用不是照搬，我仍然根据风险重新选择 Tool 和 Middleware。

二次开发的难点是找到正确接缝：哪些能力来自上游，哪些领域状态需要新增，怎样不破坏现有 Runtime。这类工作与公司维护内部平台很接近。

### 结合当前 CodeRepair 源码

- 复用 Agent 工厂：`agents/factory.py::create_deerflow_agent`。
- 复用 Thread/Run/SSE：`routers/anchored_branch.py::stream_branch_run`。
- 新增受限 Tool：`code_change/agent_patch.py`。
- 新增领域状态：`code_change/models.py` 和 `anchored_branch/models.py`。

### 技术选型与替代

如果业务只需要一次固定模型调用，没有长对话、工具循环和流式输出，直接调用模型 SDK 更简单。选择 DeerFlow 是因为这里确实复用了 Agent Runtime，而不是为了给简历增加框架名。

### 边界与追问

二次开发不等于上游全部代码都是个人贡献。面试官追问某个模块时，要先说明它来自上游，再说明自己的接入点和修改理由。

## 问题 3：简历应该怎样写才专业又不过度

### 面试官问

请给出可以放进简历的三条项目描述，并解释证据。

### 30 秒回答

第一条写架构和贡献边界，第二条写受限 Agent 与确定性验证，第三条写状态可靠性和 Anchored Branch。每条都落到当前类、状态或测试证据，不写生产级、全自动 PR、在线修复率或容器沙箱。

### 详细回答

可以使用下面三条：

```text
基于 DeerFlow 二次开发细粒度 Anchored Branch，复用 Thread、Run、Tool、Checkpoint 与 SSE Runtime，新增局部锚点、Main/Child 隔离、双栏交互和有预算的 Context Builder。

设计受限 Patch Agent，仅开放 search、read 和 typed submit Tool；将模型生成与执行解耦，在固定 Git commit 的独立 Workspace 中完成路径校验、git apply --check、服务端测试 profile、超时进程组清理和报告生成。

实现 Project/Task owner 隔离、状态机、原子 claim、lease、heartbeat 和 fencing；建立 20 case external Patch 确定性回归套件，覆盖成功、上下文冲突、路径穿越和测试失败。
```

第一条的证据是两个新增 package、FastAPI Router 和前端交互。第二条的证据是 `agent_patch.py`、Workspace、Patcher 和 TestRunner。第三条的证据是 Store、StateMachine、Evaluation 和对应单元测试。

如果简历空间只有两条，可以把 Anchored Branch 单独压缩为一句：

```text
实现 Anchored Branch，将主回答选区的 message ID、offset 和原文映射为独立 Child Thread，按预算组合主任务摘要、相关上下文和 Branch History，关闭时不修改主线。
```

### 结合当前 CodeRepair 源码

写进简历前按这个证据顺序检查：

```text
当前函数或数据结构存在
→ 有测试或可运行演示
→ 证据测到的范围与表述一致
→ 明确上游复用和个人新增
```

### 技术选型与替代

简历不需要列出全部 Python 库。专业感来自职责、问题和约束，不是框架数量。比如"模型提案和确定性执行解耦"比"使用 LangChain、LangGraph、FastAPI、Pydantic"更能说明设计。

### 边界与追问

不要使用以下表述：

- 自研 DeerFlow Agent 框架。
- 生产级分布式任务调度。
- 容器级安全沙箱。
- Agent 自动修复成功率 50%。
- 自动创建并合并 GitHub PR。

## 问题 4：如果面试官质疑项目是 AI 生成的代码，怎么回答

### 面试官问

这个项目是不是主要由 AI 帮你写的？你真正掌握了什么？

### 30 秒回答

我使用过 AI 辅助检索、生成和修改，但我不把生成量当成个人能力。我能对照源码讲清完整调用链、关键状态和失败窗口，也能解释为什么限制 Tool、为什么固定 commit、为什么测试通过只到 HANDOFF_READY。我用测试和边界表核对每条简历描述。面试现场如果让我修改状态迁移、增加负向测试或分析 Worker 重复领取，我可以从当前结构继续实现。

### 详细回答

公司开发本来就会使用文档、开源代码和 AI 工具，关键是有没有代码所有权。代码所有权至少包括四件事。

第一，能从入口走到结果。例如从 Task HTTP 请求讲到 Pydantic、Store、Queue、claim、Workspace、Agent、Patch、测试和 Review。

第二，能解释数据结构。Task 为什么同时有 status、attempt、claim id、source commit、PatchResult 和 TestResult；BranchRecord 为什么引用 Child Thread 而不复制消息。

第三，能分析失败。Worker 在 lease 过期后恢复会怎样，Patch 应用后崩溃会不会污染源仓库，测试超时如何杀子进程，为什么文件 Store 不能直接扩成多机。

第四，能诚实划边界。固定 20 case 没测在线 Agent，local-copy 不是容器，handoff 不是 PR。

我准备项目时不会只背框架定义。我会亲自运行 targeted test，阅读失败日志，写一条负向 case，并能在纸上画出控制面和执行面。

### 结合当前 CodeRepair 源码

面试前至少要能脱离文档说出这些函数：

- `create_task`、`execute_task`、`run_next_task`
- `claim_next_task`、`renew_task_claim`、`save_task`
- `build_code_change_tools`、`generate_patch_with_agent`
- `prepare_workspace`、`apply_patch_text`、`run_tests`
- `review_task`
- `BranchContextBuilder.build`、`apply_branch_decision`

### 技术选型与替代

如果面试官让现场改代码，先复述不变量，再动手。例如新增状态时先修改 Enum、Transition、序列化和测试，而不是只改一个 if。这样能体现你理解系统约束，而不只是记住路径。

### 边界与追问

不要回答"代码都是我一行一行手写的"来回避问题。更可信的回答是说明 AI 参与了什么、自己如何验证，以及能够现场解释和修改哪些核心模块。

## 问题 5：面试前怎样验收自己真的会了

### 面试官问

你认为掌握这个项目的最低标准是什么？

### 30 秒回答

我给自己五个验收项：两分钟讲清上游与二开边界；画出 external 和 agent 两条任务链；解释 claim、lease、heartbeat 和 fencing；分析三个故障窗口；准确说明 20 case、Workspace 和 PR 的能力边界。做到这些后，再补 Python async、FastAPI、LLM Tool Calling 和 LangGraph 八股。

### 详细回答

第一遍只背项目骨架：

```text
Gateway 控制面
→ Task 与状态机
→ Worker 领取
→ pinned Workspace
→ Agent 或 external Patch
→ validate / apply / test
→ report / review
```

第二遍补 AI 术语：LLM 是 Token 预测模型，Agent 是模型与 Tool 的状态循环，LangGraph 提供状态图和 Checkpoint，DeerFlow 提供产品级 Runtime。

第三遍补可靠性：owner、allowed roots、test profile、claim、lease、heartbeat、fencing、timeout、process group 和 HITL。

第四遍练故障题：模型不 submit、Patch 路径逃逸、`git apply --check` 失败、测试超时、Worker lease 过期、人工 request changes。

最后做一次反向验收。任何一句回答后都追问：对应哪个文件，当前真的实现了吗，测试证明了什么，生产版还缺什么。如果无法回答，就先删掉夸大的句子，再回源码确认。

### 结合当前 CodeRepair 源码

建议自己运行并查看：

```text
backend/tests/code_change/test_agent_patch.py
backend/tests/code_change/test_worker.py
backend/tests/code_change/test_store.py
backend/tests/code_change/test_task_runner.py
backend/tests/code_change/test_anchored_branch.py
backend/tests/code_change/test_evaluation.py
```

测试名称是证据入口，但只看通过结果不够。至少选一条用例读 Arrange、Act、Assert，弄清它制造了什么输入、调用哪个函数、断言哪个状态。

### 技术选型与替代

背诵只是第一阶段。更可靠的准备方式是让同学随机抽一道追问，要求你在两分钟内画数据流，再打开源码定位函数。项目面试通常会从口述进入代码细节。

### 边界与追问

不需要背 LangGraph 内部每个节点实现，也不需要背所有 DeerFlow Middleware。你的基本盘仍是后端：入口、状态、存储、并发、故障、权限、测试和演进。
