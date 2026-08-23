# Phase 6：Benchmark、README 与面试学习文档

## WHAT_I_USED_FROM_DEERFLOW

Benchmark 只测本项目自定义的 Context 策略和 Branch 决策闭环；不把 DeerFlow 上游能力或固定外部 Patch 评测冒充在线模型成功率。

## WHAT_I_CHANGED

阶段记录保留在 `docs/coderepair/`，正式学习顺序集中在 `docs/handbook/`。Benchmark 至少比较 Full History 与 Anchored Context，记录 prompt 字符/token 估算、Anchor 保留率、当前问题保留率和输出延迟。

## REQUEST_FLOW

```text
固定 Repository + 固定回答片段 + 固定问题集
→ Full History / Anchored Context 两组输入
→ 相同模型与工具策略
→ 记录 token、耗时、关键约束命中、人工决策结果
→ JSON + Markdown
```

## IMPORTANT_FILES

- `backend/packages/harness/deerflow/anchored_branch/context.py`
- `backend/tests/code_change/test_anchored_branch.py`
- `docs/coderepair/PHASE_01_REQUEST_FLOW.md` 到本文件
- `README_zh.md`

## WHY_THIS_DESIGN

只有固定任务、相同输入和明确指标，才能说明 Anchored Context 是否减少上下文污染；不能用编造的 QPS、在线模型成功率或人工接受率包装项目。

运行确定性上下文 Benchmark：

```bash
cd backend
PYTHONPATH=. uv run python -m deerflow.anchored_branch.benchmark --output ../artifacts/anchored-context-benchmark.json
```

它只报告上下文字符缩减率、估算 token、Anchor/Current Question 保留率和截断标记，不声称模型质量或人工接受率。

## WHAT_I_NEED_TO_LEARN

评测变量控制、token 估算局限、端到端证据和项目边界表达。

## INTERVIEW_QUESTIONS

1. Anchored Context 相比 Full History 优化了什么？
2. 如何证明不是因为换了模型才变好？
3. 当前版本哪些仍是未来生产化方案？

## 三分钟项目介绍骨架

CodeRepair 是我基于 DeerFlow Agent Harness 做的 Coding Agent 二次开发。我复用了 LangGraph、Thread、Checkpoint、Tool、Sandbox 和 Streaming，新增了 Anchored Branch Context：用户从长回答中选取局部片段，系统创建 Child Thread，并将 Anchor、摘要、Branch History、代码上下文和当前问题按预算组合后继续对话。Branch 产生结构化 Decision，用户显式 Apply 后写回 Main Thread；下一次 Main Run 收到 Decision，再由 Agent 重新检查代码、修改和测试。这样把局部追问、上下文控制和 Human-in-the-loop 合并成一条可运行链路。
