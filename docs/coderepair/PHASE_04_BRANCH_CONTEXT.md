# Phase 4：BranchContextBuilder

## WHAT_I_USED_FROM_DEERFLOW

复用 Thread 历史、`summary_text`、现有 SummarizationMiddleware 和 Tool/Sandbox 的代码读取能力；不另建完整 Memory 或 RAG 系统。

## WHAT_I_CHANGED

新增 `BranchContextBuilder`，按固定顺序组合 Anchor、Root Summary、Branch History、Code Context、Current Question，并以字符预算近似 token budget。Anchor 与当前问题 hard preserve，历史从尾部截取，代码上下文超预算时显式标记 truncated。

## REQUEST_FLOW

```text
Child checkpoint messages
 + main summary
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

完整 Main History 会污染 Branch 局部问题并浪费 token。结构化 Context 让输入来源可解释、可测量、可比较；Anchor 和当前问题不能被摘要悄悄丢失。

## WHAT_I_NEED_TO_LEARN

Prompt 组成、summary 与 message history 的边界、上下文预算、代码文件/函数/测试的最小召回。

## INTERVIEW_QUESTIONS

1. 为什么不能把整个 Main History 回灌？
2. Summary 会不会覆盖 Anchor？
3. 代码上下文为什么先做 bounded read 而不是向量库？
4. 如何证明 Context 压缩没有丢关键约束？

## 验收

单测验证超预算时 Anchor 与 Current Question 仍存在，并验证路径穿越不能读取仓库外文件。
