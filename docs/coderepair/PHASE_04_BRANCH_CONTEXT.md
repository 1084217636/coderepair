# Phase 4：BranchContextBuilder

## WHAT_I_USED_FROM_DEERFLOW

复用 Thread 历史、`summary_text`、现有 SummarizationMiddleware 和 Tool/Sandbox 的代码读取能力；不另建完整 Memory 或 RAG 系统。

## WHAT_I_CHANGED

新增 `BranchContextBuilder`，生产策略组合 `Main Task Summary + Anchor + Relevant Main Context + Branch History + Current Question`，并以字符预算近似 Token Budget。Anchor 与当前问题 hard preserve，超预算时先删除可选上下文并显式标记 `truncated`。

## REQUEST_FLOW

```text
Child checkpoint messages
 + main task summary
 + relevant Main context snapshot
 + Anchor
 + bounded code context
 + current question
→ BranchContextBuilder
→ body.context.branch_context
→ AnchoredBranchContextMiddleware
→ existing Lead Agent model call
```

## IMPORTANT_FILES

- `backend/packages/harness/deerflow/anchored_branch/context.py`：`BranchContextBuilder.build`、`read_code_context`。
- `backend/packages/harness/deerflow/anchored_branch/middleware.py`：`AnchoredBranchContextMiddleware.before_model`。
- `backend/app/gateway/services.py`：`branch_context` 被允许进入运行上下文。
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py`：根据运行上下文挂载自定义 Middleware。

## WHY_THIS_DESIGN

完整 Main History 背景充分但噪声和 Token 成本高；只给 Anchor 成本低但容易缺背景。Anchored Context 保留主任务摘要和筛选后的相关主线内容，在背景充分与隔离之间折中。三种策略共用同一 Builder，便于控制变量实验。

## WHAT_I_NEED_TO_LEARN

Prompt 组成、summary 与 message history 的边界、上下文预算、代码文件/函数/测试的最小召回。

## INTERVIEW_QUESTIONS

1. Full History、Anchor Only 和 Anchored Context 各自会失败在哪里？
2. Summary 会不会覆盖 Anchor？
3. 代码上下文为什么先做 bounded read 而不是向量库？
4. 如何证明 Context 压缩没有丢关键约束？

## 验收

单测验证超预算时 Anchor 与 Current Question 仍存在，并验证路径穿越不能读取仓库外文件。
