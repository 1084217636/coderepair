# 02 跑通两个最小演示

先验证两条链路：外部 Patch 的确定性闭环，以及 Anchored Context 的确定性 Benchmark。在线模型配置不是理解架构的前置条件。

## 环境与命令

```bash
make config
make doctor
cd backend
PYTHONPATH=. uv run pytest tests/code_change -q
PYTHONPATH=. uv run python -m deerflow.code_change.evaluation --output ../artifacts/code-change-evaluation
PYTHONPATH=. uv run python -m deerflow.anchored_branch.benchmark --output ../artifacts/anchored-context-benchmark.json
```

需要体验 Web UI 时，再回仓库根目录运行 `make dev`，浏览器打开 `http://localhost:2026`。Code Change API 默认关闭，启用时需要 `DEER_FLOW_CODE_CHANGE_ENABLED=true`；`worker/run-once` 还要求独立 Worker token。

## 结果怎样解释

- `tests/code_change` 证明代码协议和失败分支被测试，不证明任意仓库都能自动修好。
- 20 例 evaluation 使用固定外部 Patch，衡量确定性执行与安全拒绝，不衡量在线模型质量。
- Anchored Context Benchmark 比较字符数、估算 token、Anchor/Question 保留和截断，不衡量回答正确率。

## 本章代码阅读任务

### 两个评测脚本分开问

第一次只问 `evaluation.py`，第二次只问 `benchmark.py`：

> 我现在只学习【当前评测文件】。请先说明它想回答哪个问题，再按入口函数、样本构造、执行循环、指标计算和结果写出分段解释。每个指标都要说明分子、分母、数据来源和没有测量的内容；再结合一条固定样本手算结果。最后给出运行命令、输出文件中应检查的字段、不能写进简历的推论，以及 3 道带答案的自测题。

不能把固定 Patch 评测说成在线 Agent 修复率，也不能把字符估算说成模型账单 token。

- 阅读顺序：看 `backend/packages/harness/deerflow/code_change/evaluation.py` 的 `fixed_cases`，再看 `backend/packages/harness/deerflow/anchored_branch/benchmark.py` 的 `run_benchmark`。
- 看到什么程度：能准确解释两个 Benchmark 的输入、输出与没有测量的指标。
- 暂不要求：不配置真实模型，不启动完整 Docker 栈。
- 验收动作：实际运行测试和两个命令，打开生成的 JSON/Markdown 结果核对字段。

## 本章自测

1. 20 个固定用例能否证明 Agent 修复成功率？
2. Anchored Benchmark 的 token 数是精确账单吗？
3. 为什么先跑确定性演示？

## 参考答案

1. 不能，因为它们使用预先给定的外部 Patch，没有调用在线模型生成补丁。
2. 不是，当前按字符近似估算，只适合在同一规则下比较上下文规模。
3. 它能先隔离环境、Patch、测试和安全边界问题，避免把所有失败都归因于模型。
