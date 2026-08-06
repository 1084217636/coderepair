# CodeRepair 学习入口

CodeRepair 的主学习资料在 [`handbook/README.md`](handbook/README.md)。手册按 00 到 20 编号，假设你只会 Python 基本语法。第一次学习时，按编号顺序读，不需要同时翻旧版总结文档。

每一章都包含两块固定内容：

1. “本章源码阅读任务”会写明类、函数、字段、阅读顺序和验收标准。
2. “本章自测题与参考答案”把答案放在同一个文件里。先遮住答案口述，再逐题核对。

## 三遍学习法

第一遍读 00 到 06。目标是能用自己的话回答：DeerFlow 上游有什么，个人二开增加了什么，为什么代码变更不能只靠一段 prompt。

第二遍读 07 到 17。目标是能从 HTTP 请求讲到 Task、Queue、Worker、Workspace、Patch、测试、报告和审批，并能解释故障恢复。

第三遍读 18 到 20。目标是记住具体类、字段和函数，完成简历口径、模拟面试与闭卷验收。

## 当前实现的统一口径

学习时始终分清三层：

- 上游 DeerFlow：通用 Agent、Tool、Skill、Middleware、Thread/Run、Memory、SandboxProvider 和工作台。
- 当前个人二开：owner 隔离的 Project/Task、文件 Store、本地 JSONL 队列、claim/lease/heartbeat/fencing，以及外部 Patch 和 Agent Patch 两种模式共享的 Workspace/Test/Report/Review 主链。Agent 只拿搜索、读文件和 typed submit 三个 Tool。
- 目标架构：将文件 Store、JSONL 队列和宿主机 subprocess 分别替换为 PostgreSQL、可靠队列和短生命周期容器 Sandbox，并补在线模型固定任务评测与真实 GitHub Provider。

当前 `local-copy` 只保护登记仓库不被直接修改，不是容器沙箱。`PR handoff` 只生成交接材料和脚本，不代表 GitHub 已经创建 PR。学习和面试都按代码与测试证据回答，不把目标架构说成当前能力。
