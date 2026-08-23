# CodeRepair 学习入口

CodeRepair 的主学习资料在 [`handbook/README.md`](handbook/README.md)。手册按 00 到 20 编号，先补 LLM 与 Agent 工程基础，再进入 DeerFlow Runtime、受限 Coding Agent、Anchored Branch Context、安全评测与面试。第一次学习时只按这一套顺序读。

每一章都包含两块固定内容：

1. “本章源码阅读任务”会写明类、函数、字段、阅读顺序和验收标准。
2. “本章自测题与参考答案”把答案放在同一个文件里。先遮住答案口述，再逐题核对。

## 三遍学习法

第一遍读 00 到 04。目标是跑通演示并补齐 Python async、HTTP/SSE、LLM 消息、token 与 structured output。

第二遍读 05 到 09。目标是能讲清 DeerFlow Runtime、Agent Loop、LangGraph State、Tool、Middleware、Memory、Skill 与 Sub-Agent。

第三遍读 10 到 15。目标是走通检索、Patch Agent、Workspace/Test、Anchored Branch、Context 与 Decision/HITL。

第四遍读 16 到 20。目标是完成安全威胁模型、Agent eval、故障排查、源码地图和六周面试验收。

## 当前实现的统一口径

学习时始终分清三层：

- 上游 DeerFlow：通用 Agent、Tool、Skill、Middleware、Thread/Run、Memory、SandboxProvider 和工作台。
- 当前个人二开：owner 隔离的 Project/Task、文件 Store、本地 JSONL 队列、claim/lease/heartbeat/fencing，以及外部 Patch 和 Agent Patch 两种模式共享的 Workspace/Test/Report/Review 主链。Agent 只拿搜索、读文件和 typed submit 三个 Tool。
- 目标架构：将文件 Store、JSONL 队列和宿主机 subprocess 分别替换为 PostgreSQL、可靠队列和短生命周期容器 Sandbox，并补在线模型固定任务评测与真实 GitHub Provider。

当前 `local-copy` 只保护登记仓库不被直接修改，不是容器沙箱。`PR handoff` 只生成交接材料和脚本，不代表 GitHub 已经创建 PR。学习和面试都按代码与测试证据回答，不把目标架构说成当前能力。
