# 09 Memory、Skill、规划与 Sub-Agent

这四个概念经常被混写，面试时必须分清。

## Memory

Memory 将跨轮次有价值的信息持久化，并在未来选择性注入。它不是完整聊天历史，也不是 Checkpoint。错误记忆会持续污染后续回答，因此需要抽取规则、更新队列、存储边界和用户隔离。

## Skill

Skill 是可发现、可启用的任务说明与资源包。它告诉 Agent 针对某类任务应遵循什么流程、读取哪些参考或脚本；SkillActivationMiddleware 只在匹配的本轮注入内容。Skill 不等于 Tool：前者主要提供方法和上下文，后者提供可执行能力。

## Planning / Todo

规划把复杂目标拆成可检查步骤，适合多阶段任务，但计划本身不会执行。应允许根据 Tool 结果更新，并避免为了简单请求制造冗余步骤。

## Sub-Agent

Lead Agent 可以把边界明确的子任务交给隔离执行器。收益是并行、上下文隔离和专业化；代价是额外 token、结果合并、取消传播和共享资源竞争。Sub-Agent 不是越多越智能，也不应把同一有序任务强行并发。

CodeRepair 的 Patch Agent 是一个专用受限 Agent，不等于通用 Sub-Agent 委派；Anchored Branch 是 Child Thread，也不是 Sub-Agent。

## 本章代码阅读任务

- 阅读顺序：`agents/memory/storage.py` 与 `updater.py` → `skills/types.py` 与 `skill_activation_middleware.py` → `todo_middleware.py` → `subagents/executor.py` 与 `registry.py`。
- 看到什么程度：能用数据生命周期区分 Memory、Checkpoint、Skill、Todo 和 Sub-Agent result。
- 暂不要求：不研究所有内置 Skill 或 Sub-Agent prompt。
- 验收动作：给“分析三个互不依赖模块”设计一次合理委派，再解释为何“按顺序改同一文件三次”不适合并行。

## 本章自测

1. Skill 与 Tool 的核心区别是什么？
2. Memory 与 Checkpoint 的核心区别是什么？
3. Branch、Sub-Agent 与普通 Run 分别解决什么问题？

## 参考答案

1. Skill 提供任务方法、说明和资源上下文；Tool 提供应用允许执行的具体能力。
2. Memory 是跨对话筛选出的长期信息；Checkpoint 是某 Thread 的图状态快照，用于继续或恢复运行。
3. Branch 隔离用户局部讨论；Sub-Agent 委派独立工作；Run 记录一次 Agent 执行生命周期。
