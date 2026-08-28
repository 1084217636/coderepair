# 09 四层面试追问

## Tool Calling

1. Function Calling 是什么？模型输出结构化函数名和参数，不会自行执行 Python。
2. 你的 read_file 怎样执行？模型产生 tool_call，DeerFlow ToolNode 路由到 `code_change_read_file`，项目代码校验相对路径和行数，结果作为 ToolMessage 回模型。
3. Tool 参数非法怎么办？路径逃逸、未索引文件、越界行数直接报错；非法 diff 经过 `git apply --check`，只允许一次修正。
4. 多个 Agent 修改同一仓库怎么办？当前通过每 Task local-copy Workspace 隔离；生产版还要并发策略、资源隔离和共享任务存储。

## Thread / Run

1. Thread 和 Run 区别？Thread 是连续会话身份，Run 是一次执行。
2. 项目哪里用？Branch 真实用 Child Thread + `start_run`；Patch Agent 只有任务关联 ID。
3. 为什么分开？同一对话能多次运行，取消、SSE、重试和记录都应落在 Run。
4. 崩溃恢复？当前了解 Checkpoint 语义即可；Code Change Worker 另有 Task claim/lease，不要混为一谈。

## Context / Middleware

1. 为什么不带全仓？成本、窗口和噪声会增加。
2. 你的 Context 如何构造？Patch Agent 用 Retrieval Bundle；Branch 用 summary + anchor + relevant context/retrieved code + history + question。
3. Embedding 不可用？检索回退 lexical + symbol。
4. Prompt Injection 怎么办？Context 标签不是安全边界，真正限制在 Tool 路径校验、只读范围、Patch 校验和测试命令白名单。

## Anchored Branch

1. 为什么不是普通新聊天？普通新聊天没有原回答选区定位。
2. 怎样隔离？Child Thread 独立保存历史和工具结果，关闭不改 Main。
3. 如何关联代码仓？BranchRecord 保存 `code_change_project_id`，每次代码追问复用 Hybrid Retrieval。
4. 分支怎样影响 Main？当前默认不会影响 Main；没有 Decision/Apply-to-Main，不能虚构该能力。
