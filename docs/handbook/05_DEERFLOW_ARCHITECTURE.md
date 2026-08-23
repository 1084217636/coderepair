# 05 DeerFlow 总体结构与一次真实请求

DeerFlow 是本项目复用的 Agent Harness。理解它的目的不是把上游能力写成自研，而是知道 CodeRepair 插在什么位置、为什么不用重造运行时。

## 四个服务与两个后端层次

- Nginx：统一入口并代理前端、Gateway 与 LangGraph 兼容路由。
- Gateway：FastAPI REST API、Thread/Run 管理和内嵌 Agent Runtime。
- Frontend：Next.js 工作台与流式状态展示。
- Provisioner：按配置提供可选 Sandbox provisioner。
- Harness (`deerflow.*`)：可复用 Agent、Tool、Middleware、Runtime、Sandbox、Memory、Skill、Sub-Agent。
- App (`app.*`)：Gateway、鉴权、Router 与应用集成；依赖方向只能 App → Harness。

## 真实请求链

```text
React useStream
→ POST /api/threads/{thread_id}/runs/stream
→ thread_runs.stream_run
→ services.start_run
→ RunManager.create_or_reject
→ run_agent
→ make_lead_agent
→ Model ↔ Tool / Middleware
→ StreamBridge.publish
→ sse_consumer
→ browser
```

Thread 是会话身份，Run 是一次执行，Checkpoint 是 LangGraph 状态快照，Run event 是供流式展示与恢复的事件。一个 Thread 可以连续产生多个 Run。

## 本章代码阅读任务

- 阅读顺序：根 `AGENTS.md` → `backend/AGENTS.md` 的 Harness/App 与 Runtime → `frontend/src/core/threads/hooks.ts` → `thread_runs.py` → `services.py`。
- 看到什么程度：能画出服务边界，并区分 Thread、Run、Checkpoint、Message 和 StreamEvent。
- 暂不要求：不背所有 Router、Middleware 和存储实现。
- 验收动作：从前端调用追到 `sse_consumer`，再指出 Anchored Branch 复用了哪几个入口。

## 本章自测

1. Harness 为什么不能反向 import `app.*`？
2. Thread 与 Run 为什么不能合成一个对象？
3. CodeRepair 为什么仍然需要自己的 Task？

## 参考答案

1. Harness 要保持可复用和可发布，反向依赖应用层会形成耦合与循环依赖。
2. Thread 表示长期会话，Run 表示一次可能成功、失败或取消的执行，两者生命周期和查询维度不同。
3. Task 记录代码变更的基线 commit、Patch、测试、审核和重试，不等同于通用聊天 Run。
