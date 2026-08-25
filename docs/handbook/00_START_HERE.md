# 00 从这里开始：只学一条 AI 主线

这套手册只讲 CodeRepair，不承担 IM、红包、Kafka 或多机消息投递教学。项目的学习主线是：

```text
DeerFlow 请求运行时
→ 受限 Patch Agent 搜索和阅读代码
→ typed Tool 提交 unified diff
→ Worker 在固定提交的 Workspace 中校验、应用和测试
→ 用户从回答中创建 Anchored Branch
→ 有预算的 Branch Context
→ 结构化 Decision 显式 Apply 回主 Thread
```

先区分三层事实：上游 DeerFlow 已有的 Agent Harness；本项目实际新增的 Code Change 与 Anchored Branch；尚未实现的生产化设想。简历只写前两层中能由代码和测试证明的内容。

## 学习方法

按 `00` 到 `20` 阅读。`03`～`09` 专门补 AI 工程与 Agent 基础，`10`～`18` 再进入 CodeRepair 实现。每章完成四件事：说清问题、画出调用链、定位关键符号、指出至少一个边界。不要把文件队列、租约或 Kubernetes 当成项目卖点；它们只是控制面可靠性背景。

## 本章代码阅读任务

### 分三次向 AI 提问

不要让 AI 一次解释两个目录。按顺序分别问 `README_zh.md`、`code_change/`、`anchored_branch/`：

> 我第一次学习 CodeRepair，目前只看【当前文件或目录】。假设我不了解 DeerFlow 和 Agent，请先告诉我它在项目主线中的位置，再按目录入口、公开对象和调用关系分段解释。每个名词第一次出现时给出本项目中的具体例子，并明确这是上游 DeerFlow、我的二次开发，还是尚未实现。不要只给路径或名词表。最后写出看到什么程度就停，并给 3 道带答案的自测题。

一次问完一个范围并能复述后，再进入下一个。

- 阅读顺序：先看 `README_zh.md` 顶部，再看 `docs/handbook/README.md`，最后浏览 `backend/packages/harness/deerflow/code_change/` 与 `backend/packages/harness/deerflow/anchored_branch/`。
- 看到什么程度：能用两句话区分上游能力和个人新增能力。
- 暂不要求：不追 LangGraph、Checkpointer 或 SandboxProvider 的内部实现。
- 验收动作：不看文档画出上面的主线，并在每个箭头上写一个真实文件名。

## 本章自测

1. 这个项目的核心是多机任务队列吗？
2. Agent 能否直接修改登记仓库并宣布测试通过？
3. Anchored Branch 为什么属于 AI 上下文工程，而不是 IM 分支会话？

## 参考答案

1. 不是。核心是受控 Coding Agent 与 Anchored Context；队列只是执行控制面的辅助机制。
2. 不能。Agent 只能搜索、读取并通过 typed Tool 提交候选 Patch，Worker 才能校验、应用和测试。
3. 它从模型回答中固定一个 Anchor，在独立 Child Thread 内组织摘要、局部历史、代码上下文和当前问题，目标是降低长对话上下文污染。
