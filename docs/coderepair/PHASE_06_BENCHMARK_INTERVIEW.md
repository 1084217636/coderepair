# Phase 6：Benchmark、README 与面试学习文档

## WHAT_I_USED_FROM_DEERFLOW

Benchmark 只测本项目自定义的 Context 策略；不把 DeerFlow 上游能力、上下文命中率或固定外部 Patch 评测冒充在线模型成功率。

## WHAT_I_CHANGED

Benchmark 比较 Full History、Anchor Only 和 Anchored Context，记录 Prompt Token、背景遗漏率、无关上下文比例、Branch History 保留和截断。只有提供真实模型输出时才计算回答正确率；否则 `answer_correct=null`。

## REQUEST_FLOW

```text
固定 Repository + 固定回答片段 + 固定问题集
→ Full History / Anchor Only / Anchored Context 三组输入
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

默认运行只报告可确定计算的上下文指标。要比较回答正确率和长分支后主任务恢复能力，必须固定模型、温度、工具策略和任务集，保存三组真实输出后再评分。

## WHAT_I_NEED_TO_LEARN

评测变量控制、token 估算局限、端到端证据和项目边界表达。

## INTERVIEW_QUESTIONS

1. Anchored Context 相比 Full History 优化了什么？
2. 如何证明不是因为换了模型才变好？
3. 当前版本哪些仍是未来生产化方案？

## 三分钟项目介绍骨架

我基于 DeerFlow 的 Thread、Checkpoint、Agent、Tool、Sandbox 和 Streaming 实现了细粒度 Anchored Branch。用户从长回答中选择一句、一段或代码片段，系统校验主消息与文本位置后创建独立 Child Thread；每次 Branch Run 按预算组合主任务摘要、Anchor、相关主线上下文和 Branch History。关闭 Branch 不写 Main Thread。我用 Full History、Anchor Only 和 Anchored Context 三组策略研究背景完整性、噪声与 Token 成本之间的取舍。Code Change 只是展示分支中搜索代码和调用工具的 Demo。
