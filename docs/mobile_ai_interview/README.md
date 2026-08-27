# CodeRepair 手机背诵手册

这套手册给第一次学习 AI 项目的 Go 后端开发者使用。它不是源码阅读任务，也不会要求你把问题复制给 AI。每一节都已经写成可以直接口述的面试答案。

先按顺序读一遍，再循环背诵。走路时一次只看一个问题，先遮住详细回答，口述 30 秒版本，然后再核对源码细节和边界。

## 阅读顺序

1. [01 Go 后端开发者怎样理解 AI 平台](01_GO_BACKEND_TO_AI.md)
2. [02 LLM、Agent、Tool、LangGraph 与 DeerFlow](02_LLM_AGENT_DEERFLOW.md)
3. [03 FastAPI 控制面与任务入口](03_CONTROL_PLANE_TASK_API.md)
4. [04 受限 Patch Agent 与代码检索](04_PATCH_AGENT_RETRIEVAL.md)
5. [05 Workspace、Patch 校验与确定性测试](05_WORKSPACE_PATCH_TEST.md)
6. [06 状态机、任务领取、人工审核与 PR 边界](06_STATE_QUEUE_HITL.md)
7. [07 Anchored Branch Context](07_ANCHORED_BRANCH_CONTEXT.md)
8. [08 安全、评测、故障与演进](08_SECURITY_EVALUATION_FAILURE.md)
9. [09 项目介绍、简历口径与高频追问](09_PROJECT_INTERVIEW.md)

## 先记住项目边界

上游 DeerFlow 已经提供通用 Agent、Thread、Run、Checkpoint、Tool、Middleware、SandboxProvider、StreamBridge、SSE 和 Next.js 工作台。

个人二次开发集中在两块：

```text
deerflow.code_change
受控代码变更任务、受限 Patch Agent、Workspace、校验、测试、审核材料

deerflow.anchored_branch
从主对话选择 Anchor、创建独立 Child Thread，并用受预算的 Anchored Context 继续局部追问
```

当前没有完成的能力：

- 没有自动创建或合并真实 GitHub PR。
- `local-copy` 不是生产容器沙箱。
- 文件 Store 和 JSONL 队列不支持多机共享。
- 固定 20 case 没有调用在线模型，不能证明 Agent 自动修复率。
- 没有真实用户接受率数据。

面试时可以说"基于 DeerFlow 二次开发"，不能说"从零自研 DeerFlow"或"生产级全自动代码修复平台"。

## 每道题怎么背

每道题固定有六部分：

1. 面试官问：真实提问方式。
2. 30 秒回答：先给结论，适合第一轮回答。
3. 详细回答：面试官继续追问时展开。
4. 结合当前源码：说出关键文件、类和函数。
5. 技术选型与替代：解释为什么这样做，以及还有什么方案。
6. 边界与追问：主动控制项目口径，并准备下一层追问。

背诵标准不是逐字复读。你需要做到：关键词不丢，调用链不错，个人贡献不夸大，能说明一个设计为什么存在。
