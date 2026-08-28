# 02 跑通两个最小演示

先用测试和 20-case external Patch 套件验证确定性执行面。配置聊天模型后，再运行 Coding Agent 和 Anchored Context 两组真实模型评测。三者回答的问题不同。

## 环境与命令

```bash
make config
make doctor
cd backend
PYTHONPATH=. uv run pytest tests/code_change -q
PYTHONPATH=. uv run python -m deerflow.code_change.evaluation --output ../artifacts/code-change-evaluation
PYTHONPATH=. uv run python -m deerflow.code_change.agent_evaluation --output ../artifacts/coding-agent-evaluation
PYTHONPATH=. uv run python -m deerflow.anchored_branch.benchmark --output ../artifacts/anchored-context-evaluation
```

需要体验 Web UI 时，再回仓库根目录运行 `make dev`，浏览器打开 `http://localhost:2026`。Code Change API 默认关闭，启用时需要 `DEER_FLOW_CODE_CHANGE_ENABLED=true`；`worker/run-once` 还要求独立 Worker token。

## 结果怎样解释

- `tests/code_change` 证明代码协议和失败分支被测试，不证明任意仓库都能自动修好。
- 20 例 evaluation 使用固定外部 Patch，衡量确定性执行与安全拒绝，不衡量在线模型质量。
- 12-task Agent Evaluation 真实调用模型并执行 Patch 和测试，当前 final test pass rate 为 83.33%。
- 12-case Anchored Context Evaluation 对每种策略真实调用模型，比较 answer correct rate、实际 Prompt Token 和 background omission。

## 本章代码阅读任务

### 三个评测脚本分开问

依次只问 external `evaluation.py`、真实 Agent `agent_evaluation.py` 和 Branch `benchmark.py`：

> 我现在只学习【当前评测文件】。请先说明它想回答哪个问题，再按入口函数、样本构造、执行循环、指标计算和结果写出分段解释。每个指标都要说明分子、分母、数据来源和没有测量的内容；再结合一条固定样本手算结果。最后给出运行命令、输出文件中应检查的字段、不能写进简历的推论，以及 3 道带答案的自测题。

不能把 fixed external Patch 回归说成在线 Agent 修复率。真实模型百分比必须带任务数、运行条件和失败分类。

- 阅读顺序：看 `code_change/evaluation.py::fixed_cases`，再看 `code_change/agent_evaluation.py::agent_cases/run_agent_evaluation`，最后看 `anchored_branch/benchmark.py::evaluation_cases/run_anchored_evaluation`。
- 看到什么程度：能准确解释三套样本、执行链、分母、输出和不能外推的结论。
- 暂不要求：不启动完整 Docker 栈；真实评测需要已配置的聊天模型。
- 验收动作：实际运行测试和三个命令，打开生成的 JSON/Markdown，抽查一个成功和一个失败 case。

## 本章自测

1. 20 个固定用例能否证明 Agent 修复成功率？
2. Anchored Context 的 Prompt Token 来自哪里？
3. 为什么先跑确定性演示？

## 参考答案

1. 不能，因为它们使用预先给定的外部 Patch，没有调用在线模型生成补丁。
2. 优先读取模型响应的 `usage_metadata.input_tokens`；Provider 不返回 usage 时才退回字符估算。报告中需要说明使用的是哪一种。
3. 它能先隔离环境、Patch、测试和安全边界问题，避免把所有失败都归因于模型。
