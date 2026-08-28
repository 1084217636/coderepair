# 15 Code Change Task 状态机与 Human-in-the-loop

Anchored Branch 没有 Decision、Accept/Edit/Reject 或 Apply-to-Main。关闭 Branch 不写主线。本章只讲 Code Change 主链中候选 Patch 的人工 approve/request changes，不要把代码审核状态机误认为对话分支的长期记忆治理。

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

### 只学习 Code Change Review

按 Code Change model/state/worker/review 顺序阅读：

> 我现在只学习【当前决策或状态函数】。请先说明用户在什么状态下触发它，再按请求字段、前置状态检查、持久化写入、幂等判断、后续副作用和响应逐段解释。画出调用前后状态机，并推演重复请求、旧 Worker 写回、request changes 后重提。若与另一套 human gate 比较，只在结尾列出差异，不要混讲代码。最后给 3 道带答案的自测题。

回答必须区分“保存决定”和“执行决定”。

- 阅读顺序：`backend/packages/harness/deerflow/code_change/models.py` → `backend/packages/harness/deerflow/code_change/state_machine.py` → `backend/packages/harness/deerflow/code_change/worker.py` → `backend/packages/harness/deerflow/code_change/review.py`。
- 看到什么程度：能解释 Patch 审核的输入、持久化位置、合法状态和后续副作用。
- 暂不要求：不设计跨服务审批平台或多机队列。
- 验收动作：画出旧 Worker 恢复写回、approve 和 request changes 后重提 Patch 三种状态变化。

## 本章自测

1. Task 为什么不能只是一条队列消息？
2. Human-in-the-loop 只是在 UI 放一个按钮吗？
3. Branch Close 和 Patch approve 的副作用为什么不同？

## 参考答案

1. Task 要长期保存基线、输入、过程、结果、失败、重试和审批；队列消息可能重复或过期。
2. 不是。还需要合法状态、身份、审查材料、幂等、审计记录和明确的批准后副作用边界。
3. Branch Close 只结束 Child Thread，Main 不变；Patch approve 是 Coding Agent 代码交付链的人工作业状态。它们属于不同产品问题。
