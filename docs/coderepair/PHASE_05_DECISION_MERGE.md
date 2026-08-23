# Phase 5：BranchDecision → Apply to Main

## WHAT_I_USED_FROM_DEERFLOW

复用 Thread metadata 更新、Checkpoint/Run 的下一次读取和现有人工审批思路；不把 Branch 文本直接拼回 Main History，也不自动修改代码。

## WHAT_I_CHANGED

新增结构化 `BranchDecision`、`POST /{branch_id}/decision` 和 `POST /{branch_id}/apply`。Apply 写入主 Thread 的 `anchored_branch_decision` metadata，并由下一次 `start_run` 自动注入 `branch_decision`，主 Agent 继续决定是否调用工具修改代码。

## REQUEST_FLOW

```text
Branch Conversation
→ structured BranchDecision
→ human preview / explicit Apply
→ main Thread metadata
→ next main Run
→ AnchoredBranchContextMiddleware
→ Agent decides whether to inspect / modify / test
```

## IMPORTANT_FILES

- `backend/packages/harness/deerflow/anchored_branch/models.py`：`BranchDecision`。
- `backend/packages/harness/deerflow/anchored_branch/store.py`：`save_decision`、`mark_applied`。
- `backend/app/gateway/routers/anchored_branch.py`：`create_branch_decision`、`apply_branch_decision`。
- `backend/app/gateway/services.py`：读取主 Thread decision 并注入下一次 Run。

## WHY_THIS_DESIGN

Branch History 不是可靠的任务约束；结构化 Decision 可审计、可幂等、可预览。Merge 只合并决策，不等价于自动改代码，避免人工意图未经主 Agent 验证直接产生副作用。

## WHAT_I_NEED_TO_LEARN

幂等键、状态转换、metadata 持久化、Apply 与真实代码变更的边界。

## INTERVIEW_QUESTIONS

1. 为什么 Merge 不直接复制 Branch History？
2. Apply 如何保证重复点击不会重复应用？
3. 为什么 Decision 合并后仍要由主 Agent 重新调用工具和测试？

## 验收

重复 Apply 返回同一 decision，主 Thread metadata 有结构化 decision，下一次 Main Run 能收到它。
