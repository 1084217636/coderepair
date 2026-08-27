# Phase 5：关闭 Branch 与可选总结回主线

> 文件名为兼容旧链接保留；当前设计没有 BranchDecision 或 Apply-to-Main。

## 当前行为

关闭 Branch 调用 `POST /api/anchored-branches/{branch_id}/close`，只把 Branch Record 和 Child Thread metadata 标为 `CLOSED`。Main Thread 的消息、Checkpoint 和 metadata 都不写入，因此默认关闭不会污染主线。

```text
Branch Conversation
→ Close
→ Branch Record CLOSED
→ Child Thread metadata CLOSED
→ Main Thread unchanged
```

实现位置：

- `anchored_branch/store.py::close`：幂等关闭一个 Branch。
- `anchored_branch.py::close_branch`：校验 owner 后只更新 Child。
- `anchored-branch-panel.tsx::handleClose`：关闭右栏分支，主回答仍留在左侧原位置。

## 唯一允许的后续增强

可以增加“带总结返回主线”：先让模型根据 Branch History 生成一条短总结，展示给用户；只有用户点击确认后，才把这条普通消息写入 Main Thread。生成总结和写入主线必须是两个动作，默认 Close 仍不写 Main。

当前版本没有实现该可选增强，也不会用 metadata 写入冒充可见的主线消息。

## 面试回答

为什么删除 Decision/Apply？因为项目目标是研究局部锚点和上下文隔离，而不是长期记忆治理。强制每个分支形成 Decision 会增加用户负担，也把项目重心带到审核、冲突和版本治理。这里更重要的可验证性质是：Branch 可以长时间调用模型和工具，但 Main Checkpoint 始终不变。

## 验收

创建两个 Branch，关闭其中一个；它变为 `CLOSED`，另一个仍为 `ACTIVE`，Main Thread 不增加消息，也不出现 Branch metadata。
