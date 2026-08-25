# 03 Python、async、FastAPI 与流式响应

AI 工程并不只是在 Python 中调用一次模型 API。模型请求耗时长、Tool 可能并发、前端需要持续看到进度，所以必须理解异步 IO、HTTP 生命周期和流式响应。

## 必须掌握

- `def` 与 `async def`：后者返回 coroutine，需要 `await` 或由事件循环调度。
- IO-bound 与 CPU-bound：等待网络/磁盘适合异步；CPU 密集计算仍会阻塞事件循环。
- FastAPI Router：Pydantic 校验请求，依赖注入提供 store、鉴权与运行组件，异常映射为 HTTP 状态码。
- SSE：服务器在一个 HTTP 响应中持续发送事件；比“等 Agent 完全结束再返回 JSON”更适合可观察的长任务。
- 后台 Run：客户端断开、取消、重连与去重都需要显式生命周期，不能只依赖 Handler 局部变量。

```text
browser POST
→ FastAPI request validation
→ start background Run
→ StreamBridge receives events
→ StreamingResponse / SSE
→ browser incrementally renders
```

`async` 不会自动把同步文件 IO 变快。DeerFlow 中耗时同步调用需要 `asyncio.to_thread` 或真正异步实现，否则一个慢调用可能拖住同一事件循环上的其他请求。

## 面试表达

不要只背“FastAPI 性能高”。应说明：在模型调用和流事件等待期间释放事件循环；同步 subprocess、文件扫描和 CPU 工作仍需单独处理；SSE 是单向服务端推流，而 WebSocket 是双向长连接，本项目的 Agent 输出更适合 SSE。

## 本章代码阅读任务

### 按 HTTP 生命周期分三次问

先问 Router，再问 Service，最后问清理测试：

> 我只会基本编程语法，现在只学习【当前文件和函数】。请从一次浏览器请求开始，先说明该函数处于请求生命周期哪一步，再按 Python 代码块解释参数类型、`async`/`await`、创建的对象、后台任务、事件流和异常处理。遇到 FastAPI 依赖注入、coroutine、SSE 或取消时必须用当前变量举例。最后分别推演成功、模型异常、浏览器断开，并写出看到什么程度就停和 3 道带答案的自测题。

一次只追一层，不要同时展开 ASGI、LangGraph 和前端内部实现。

- 阅读顺序：`backend/app/gateway/routers/thread_runs.py` 的流式路由 → `backend/app/gateway/services.py` 的 `start_run`/`sse_consumer` → `backend/tests/test_gateway_runtime_cleanup.py`。
- 看到什么程度：能指出请求校验、后台任务、事件桥和断开清理分别在哪一层。
- 暂不要求：不研究 ASGI Server 内核或 TCP 拥塞控制。
- 验收动作：画出请求成功、模型异常、浏览器断开三条时序，并标明谁负责结束 Run。

## 本章自测

1. `async def` 内直接调用同步文件读取有什么风险？
2. SSE 与 WebSocket 在本项目里的适用区别是什么？
3. 为什么不能让 HTTP Handler 自己保存唯一的 Run 状态？

## 参考答案

1. 它会阻塞事件循环，使同进程其他异步请求和流事件不能及时运行。
2. SSE 适合服务端向浏览器连续发送 Agent 事件且能沿用 HTTP；WebSocket 适合持续双向实时通信，但会增加连接协议与恢复复杂度。
3. Handler 会结束、断开或被重建；Run 需要独立管理才能支持取消、重连、去重和查询。
