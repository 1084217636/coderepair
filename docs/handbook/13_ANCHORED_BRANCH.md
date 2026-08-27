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
- Branch Record：parent/child 关系、Anchor、Main Task Summary、相关主线快照、策略、预算和状态。
- Anchor：文本、message ID、offset、可选 file/symbol/code context。

Branch Store 不保存消息，避免 `branch_messages` 与 DeerFlow Thread 双写。owner 检查同时覆盖 Main、Child 与 Branch；无权资源返回 404，避免泄露存在性。关闭 Branch 只更新 Child，不写 Main。

## 本章代码阅读任务

### Model、Store、Router、Frontend 分层问

按四层一次问一个文件：

> 我第一次学习 Anchored Branch，现在只看【当前文件或组件】。请从用户选中一段回答创建分支开始，说明这一层接收什么、创建或读取什么对象、保存到哪里、怎样关联 main_thread_id/child_thread_id/anchor。按数据结构、函数和状态变化逐段解释，并区分 Branch Store 数据与 Thread/Checkpoint 数据。最后推演刷新页面和继续提问时数据从哪里恢复，给出看到什么程度就停和 3 道带答案的自测题。

不要把 Anchored Branch 误解成 Git Branch。

- 阅读顺序：`backend/packages/harness/deerflow/anchored_branch/models.py` → `backend/packages/harness/deerflow/anchored_branch/store.py` → `backend/app/gateway/routers/anchored_branch.py` 的 create/list/get/stream → `frontend/src/components/workspace/anchored-branch-panel.tsx`。
- 看到什么程度：能解释 AnchorSelection、BranchRecord、Main/Child Thread 与 Checkpoint 的关系。
- 暂不要求：不实现协同编辑式文本 Anchor 自动漂移。
- 验收动作：创建 Branch、刷新、继续提问，逐项说明恢复数据来自 Branch Store 还是 Thread/Checkpoint。

## 本章自测

1. 为什么不新建 BranchMessage 表？
2. 创建 Branch 时为什么要同时校验 message ID、assistant 角色和 Anchor 原文？
3. Branch 与 Sub-Agent 有什么区别？

## 参考答案

1. Child Thread 已提供完整消息、Run、Checkpoint 和 SSE 生命周期；双写会产生一致性与迁移问题。
2. message ID 防止锚到错误回答，角色校验限制来源必须是助手答案，原文校验防止客户端伪造不存在的片段；渲染 offset 不匹配时可以用原文重新定位。
3. Branch 是用户可见的局部会话；Sub-Agent 是 Lead Agent 内部委派的工作单元。
