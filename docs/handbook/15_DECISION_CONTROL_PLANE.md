# 15 Decision 回流、Task 状态机与 Human-in-the-loop

本项目有两类人工控制点：Branch 的结构化 Decision 需要用户显式 Apply 回 Main Thread；Code Change 的候选 Patch 在测试和报告完成后需要人工 approve 或 request changes。二者都遵循“模型建议不自动变成高风险副作用”。

## Branch Decision

`BranchDecision` 保存 summary、actions、constraints、rationale。Apply 合并的是决策，不是聊天历史，也不是 Git branch。它写入 Main Thread metadata，下一次 Main Run 由现有 Agent 决定是否检查、修改和测试。重复 create/apply 返回同一 Decision，避免网络重试产生重复动作。

## Code Change Task

```text
CREATED → QUEUED → PLANNING → RETRIEVING_CONTEXT
agent: GENERATING_PATCH ┐
external: PATCH_RECEIVED ├→ VALIDATING_PATCH → APPLYING_PATCH
                         └→ RUNNING_TESTS → REVIEWING → HANDOFF_READY
HANDOFF_READY → APPROVED / CHANGES_REQUESTED
```

Task 持久记录 requirement、source commit、Patch、context、test、attempt、Agent correlation 和 review evidence。Queue 只负责唤醒 Worker。claim/lease/heartbeat/fencing 防止过期 Worker 写回，但当前是单机文件实现，不是项目主卖点或多机队列。

`HANDOFF_READY` 表示审查材料就绪；`APPROVED` 表示人工同意；`PR_CREATED` 必须来自真实 GitHub 成功响应。当前只生成 PR body 与 handoff 脚本。

## 本章代码阅读任务

- 阅读顺序：`anchored_branch/store.py` 的 Decision 方法与 Router apply → `code_change/models.py` → `state_machine.py` → `worker.py` → `review.py`。
- 看到什么程度：能比较两个 human gate 的输入、持久化位置、幂等方式和后续副作用。
- 暂不要求：不设计跨服务审批平台或多机队列。
- 验收动作：画出重复 Apply、旧 Worker 恢复写回、request changes 后重提 Patch 三种状态变化。

## 本章自测

1. Apply Branch Decision 后是否已经改代码？
2. Task 为什么不能只是一条队列消息？
3. Human-in-the-loop 只是在 UI 放一个按钮吗？

## 参考答案

1. 没有。它只写 Main metadata，下一次 Agent Run 才可能调用工具执行变更。
2. Task 要长期保存基线、输入、过程、结果、失败、重试和审批；队列消息可能重复或过期。
3. 不是。还需要合法状态、身份、审查材料、幂等、审计记录和明确的批准后副作用边界。
