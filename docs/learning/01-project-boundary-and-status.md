# 项目边界与当前状态

文档对应提交：`7c9059b1`
生成或最后校验时间：2026-08-04
适用分支：`agent-code-change-platform`

## 当前真实主链

HTTP code-change router 接收 Project/Task 请求，`CodeChangeStore` 持久化 JSON/JSONL 状态并入队；Worker claim 任务后准备 local-copy workspace，扫描和召回代码上下文，调用受控 Agent 工具提交 Patch，执行校验、测试并写入报告、审计和 PR Handoff。

## 不能夸大的边界

- 【当前已实现】任务状态迁移、租约 claim、workspace manifest、Patch 路径校验、受控测试和审核产物。
- 【当前已实现】上下文检索是仓库扫描与关键词/路径排序，不应描述为完整向量 RAG。
- 【上游能力】Agent 主循环和 DeerFlow 扩展机制不能写成个人从零实现。
- 【未来方案，当前未实现】自动创建或合并 GitHub PR、绝对安全的 Sandbox、多机持久化队列。
