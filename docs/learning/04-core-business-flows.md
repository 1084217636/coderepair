# 核心业务调用链

文档对应提交：`7c9059b1`
生成或最后校验时间：2026-08-04
适用分支：`agent-code-change-platform`

## Worker 执行主链

```text
创建 Project/Task
→ 持久化并入队
→ Worker 原子 claim/lease
→ local-copy workspace
→ repo scan 与上下文召回
→ DeerFlow/Agent 工具检索并提交 unified diff
→ Patch 路径校验与 dry-run/apply
→ 受控测试
→ task_report/audit/pr_handoff
→ REVIEW_REQUIRED/HANDOFF_READY
```

阅读顺序：`routers/code_change.py` → `worker.py` → `workspace.py` → `context_retriever.py` → `agent_patch.py` → `patcher.py` → `test_runner.py` → `report_writer.py`。每项记录输入、输出、状态迁移、同步/异步边界、超时和失败结果。

## Agent 边界

`agent_patch.py` 中的 `code_change_search`、`code_change_read_file`、`code_change_submit_patch` 是本项目为代码变更场景提供的受控工具；Agent 主循环及通用 Skills/Sub-Agent 机制来自 DeerFlow 上游。提交 Patch 不等于自动创建或合并 PR。

## 状态机

阅读 `models.py` 与 `state_machine.py`，画出合法迁移，重点理解 `PATCH_RECEIVED`、校验、应用、测试、审核和 handoff 之间为什么不能直接跳转，以及 retry/失败如何留下可审计证据。
