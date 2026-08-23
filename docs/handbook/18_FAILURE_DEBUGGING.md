# 18 Agent 故障定位与恢复

AI 工程面试常给一个现象让你定位，而不是让你背架构。调试时先判断失败发生在哪一层，不要第一反应就“换模型或改 prompt”。

## 分层排查

| 现象 | 首查 | 常见原因 |
| --- | --- | --- |
| 没有流式输出 | Run/Event/SSE | Run 未创建、事件桥错误、连接断开、代理缓冲 |
| 模型不调用 Tool | prompt/schema/available tools | 描述不清、Tool 被过滤、模型不支持、上下文冲突 |
| Tool 参数错误 | schema 与原始 tool call | 字段歧义、类型/长度、模型截断 |
| 重复 Tool 循环 | trajectory/loop detector | 结果不可理解、错误被吞、完成条件不清 |
| 检索不到目标文件 | scan/index/query/top-k | 文件被过滤、分词不匹配、语义召回不足 |
| Patch apply 失败 | source commit/diff/context | 基线不一致、hunk 错误、路径非法 |
| 测试卡死 | subprocess tree/timeout/log | 子进程、网络等待、环境不完整 |
| Branch 答非所问 | rendered context/budget | Anchor 未注入、历史噪声、截断策略 |

## 恢复原则

- 模型或 Tool 调用可以在明确幂等边界内重试；高风险外部副作用必须先查询状态。
- Agent 中间 state 与业务 Task 分开恢复：Checkpoint 恢复对话图，Task 状态机恢复代码变更流程。
- 保留 correlation ID，把 HTTP request、Thread、Run、Task、Agent run、Tool call 和 artifact 串起来。
- 日志要可诊断但不能泄漏 API key、用户 Secret 或完整敏感源码。

当前文件 claim 的 lease/heartbeat/fencing 用于拒绝 stale Worker 写回。它是故障恢复细节，不表示跨机 exactly-once；更现实的目标是至少一次唤醒、幂等执行和拒绝过期结果。

## 本章代码阅读任务

- 阅读顺序：`runtime/runs/manager.py` 与 `stream_bridge/` → `llm_error_handling_middleware.py` → `loop_detection_middleware.py` → `code_change/worker.py` 的失败分支与 heartbeat。
- 看到什么程度：给一个用户现象，能先定位层次，再找 correlation ID、状态、事件、Tool trace 和 artifact。
- 暂不要求：不部署集中日志或 tracing 平台。
- 验收动作：任选“Agent 不 submit Patch”和“Branch 无输出”各写一份五步排障 runbook。

## 本章自测

1. Tool 一直重复时为什么不能只增加最大循环次数？
2. Checkpoint 恢复后为何仍可能重复外部副作用？
3. 什么是好的 Agent 错误分类？

## 参考答案

1. 上限只能止损，还应检查 Tool 返回是否可理解、错误是否被吞、prompt 是否缺完成条件，并加入 loop trace。
2. Checkpoint 与外部系统没有原子事务，恢复点可能在副作用之后但状态写入之前。
3. 能定位可行动阶段，例如 model/provider、context overflow、tool validation、retrieval miss、patch conflict、test failure、timeout、auth，而不是统一记为“Agent failed”。
