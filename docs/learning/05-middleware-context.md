# 05 Middleware 与 Context：它们分别解决什么

Middleware 是 Agent 调用前后可插入的处理层。普通项目里常用于注入系统提示、控制 Token、记录 trace 或过滤工具。DeerFlow 提供 Middleware 框架，但项目不能把所有上游 Middleware 都算成自研。

## Patch Agent 的实际情况

`agent_patch.py::create_code_change_agent()` 调用 `create_deerflow_agent(..., middleware=[])`。这意味着它刻意不用通用 Lead Agent 的复杂 Middleware 链，而采用短 System Prompt、初始 Retrieval Context 和三个受限 Tool。这样更容易解释权限与失败路径。

## Branch 的实际情况

`anchored_branch/context.py::BranchContextBuilder.build()` 不是通用 DeerFlow Middleware 本身，而是项目自己的上下文构造器。`routers/anchored_branch.py::stream_branch_run()` 在启动 Child Run 前构造：Main Task Summary、Anchor、Relevant Main Context、可选检索代码、Branch History、Current Question。

`anchored_branch/middleware.py` 把这个结果以隐藏 Context 的方式送入 Branch Run。Anchor 和当前问题硬保留，可选部分受 Token Budget 裁剪。

## 面试一句话

我使用 DeerFlow 的 Middleware 接缝注入 Branch Context；Patch Agent 为了可控性显式关闭通用 Middleware，只保留受预算的检索 Prompt 和受限 Tool。
