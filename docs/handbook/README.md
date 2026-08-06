# CodeRepair / DeerFlow 二开学习手册

> 唯一学习主线：只按本目录 `00_START_HERE.md` 到 `20_STUDY_PLAN.md` 的编号顺序阅读。此前新增的 `docs/learning/` 摘要已合并到本手册，不再单独维护。

这套手册假设你只会 Python 基本语法。第一次读时不要从状态机、沙箱或 Agent
评测开始，也不要试图一天背完所有类名。先把“用户提出改代码需求后，系统怎样安全地产生一个候选变更”这条主线讲顺，再回头补每个模块。

## 先明确项目是什么

这个仓库以字节跳动开源的 DeerFlow 2.0 为底座。上游 DeerFlow 已经提供通用 Agent、
Tool、Skill、Middleware、Thread/Run、Memory、SandboxProvider 和 Next.js 工作台。本项目的个人二开是
Code Change。它支持外部 Patch 和 Agent Patch 两种 Task 模式。Agent 模式由 Worker 调用
`generate_patch_with_agent`，模型只能搜索、按行读代码并通过 typed Tool 提交候选；两种模式随后共用
固定源码 Workspace、Patch 校验、测试、报告和人工审批链路。fake-model 测试能证明 Agent 图和 Tool
协议真实接通，但不能代表在线模型在真实仓库中的修复成功率。

面试时必须分开说：

- “上游已有”：DeerFlow 通用 Agent Harness 的基础设施。
- “我新增”：`deerflow.code_change`、Code Change API、受控 Patch Agent 组件、任务状态机、
  owner 隔离、claim/lease/heartbeat/fencing、测试模板、报告与审批控制台。
- “没有完成”：自动合并、真实生产集群、任意仓库的高成功率自动修复，以及真实用户的人工接受率。

## 建议阅读顺序

| 阶段 | 章节 | 读完应当会什么 |
| --- | --- | --- |
| 第一次认识 | 00～03 | 能运行演示，知道 HTTP、FastAPI 和进程分别是什么 |
| 看懂底座 | 04～06 | 分清 DeerFlow 上游结构和个人二开动机 |
| 看懂核心代码 | 07～14 | 能从请求讲到 Agent、Worker、测试、报告和审批 |
| 学可靠性 | 15～17 | 能解释多机边界、CI/评测和常见故障 |
| 准备面试 | 18～20 | 记住主要类与函数，写简历，做闭卷自测 |

逐章阅读：

1. [00 使用方式与学习目标](00_START_HERE.md)
2. [01 项目解决什么问题](01_PROBLEM_AND_SCOPE.md)
3. [02 跑通第一个演示](02_FIRST_DEMO.md)
4. [03 Python、HTTP 与 FastAPI 基础](03_PYTHON_HTTP_FASTAPI.md)
5. [04 原版 DeerFlow 总体结构](04_DEERFLOW_ARCHITECTURE.md)
6. [05 Agent、Tool、Skill、Middleware 与 Sub-Agent](05_AGENT_CONCEPTS.md)
7. [06 为什么二次开发](06_WHY_FORK_DEERFLOW.md)
8. [07 Project、Task 与状态机](07_PROJECT_TASK_STATE.md)
9. [08 Queue、Worker、claim、lease 与 fencing](08_QUEUE_WORKER_LEASE.md)
10. [09 仓库扫描与上下文检索](09_REPOSITORY_RETRIEVAL.md)
11. [10 真实 Patch Agent 链路](10_PATCH_AGENT.md)
12. [11 unified diff、Workspace 与测试](11_PATCH_WORKSPACE_TEST.md)
13. [12 Sandbox 与安全边界](12_SANDBOX_SECURITY.md)
14. [13 报告、审计、人工审批与 PR Handoff](13_REVIEW_AND_HANDOFF.md)
15. [14 一次完整调用链](14_END_TO_END_FLOW.md)
16. [15 多服务器公司部署与当前边界](15_MULTI_SERVER_DEPLOYMENT.md)
17. [16 测试、GitHub Actions 与评测](16_TEST_CI_EVALUATION.md)
18. [17 故障场景与恢复](17_FAILURE_RECOVERY.md)
19. [18 必须掌握的类、字段和函数](18_CODE_MAP.md)
20. [19 简历口径与面试问答](19_RESUME_AND_INTERVIEW.md)
21. [20 四周学习计划与验收表](20_STUDY_PLAN.md)

## 两种学习口径不要混用

“当前本地实现”和“公司规模演进方案”是两件事。本手册凡是讲公司多服务器方案，都会明确标记为目标架构。当前 Code Change 的 JSON/JSONL 存储和本地文件 claim 适合单机演示与验证状态机，不等于已经具备跨机器一致性。公司化方案应把任务状态放入 PostgreSQL，把队列放入 Redis Streams、Kafka 或专用任务系统，把执行放入真正的容器 Sandbox。

## 每章怎样使用

每章末尾都有“本章代码阅读任务”“本章自测”和“参考答案”。答案与题目放在同一个文件中。阅读任务的四个标签含义如下：

- 阅读顺序：先看哪个类或函数，再跟到哪里。
- 看到什么程度：合上文件后必须能说出的内容。
- 暂不要求：第一遍不需要钻研的上游实现或语法细节。
- 验收动作：用口述、画图、命令或字段定位证明自己真的看懂。

读源码时不要只点开链接扫一眼。每次至少找到函数入口、主要输入、返回值、状态变化和一个失败分支。

## 每学完一章都问自己四个问题

1. 这个模块解决了什么具体问题？
2. 如果不用它，会出现什么失败？
3. 一次请求从哪个函数走到哪个函数？
4. 当前代码做到了什么，哪里只是演进设计？

如果第四个问题答不清，就先不要背更漂亮的项目介绍。秋招面试最怕的不是功能少，而是把上游能力、目标设计和自己的当前实现混在一起。
