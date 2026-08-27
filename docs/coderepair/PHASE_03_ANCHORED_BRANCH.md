# Phase 3：Anchored Branch

## WHAT_I_USED_FROM_DEERFLOW

复用 ThreadMetaStore、Checkpointer、Thread CRUD、RunManager 和 SSE。Branch 不建立 `branch_messages` 表。

## WHAT_I_CHANGED

新增 `deerflow.anchored_branch` 领域包和 `/api/anchored-branches`。用户选中回答片段后，前端提交 Main message ID、文本偏移和 Anchor 原文；后端确认它来自该 Main Thread 的助手回答，再创建 Child Thread。一个主回答可以关联多个 Branch。

## REQUEST_FLOW

```text
React Selection + message_id + offsets
→ POST /api/anchored-branches
→ validate assistant message and anchor text
→ AnchorSelection + immutable Main context snapshot
→ Child Thread + empty checkpoint
→ branch_id / child_thread_id 持久化
→ POST /{branch_id}/runs/stream
→ DeerFlow start_run + SSE
```

## IMPORTANT_FILES

- `backend/packages/harness/deerflow/anchored_branch/models.py`：`AnchorSelection`、`BranchRecord`。
- `backend/packages/harness/deerflow/anchored_branch/store.py`：Branch 索引，不保存消息。
- `backend/app/gateway/routers/anchored_branch.py`：`create_branch`、`stream_branch_run`。
- `frontend/src/components/workspace/anchored-branch-panel.tsx`：Main/Branch 双栏、Selection、切换、关闭与 Anchor 标记。

## WHY_THIS_DESIGN

Child Thread 天然获得独立消息历史、Checkpoint、Run 列表和 SSE。Branch 的搜索、工具调用和追问都只写 Child Thread；关闭 Branch 只更新 Child 状态，不更新 Main metadata 或 Main messages。Branch Store 只保存关系、锚点和创建时的主线上下文快照。

## WHAT_I_NEED_TO_LEARN

Thread metadata 与 checkpoint 的区别、Child Thread 的 owner 隔离、选择文本到 API body 的映射。

## INTERVIEW_QUESTIONS

1. 为什么 Branch 是 Child Thread 而不是自定义 Session？
2. 刷新页面后 Branch 为什么还能恢复？
3. 为什么必须在创建时校验 message ID、offset 和原文？

## 验收

选择一段回答，创建 Branch，刷新后能从 Branch 列表恢复，并能在 Child Thread 上继续运行。
