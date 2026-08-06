# 06 为什么二次开发 DeerFlow

## 原版已经很强，为什么还要改

DeerFlow 解决的是通用 Agent Harness：让模型使用 Tool、Skill、Memory、Sub-Agent 和 Sandbox 完成开放式任务。开放式能力适合研究和通用助手，却不等于一个团队可以直接接受的代码变更流程。

代码修改有更严格的业务约束：

- 每个任务必须属于某个用户和项目。
- 必须固定源码基线，避免“测的版本”和“交接的版本”不同。
- 同一任务不能被多个 Worker 无保护地同时完成。
- Patch 必须限制路径、大小和格式。
- 测试命令必须由服务端批准。
- 模型输出、Patch、测试、审批需要形成一条审计链。
- 测试通过后仍要等人确认，不能自动合并。

这些不是再写一段 prompt 就能解决的，需要状态机和控制面。

## 二开的设计原则

### 1. 概率性和确定性分层

Agent 负责需要理解与推理的部分：检索上下文、提出候选 diff、解释理由。Worker 负责可重复验证的部分：检查路径、应用 Patch、执行测试模板、记录退出码。

这样失败时能判断是“模型没有提交候选”“Patch 无法应用”还是“测试失败”，而不是只得到一句模糊的 Agent 报错。

### 2. 权限按最小需要授予

生成 Patch 不需要执行命令，所以 Agent 没有 bash。普通用户不需要领取队列，所以 Worker API 使用内部身份。浏览器不需要知道 Secret，所以内部 token 只在服务端。

### 3. 状态必须能恢复

请求超时或 Worker 宕机后，Task 仍应留在持久层。claim、lease、heartbeat 和 fencing 用于判定谁有权继续写结果。人工审批也作为状态，而不是一条不可靠的聊天消息。

### 4. 每个结论都要有证据

“Patch 已应用”对应 `git apply` 退出码与日志；“测试通过”对应固定 argv、exit code 和 test.log；“已批准”对应 reviewer、时间和审阅文件。没有证据就不升级状态。

## 为什么不用 GitHub Copilot 类产品当项目

使用现成产品能解决实际问题，但不容易展示你对任务状态、执行隔离、可靠队列和审批控制的设计。这个二开项目的价值在平台层，而不是和成熟代码模型比生成质量。

## 为什么不从零写一个 Agent 框架

秋招个人项目时间有限。重写 Thread、Tool 调用、模型 Provider、SSE 和 Sandbox 抽象会产生大量基础设施代码，却不一定体现业务判断。复用成熟上游，再明确贡献边界，更接近公司的二次开发和平台集成工作。

前提是你真的能读懂上游关键结构，不能只改外层 API。至少要会讲
`create_deerflow_agent`、Tool 调用循环、Thread/Run 和 SandboxProvider 的职责。

## 为什么当前先做单条纵向链路

项目没有同时做自动 Issue 分析、代码评审、依赖升级、文档生成和全自动 PR。只做一条需求到候选 Patch、测试、报告和审批的闭环，更容易把安全、失败恢复和评测做实。

面试区分度通常来自一个链路被问深以后仍能回答，而不是 README 里列了十种互不连通的 Agent。

## 设计框架

```text
输入层：认证用户、Project、requirement
理解层：DeerFlow Agent + 请求级代码检索 Tool
边界层：typed submit_patch、路径/大小校验
调度层：Task 状态机、Queue、claim/lease/fencing
执行层：固定源码基线、Workspace、Patch、测试模板
治理层：日志、报告、审计、人工审批、PR handoff
评测层：固定任务集、成功率、安全拦截、耗时
```

这个框架也是你回答“为什么二开、怎么设计”的主干。

## 本章代码阅读任务

阅读顺序：先确认上游通用入口，再找上游没有覆盖的领域对象、执行编排和人工门禁。

1. 读 `backend/packages/harness/deerflow/agents/factory.py::create_deerflow_agent`，列出它解决的模型、Tool、Middleware、state schema、checkpointer 和 Agent name 组装。
2. 读 `backend/packages/harness/deerflow/code_change/models.py` 的 `Project`、`TaskStatus`、`PatchMode`、`Task`，圈出 owner、source commit、attempt、claim、Patch/Test 和审批字段。
3. 读 `backend/packages/harness/deerflow/code_change/worker.py::execute_task`，在纸上分出理解层、边界层、执行层和治理层，并为每层写函数名。
4. 读 `review.py::review_task` 与 `report_writer.py::write_reports`，确认人工门禁和审计证据由状态与文件实现。

看到什么程度：不用“为了更强”这类空话，能用固定基线、测试模板、可靠领取和人工审批四个具体缺口回答为什么二开。

暂不要求：不追每种 Middleware，也不展开 `git apply`、subprocess 和前端样式。先掌握复用边界与领域设计。

验收动作：画“上游已有”和“领域新增”两列，把设计框架七层中的每个当前组件放入正确列；目标架构另列，不混入当前实现。

## 本章自测

1. 为什么不能只改 system prompt？
2. 概率性与确定性怎样分层？
3. 为什么不从零写 Agent 框架？
4. 这个二开真正能展示什么能力？
5. 为什么只做一条纵向链路？
6. 设计框架七层分别是什么？

## 参考答案

1. prompt 不能原子领取任务、限制 HTTP 命令、固定 Git commit、强制路径校验或写审批状态。这些约束需要领域模型和确定性代码。
2. Agent 搜索、阅读并提出候选 diff；Worker 负责路径校验、`git apply`、固定测试、状态迁移与报告。模型文字不能替代退出码和文件证据。
3. Thread/Run、Tool 循环、模型 Provider、SSE 和 Sandbox 抽象已由 DeerFlow 提供。复用它们能把时间放在代码变更控制面。
4. 它展示领域建模、后台任务可靠性、安全边界、确定性验证、人工门禁和生产化演进判断，不是与成熟代码模型比较生成质量。
5. 一条需求到 Patch、测试、报告、审批的链路可以把失败窗口和证据做实。多个不连通功能经不起深入追问。
6. 输入层接用户、Project、requirement；理解层运行 Agent 与检索；边界层接 typed Patch；调度层维护 Task、Queue、lease；执行层固定基线并测试；治理层写报告和审批；评测层用固定任务衡量结果。
