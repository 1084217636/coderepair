# Phase 1：跑懂一次 DeerFlow 请求

## WHAT_I_USED_FROM_DEERFLOW

- Thread 与 ThreadMetaStore：保存会话身份、metadata 和 owner。
- RunManager：创建、记录和取消一次 Run。
- `make_lead_agent`：按运行配置创建 Lead Agent、Middleware 和 Tool。
- `StreamBridge` 与 `sse_consumer`：把后台 Agent 事件变成可重连 SSE。
- Checkpointer：按 `thread_id` 持久化 LangGraph state 和 checkpoint。
- Sandbox Tool：由 DeerFlow 的 Tool 层调用现有 Sandbox，不在 CodeRepair 重写 Docker 执行器。

## WHAT_I_CHANGED

本阶段只增加学习证据和后续扩展的接入点，没有复制 DeerFlow Runtime。Anchored Branch 的 branch run 最终调用同一个 `start_run` 与 `sse_consumer`。

## REQUEST_FLOW

```text
React useStream
→ POST /api/threads/{thread_id}/runs/stream
→ thread_runs.stream_run
→ services.start_run
→ RunManager.create_or_reject
→ run_agent
→ make_lead_agent
→ Middleware / Model / Tool
→ Sandbox
→ StreamBridge.publish
→ services.sse_consumer
→ SSE event
→ useStream
```

## IMPORTANT_FILES

- `frontend/src/core/threads/hooks.ts`：`useThreadStream`，L838 附近创建 `useStream`。
- `backend/app/gateway/routers/thread_runs.py`：`stream_run`，L422-L447。
- `backend/app/gateway/services.py`：`start_run`，L430-L573；`sse_consumer`，L579-L590。
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py`：`_make_lead_agent`，L450-L564。
- `backend/packages/harness/deerflow/runtime/stream_bridge/base.py`：`StreamBridge` 与 `StreamEvent`。
- `backend/packages/harness/deerflow/runtime/runs/manager.py`：`RunRecord` 与 `RunManager`。

## IMPORTANT_CLASSES

`RunRecord`、`RunManager`、`StreamBridge`、`StreamEvent`、`ThreadState`。

## IMPORTANT_FUNCTIONS

`useStream`、`stream_run`、`start_run`、`run_agent`、`make_lead_agent`、`sse_consumer`。

## WHY_THIS_DESIGN

请求接收与 Agent 执行解耦，后台任务通过 StreamBridge 发布事件，HTTP 层只负责订阅并格式化 SSE。Branch 不新造 WebSocket 或 BranchSession，而是创建 Child Thread 后复用这条链路。

## WHAT_I_NEED_TO_LEARN

画出 Thread、Run、Checkpoint、Message、ToolMessage 和 SSE event 的关系；解释一个 Thread 为什么可以有多个 Run，以及断开后 `on_disconnect` 如何影响 Run。

## INTERVIEW_QUESTIONS

1. Thread 和 Run 有什么区别？
2. 为什么不能让 HTTP Handler 同步等待模型？
3. Tool Result 如何重新回到模型？
4. SSE 断开时 Run 会不会自动停止？

## 验收

能从 `useStream` 追到 `sse_consumer`，并指出本项目的 Branch 只插入在 Child Thread 创建和 `body.context.branch_context` 注入处。
