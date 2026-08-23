# Phase 2：最小 Coding Agent Demo

## WHAT_I_USED_FROM_DEERFLOW

复用 DeerFlow Agent factory、Tool 调用、Sandbox 抽象和现有 SSE；不重新实现模型循环。

## WHAT_I_CHANGED

现有 `deerflow.code_change.agent_patch` 已提供最小确定性闭环：`search → read_file → typed submit_patch → Workspace apply → test → report`。Agent 只能提出候选 Patch，Worker 才能应用和测试。

## REQUEST_FLOW

```text
requirement
→ code_change_search
→ code_change_read_file
→ code_change_submit_patch
→ git apply --check / apply
→ approved test profile
→ task_report.md + audit.json
```

## IMPORTANT_FILES

- `backend/packages/harness/deerflow/code_change/agent_patch.py`
- `backend/packages/harness/deerflow/code_change/worker.py`
- `backend/packages/harness/deerflow/code_change/workspace.py`
- `backend/packages/harness/deerflow/code_change/test_runner.py`

## WHY_THIS_DESIGN

把概率性的“理解与提出修改”与确定性的“路径校验、Patch、测试”分开，避免 Agent 直接写主仓库或执行任意命令。

## WHAT_I_NEED_TO_LEARN

Tool Schema、ToolMessage、unified diff、Workspace 隔离、测试进程组和失败报告。

## INTERVIEW_QUESTIONS

1. 为什么 Agent 不能直接修改文件？
2. `shell=False` 为什么仍不等于 Sandbox？
3. 测试通过为什么不是自动合并？

## 验收

运行 `cd backend && uv run pytest tests/code_change -q`，能解释成功、Patch 冲突、路径穿越和测试失败四种结果。
