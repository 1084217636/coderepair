# 两组真实模型评测

运行日期：2026-08-28。两组评测使用本地 `config.yaml` 中的默认聊天模型，模型温度固定为 0。配置文件和密钥不进入 Git。

## Coding Agent evaluation

运行命令：

```bash
cd backend
PYTHONPATH=. uv run python -m deerflow.code_change.agent_evaluation \
  --output ../artifacts/coding-agent-evaluation
```

每个 case 都会创建临时 Git 仓库，登记 Project，然后运行真实链路：

```text
Requirement
→ Hybrid Retrieval
→ DeerFlow Agent
→ search/read/typed submit Tool
→ git apply --check
→ local-copy Workspace
→ unittest
→ Diff/Report
```

| 指标 | 结果 |
| --- | ---: |
| Task count | 12 |
| Final test pass | 10 / 12 |
| Final test pass rate | 83.33% |
| Retrieval Recall@5 | 100% |
| Average reported Agent input tokens | 2594.25 |
| Average retrieval context tokens | 119.75 |

| Case | 最终测试 | Recall@5 | 失败原因 |
| --- | ---: | ---: | --- |
| bug-health-code | 通过 | 命中 |  |
| condition-negative-discount | 通过 | 命中 |  |
| normalize-username | 失败 | 命中 | 一次校验反馈后，第二个 unified diff 仍损坏 |
| error-divide-zero | 通过 | 命中 |  |
| default-port | 通过 | 命中 |  |
| boundary-adult | 通过 | 命中 |  |
| feature-unique-order | 通过 | 命中 |  |
| parse-enabled | 通过 | 命中 |  |
| clamp-range | 通过 | 命中 |  |
| safe-mapping-get | 通过 | 命中 |  |
| small-feature-greeting | 通过 | 命中 |  |
| source-and-test-update | 失败 | 命中 | 一次校验反馈后，第二个 unified diff 仍损坏 |

本次环境没有设置 `CODE_CHANGE_EMBEDDING_*`，所以检索使用 lexical + symbol fallback。100% Recall@5 只表示这 12 个任务的标注目标文件进入 Top 5，不能外推为大仓检索准确率。

失败任务的 token 记录为 0，因为第一次图调用在 Tool 异常处终止，当前结果对象拿不到那次模型 usage。`average_input_tokens` 因此偏低，只作为辅助观察，不能当作精确成本对比。最终测试通过率和 Recall@5 不受这个记录缺口影响。

## Anchored Context evaluation

运行命令：

```bash
cd backend
PYTHONPATH=. uv run python -m deerflow.anchored_branch.benchmark \
  --output ../artifacts/anchored-context-evaluation
```

12 个真实或半真实代码理解案例在同一个模型和温度下分别运行三种策略。模型必须实际输出答案，程序再按固定选项金标准判分。

| Strategy | Correct Rate | Avg Prompt Tokens | Background Omission |
| --- | ---: | ---: | ---: |
| Full History | 100% | 261.67 | 0% |
| Anchor Only | 83.33% | 211.42 | 100% |
| Anchored Context | 100% | 234.67 | 0% |

Anchored Context 在这组案例中比 Full History 少 10.32% Prompt Token，同时保持相同正确率。Anchor Only 的 Token 最少，但两个案例答错，而且上下文构造阶段缺少标注的前置事实。

## 与 20-case 回归套件的区别

`deerflow.code_change.evaluation` 的 20 条 case 使用预先写好的 external Patch，只验证状态机、Patch 应用、测试和安全拒绝。它不调用模型，不能算 Coding Agent 成功率。简历中的 83.33% 只能来自本页第一组真实 Agent 评测。

两组数据目前都是小样本、单次运行。正式对外报告时要附任务数、运行日期、模型配置和失败分类，不能只写百分比。
