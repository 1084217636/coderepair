# 06 Agent Loop、LangGraph State 与 Checkpoint

最小 Agent Loop 可以理解为：模型观察 state，决定直接回答或调用 Tool；Tool 执行后把结果写回 state；模型继续判断，直到结束、失败或触发限制。

```text
messages/state
→ model node
→ final answer ───────────────→ END
→ tool_calls → tool node → ToolMessage ─┐
                   ↑_____________________|
```

LangGraph 将这个循环显式建模为有状态图。State 不只保存 messages，还能保存 sandbox、todos、artifacts、goal、summary、delegations 等字段；Reducer 决定新旧更新如何合并。Checkpoint 让图状态与 `thread_id` 关联，从而支持多轮继续、恢复和调试。

## 必须理解的失败

- 模型发出 Tool call，但进程中断，没有 ToolMessage：需要补全 dangling tool call，避免消息协议损坏。
- Tool 抛异常：应变成可读 ToolMessage 或明确失败，而不是让整条图无上下文崩溃。
- Agent 重复调用同一 Tool：需要 loop detection、次数和 token 预算。
- Checkpoint 存在不代表外部副作用可回滚；文件写入、PR 创建仍要自己设计幂等。

Patch Agent 当前用同一个 Agent factory，但没有配置持久化 Checkpointer；其 thread/run ID 只是 Task 关联元数据。这个差异是重要面试边界。

## 本章代码阅读任务

### 按 Agent 状态变化逐个问

分别学习 factory、state、checkpointer、dangling Tool middleware：

> 我现在只学习【当前文件或目录】。请先说明它解决 Agent 循环中的哪个状态问题，然后按类、函数和代码块解释 state 从哪里来、字段如何合并、node/edge 怎样选择下一步、何时保存 checkpoint 或补 ToolMessage。请画出调用前 state 和调用后 state，并推演一次正常 Tool、Tool 异常、进程中断。最后明确 Patch Agent 是否实际启用持久化 checkpointer，并给 3 道带答案的自测题。

回答必须区分 LangGraph 通用能力和 CodeRepair 当前接线。

- 阅读顺序：`backend/packages/harness/deerflow/agents/factory.py` → `backend/packages/harness/deerflow/agents/thread_state.py` → `backend/packages/harness/deerflow/runtime/checkpointer/` → `backend/packages/harness/deerflow/agents/middlewares/dangling_tool_call_middleware.py`。
- 看到什么程度：能解释 node、state、reducer、conditional edge、checkpoint 各解决什么问题。
- 暂不要求：不手写完整 LangGraph Runtime 或研究序列化格式。
- 验收动作：画出一次 Tool call 成功、Tool exception、进程在 Tool 返回前中断三种状态变化。

## 本章自测

1. Agent 与固定 DAG 工作流有什么区别？
2. Checkpoint 能否保证 PR 只创建一次？
3. Patch Agent 为什么不能称为持久化会话 Agent？

## 参考答案

1. Agent 的下一步由模型和当前 state 动态决定；固定 DAG 的分支通常由预定义条件决定。实际系统常把两者组合。
2. 不能。Checkpoint 保存图状态，外部 API 副作用仍需要幂等键、查询和补偿。
3. 它没有 Gateway Thread/Run 记录，也没有 graph checkpointer，ID 仅用于任务关联。
