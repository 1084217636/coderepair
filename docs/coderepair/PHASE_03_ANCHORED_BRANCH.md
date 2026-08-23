# Phase 3：Anchored Branch

## WHAT_I_USED_FROM_DEERFLOW

复用 ThreadMetaStore、Checkpointer、Thread CRUD、RunManager 和 SSE。Branch 不建立 `branch_messages` 表。

## WHAT_I_CHANGED

新增 `deerflow.anchored_branch` 领域包和 `/api/anchored-branches`：用户选中回答片段后，系统创建一个 Child Thread，并在 metadata 中记录 `parent_thread_id`、`branch_type` 和 `branch_status`。

## REQUEST_FLOW

```text
React window.getSelection()
→ POST /api/anchored-branches
→ AnchorSelection
→ Child Thread + empty checkpoint
→ branch_id / child_thread_id 持久化
→ POST /{branch_id}/runs/stream
→ DeerFlow start_run + SSE
```

## IMPORTANT_FILES

- `backend/packages/harness/deerflow/anchored_branch/models.py`：`AnchorSelection`、`BranchRecord`。
- `backend/packages/harness/deerflow/anchored_branch/store.py`：Branch 索引，不保存消息。
- `backend/app/gateway/routers/anchored_branch.py`：`create_branch`、`stream_branch_run`。
- `frontend/src/components/workspace/anchored-branch-panel.tsx`：Selection 与 Branch UI。

## WHY_THIS_DESIGN

Child Thread 天然获得独立消息历史、Checkpoint、Run 列表和 SSE；主会话不会因为局部追问而膨胀。Branch Store 只保存关系和锚点，消息仍由 DeerFlow Thread 保存。

## WHAT_I_NEED_TO_LEARN

Thread metadata 与 checkpoint 的区别、Child Thread 的 owner 隔离、选择文本到 API body 的映射。

## INTERVIEW_QUESTIONS

1. 为什么 Branch 是 Child Thread 而不是自定义 Session？
2. 刷新页面后 Branch 为什么还能恢复？
3. Anchor 失效时怎样处理？

## 验收

选择一段回答，创建 Branch，刷新后能从 Branch 列表恢复，并能在 Child Thread 上继续运行。
