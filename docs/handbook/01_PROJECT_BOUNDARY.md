# 01 项目定位与能力边界

## 项目解决什么问题

通用聊天 Agent 可以读写文件，但“模型说已修复”不等于变更可验证。CodeRepair 把概率性的理解与生成，放在确定性的路径检查、Patch 应用、测试和人工确认之前；同时用 Anchored Branch 解决长对话中局部技术问题容易被全量历史淹没的问题。

## 上游、个人新增、未完成

| 范围 | 内容 |
| --- | --- |
| 上游 DeerFlow | Thread、Run、Checkpoint、Lead Agent、Tool、Middleware、SandboxProvider、StreamBridge、SSE、Next.js 工作台 |
| 本项目新增 | `deerflow.code_change`、Code Change API/控制台、受限 Patch Agent、`deerflow.anchored_branch`、Branch Context、Decision/Apply |
| 当前未完成 | 自动创建或合并真实 PR、生产级容器隔离、在线模型修复率评测、真实用户接受率、多机共享任务存储 |

Project/Task、claim/lease 与报告仍是当前实现的一部分，但它们服务于 Coding Agent 的可控执行，不是另一个分布式系统项目的主叙事。

## 简历定位

推荐定位为“基于 DeerFlow 二次开发的可审计 Coding Agent 工作流与上下文分支机制”，不要写成“自研 Agent 框架”“生产级分布式调度平台”或“全自动代码修复系统”。

## 本章代码阅读任务

### 分文件确认项目边界

先单独问 `backend/AGENTS.md`，再分别问两个 `__init__.py`：

> 我正在学习 CodeRepair 项目边界，现在只看【当前文件】。请先解释这个文件为什么能证明模块职责，再逐段说明导出的类/函数、允许的依赖方向、调用者和没有实现的能力。凡是上游 DeerFlow 已有能力和本项目新增能力都要分开列出。最后把本文件能支持的简历表述改成准确口径，并给 3 道带答案的自测题。

不要从目录名推测贡献，必须以当前代码和导出符号为准。

- 阅读顺序：读 `backend/AGENTS.md` 的 Code-change invariants，再看 `backend/packages/harness/deerflow/code_change/__init__.py` 和 `backend/packages/harness/deerflow/anchored_branch/__init__.py`。
- 看到什么程度：能把每个简历关键词归到“上游”“新增”或“未完成”。
- 暂不要求：不背所有状态值和 API 路径。
- 验收动作：写一版 80 字项目介绍，不能出现“完全自研、生产级、自动合并”。

## 本章自测

1. 为什么不能把 DeerFlow 的 Thread、Tool 和 Sandbox 写成个人从零实现？
2. Code Change 和 Anchored Branch 共同的设计思想是什么？
3. claim/lease 应该放在项目介绍的第一句吗？

## 参考答案

1. 它们来自上游，个人工作是复用并扩展；混写会使项目贡献不可验证。
2. 把模型能力放进显式、可审计、可测试的边界：候选 Patch 要经过确定性验证，局部分支决策要经用户 Apply 才回主线程。
3. 不应。它是控制面可靠性细节，只有面试官追问并发领取或故障恢复时再展开。
