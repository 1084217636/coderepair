# CodeRepair AI 工程与 Agent 开发学习手册

这是本仓库唯一的顺序学习入口。目标不是只会介绍一个二开功能，而是达到 AI 应用/Agent 工程岗所需的基础水平：理解 LLM 调用与上下文，能读 Agent Runtime，能设计 Tool、Middleware、Memory、Sub-Agent、安全边界与评测，并能用 CodeRepair 的真实实现回答追问。

## 学习主线

```text
Python async / HTTP / SSE
→ LLM messages / token / structured output
→ DeerFlow Runtime / LangGraph State
→ Tool / Middleware / Context / Memory / Skill / Sub-Agent
→ Repository Retrieval / Patch Agent / Workspace Test
→ Anchored Branch / Context Isolation / Context Experiment
→ Security / Evaluation / Observability / Debugging
→ Code Map / Resume / Interview
```

## 上游与个人实现

- 上游 DeerFlow：Thread、Run、Checkpoint、Agent factory、通用 Tool/Middleware、Memory、Skill、Sub-Agent、SandboxProvider、StreamBridge/SSE 和工作台。
- 个人新增：细粒度 Anchor、Main/Child 隔离、Branch Context Builder、双栏 UI 和三策略实验；Code Change 控制面与受限 Patch Agent 作为 Demo。
- 未完成：生产级容器执行、在线模型修复率、真实人工接受率、真实 GitHub PR Provider 和多机共享任务控制面。

## 唯一阅读顺序

### 第一阶段：运行基础与 LLM 基础

1. [00 从这里开始](00_START_HERE.md)
2. [01 项目定位与能力边界](01_PROJECT_BOUNDARY.md)
3. [02 跑通两个最小演示](02_FIRST_DEMO.md)
4. [03 Python、async、FastAPI 与流式响应](03_PYTHON_ASYNC_HTTP.md)
5. [04 LLM API、消息、Token 与结构化输出](04_LLM_FOUNDATIONS.md)

### 第二阶段：Agent Harness 基础

6. [05 DeerFlow 总体结构与一次真实请求](05_DEERFLOW_ARCHITECTURE.md)
7. [06 Agent Loop、LangGraph State 与 Checkpoint](06_AGENT_LOOP_LANGGRAPH.md)
8. [07 Tool Calling、Schema 与最小权限](07_TOOL_CALLING.md)
9. [08 Middleware 与 Context Engineering](08_MIDDLEWARE_CONTEXT.md)
10. [09 Memory、Skill、规划与 Sub-Agent](09_MEMORY_SKILLS_SUBAGENTS.md)

### 第三阶段：Coding Agent 实现

11. [10 仓库扫描、检索与代码上下文](10_REPOSITORY_RETRIEVAL.md)
12. [11 受限 Patch Agent 的完整链路](11_CODING_AGENT.md)
13. [12 Workspace、unified diff 与测试门禁](12_WORKSPACE_PATCH_TEST.md)

### 第四阶段：Anchored Context 实现

14. [13 Anchored Branch：从回答片段创建 Child Thread](13_ANCHORED_BRANCH.md)
15. [14 BranchContextBuilder：预算、裁剪与提示注入](14_BRANCH_CONTEXT.md)
16. [15 Code Change Task 状态机与 Human-in-the-loop](15_DECISION_CONTROL_PLANE.md)

### 第五阶段：工程质量与求职

17. [16 Agent 安全、Guardrail 与 Sandbox 边界](16_SECURITY_GUARDRAILS.md)
18. [17 Agent 评测、可观测性与成本](17_EVALUATION_OBSERVABILITY.md)
19. [18 Agent 故障定位与恢复](18_FAILURE_DEBUGGING.md)
20. [19 完整调用链与源码地图](19_END_TO_END_CODE_MAP.md)
21. [20 AI 工程岗简历、面试题与六周计划](20_RESUME_STUDY_PLAN.md)
22. [21 AI 辅助 Agent 开发：真实故障、工作差异与面试口径](21_AI_ASSISTED_AGENT_DEVELOPMENT.md)

## 怎样学才算有效

每章末尾都有源码阅读任务、自测与参考答案。代码阅读任务中的每个文件或相邻函数组都要单独向 AI 提问，不要一次要求解释整章。每章已经提供可复制的问题，回答必须结合当前仓库，按调用者、输入、代码块、状态变化、失败分支和学习停止条件展开，并在结尾附带答案的自测。只给路径、概念列表或下一篇链接的回答不算完成。

每次学习按这个顺序进行：复制当前小问题，得到分段讲解，亲自打开源码核对，关闭回答复述调用链，再完成自测。当前文件能说清后才进入下一个。整个手册至少完成一次可运行演示、一张手画调用链、一条自己补的负向测试、一份 Agent eval，以及三篇来自真实开发过程的故障复盘。判断一句话能否写进简历，只问：它来自上游还是个人新增；当前代码是否存在；证据究竟证明了什么。

`docs/coderepair/` 只保留开发阶段记录，不再提供另一套学习编号。
