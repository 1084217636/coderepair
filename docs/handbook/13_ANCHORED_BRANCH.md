# 13 Anchored Branch：从回答片段创建 Child Thread

长对话中，用户常只想追问一个局部判断。继续携带全量历史会引入无关上下文；另开普通聊天又会丢失被选中的精确片段。Anchored Branch 保存 Anchor，并复用 DeerFlow Child Thread 建立独立局部对话。

```text
window.getSelection()
→ POST /api/anchored-branches
→ validate Main Thread owner
→ AnchorSelection
→ create Child Thread + empty checkpoint
→ AnchoredBranchStore stores relationship and anchor
→ POST /{branch_id}/runs/stream
→ reuse start_run + StreamBridge + SSE
```

## 数据边界

- Main Thread：原对话及其 summary/checkpoint。
- Child Thread：分支自己的消息、Run 与 checkpoint。
- Branch Record：parent/child 关系、Anchor、root summary、状态和 Decision。
- Anchor：文本、message ID、offset、可选 file/symbol/code context。

Branch Store 不保存消息，避免 `branch_messages` 与 DeerFlow Thread 双写。owner 检查同时覆盖 Main、Child 与 Branch；无权资源返回 404，避免泄露存在性。

## 本章代码阅读任务

- 阅读顺序：`anchored_branch/models.py` → `store.py` → `routers/anchored_branch.py` 的 create/list/get/stream → `frontend/src/components/workspace/anchored-branch-panel.tsx`。
- 看到什么程度：能解释 AnchorSelection、BranchRecord、Main/Child Thread 与 Checkpoint 的关系。
- 暂不要求：不实现协同编辑式文本 Anchor 自动漂移。
- 验收动作：创建 Branch、刷新、继续提问，逐项说明恢复数据来自 Branch Store 还是 Thread/Checkpoint。

## 本章自测

1. 为什么不新建 BranchMessage 表？
2. Anchor offset 在原消息变化后可能遇到什么问题？
3. Branch 与 Sub-Agent 有什么区别？

## 参考答案

1. Child Thread 已提供完整消息、Run、Checkpoint 和 SSE 生命周期；双写会产生一致性与迁移问题。
2. offset 可能失效，需要 message ID、原文校验、重新定位或明确提示 stale anchor；当前实现不是完整文本锚点系统。
3. Branch 是用户可见的局部会话；Sub-Agent 是 Lead Agent 内部委派的工作单元。
