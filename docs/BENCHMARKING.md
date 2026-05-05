# Benchmark 与评估说明

这个项目现在不只保存单次运行的 `10_evaluation.json`，还提供了一套可重复跑的 benchmark 入口，用来回答两个关键问题：

- 单智能体和多智能体谁更稳？
- 检索链和修复链到底有没有把问题带对？

## 评估分两层

### 1. 单次运行评估

每次执行后会在 `artifacts/session_*/10_evaluation.json` 里生成：

- `retrieval_hit_rate`
- `retrieved_files`
- `lexical_backend`
- `rerank_enabled`
- `primary_score`
- `avg_retrieval_score`
- `retrieved_code_ratio`
- `precheck_issue_total`
- `call_relations_count`
- `dependency_span`
- `validation_passed`
- `repair_status`
- `repair_success`

这层适合回答“这一次跑得怎么样”。

### 2. Benchmark 套件

默认 benchmark 套件在：

- `evaluation/benchmark_suite.py`

当前默认 case 覆盖：

- 项目总览分析
- `Calculate` 缺陷定位
- 工程文件上下文分析
- `single` / `multi` 两种模式对比

另外补充了一个 `go-repair` 任务集：

- 位置：`evaluation/task_catalog.py`
- 规模：30 个 Go 工程任务
- 覆盖：编译错误、单测修复、接口字段调整、错误处理、配置文件、低风险重构
- 用途：用于快速跑出“检索命中、验证通过、修复状态、失败类型”的准业务评估结果

每次跑完会在：

- `artifacts/benchmark_reports/benchmark_*.json`
- `artifacts/benchmark_reports/benchmark_*.md`

生成汇总报告。

现在 benchmark 还支持 variant 对比报告：

- `artifacts/benchmark_reports/benchmark_compare_*.json`
- `artifacts/benchmark_reports/benchmark_compare_*.md`

这层适合回答“同一组 case 下，`keyword baseline / BM25 / BM25 + rerank` 到底谁更稳”。

## 运行方式

最简单的跑法：

```bash
./.venv/bin/python scripts/run_benchmarks.py --provider groq --validation-mode local --limit 2
```

如果你只想看某一个 case：

```bash
./.venv/bin/python scripts/run_benchmarks.py \
  --provider groq \
  --case calculate_bug_single \
  --validation-mode local
```

如果你要跑扩展后的 Go 任务集：

```bash
./.venv/bin/python scripts/run_benchmarks.py \
  --suite go-repair \
  --provider groq \
  --limit 5 \
  --validation-mode local
```

如果你只想做分析，不跑验证：

```bash
./.venv/bin/python scripts/run_benchmarks.py --provider groq
```

如果你要强制对所有 case 跑验证：

```bash
./.venv/bin/python scripts/run_benchmarks.py --provider groq --validate --validation-mode auto
```

如果你想显式跑一套优化后的检索配置：

```bash
./.venv/bin/python scripts/run_benchmarks.py \
  --provider groq \
  --lexical-backend bm25 \
  --rerank \
  --validation-mode local
```

如果你想直接比较 `keyword_baseline -> bm25_only -> bm25_rerank`：

```bash
./.venv/bin/python scripts/run_benchmarks.py \
  --provider groq \
  --compare \
  --validation-mode local
```

如果你只想比较其中两个 variant：

```bash
./.venv/bin/python scripts/run_benchmarks.py \
  --provider groq \
  --compare \
  --variants keyword_baseline,bm25_rerank \
  --validation-mode local
```

## 现在能讲的评估口径

面试里最稳的说法：

- 单次运行会记录检索命中、修复状态和验证结果，避免只看模型输出文本。
- 每次运行会额外输出 `tool_calls.json`、`task_report.md`、`patch.diff`、`validate.log`、`summary.json`，用于复盘工具调用链路、写回边界、验证结果和人工接管点。
- benchmark 套件会把 `single` 和 `multi` 放到同一组 case 下比较，沉淀成可复用报告。
- benchmark variant 对比会把 `keyword / BM25 / BM25 + rerank` 放到同一组 case 下比较，输出 delta 报告，而不是凭主观感觉判断优化是否有效。
- `go-repair` 任务集可以作为简历里“小规模任务评估集”的数据来源，后续只要扩大真实仓库 case 即可。
- 当前评估更偏工程有效性，不是学术 benchmark。

## 推荐对比路线

如果你想沿着当前项目最稳的方向继续优化，建议按这个顺序看报告：

1. `keyword_baseline`
2. `bm25_only`
3. `bm25_rerank`

重点观察：

- `avg_retrieval_hit_rate`
- `avg_primary_score`
- `avg_retrieval_score`
- `avg_retrieved_code_ratio`
- `validation_pass_rate`
- `repair_success_rate`

## 边界

- 现在的 benchmark case 规模不大，更像项目级验收集。
- 现在更适合比较流程和稳定性，不适合拿来声称严格模型能力排名。
- 现在的 rerank 还是轻量 heuristic，不是 cross-encoder。
- 现在的向量检索还是 sqlite 线性扫描，不是 ANN。
- 如果后面继续扩展，优先补真实仓库 case、失败 case、多 provider 对照，再看是否要上更重的检索基础设施。
