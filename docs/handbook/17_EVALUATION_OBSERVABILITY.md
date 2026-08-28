# 17 Agent 评测、可观测性与成本

传统单元测试适合确定性代码；Agent 输出具有随机性，必须同时做协议测试、离线任务评测、轨迹观察和线上指标。只展示一个成功 Demo 不能说明系统稳定。

## 四层评测

1. Tool/函数单测：schema、路径、预算、状态转换和失败关闭。
2. Agent 协议集成：fake model 驱动真实 graph，验证 Tool call/ToolMessage/typed submit。
3. 固定任务集：固定仓库、需求、模型版本、参数和环境，多次运行统计成功与失败分类。
4. 人工/LLM judge：按预定义 rubric 评 diff 正确性、最小性和解释质量；关键结论要抽样人工复核。

## 指标拆解

- Retrieval：recall@k、MRR、读取文件/行数、上下文 token。
- Agent：任务成功率、typed-submit rate、无效 Tool call、loop/timeout、每任务模型轮数。
- Patch/Test：apply success、test pass、unsafe patch block、changed lines。
- Context：Anchor/Question 保留、token reduction、关键约束命中、回答正确性。
- 系统：首 token/总延迟、模型/Tool latency、input/output token、估算成本、错误分类。
- 人工：接受/改回/拒绝，需要真实标注；没有数据时保持 `None`，不能猜。

## 当前两组真实模型评测

第一组是 12 个 Coding Agent 小型代码任务。每个 case 创建临时 Git 仓库，实际经过 Requirement、Retrieval、Agent、Tool、Patch、Workspace 和 Test。2026-08-28 单次运行通过 10 个，最终测试通过率 83.33%；目标文件 Recall@5 为 100%。两个失败都发生在 Diff 格式阶段，不是检索漏召回。

第二组是 12 个 Anchored Context 案例，每个案例用同一个模型和温度分别运行 Full History、Anchor Only 和 Anchored Context。结果是 100% / 261.67 tokens、83.33% / 211.42 tokens、100% / 234.67 tokens。模型真实生成回答，程序按固定选择题金标准判分。

20 个 external-patch cases 仍只测确定性执行与安全拒绝，不能算模型修复率。fake-model 测试只证明 graph 和 Tool 协议接通。真实评测也是小样本单次运行，不能外推为生产效果。逐题数据和记录缺口见 `docs/evaluation/README.md`。

## 本章代码阅读任务

### 每次只核对一个指标来源

三个评测、token middleware、CI 分开问：

> 我现在只学习【当前指标或文件】。请先说明这个数字要回答什么问题，再沿代码找到样本、固定变量、执行动作、原始记录、聚合公式和输出字段。用一条样本手算，并说明失败如何分类。然后列出这个指标能支持的结论和绝对不能外推的结论。若当前是 CI，请逐个解释门禁命令验证什么。最后给 3 道带答案的自测题。

任何百分比都必须同时说出样本和分母。

- 阅读顺序：先看 `code_change/evaluation.py` 理解 external Patch 回归，再看 `code_change/agent_evaluation.py` 的 12 个真实任务，接着看 `anchored_branch/benchmark.py` 的 12 × 3 模型调用，最后看 token middleware 和 CI。
- 看到什么程度：任何指标都能回答样本是什么、变量是否固定、数据从哪来、没有测什么。
- 暂不要求：不购买在线模型额度或搭建 LangSmith 服务。
- 验收动作：亲自运行两组真实评测，从 JSON 中随机选一个成功和一个失败 case，复述原始记录如何进入汇总指标。

## 本章自测

1. 为什么最终测试通过率不足以诊断 Agent？
2. LLM-as-a-judge 有什么风险？
3. 本地 pytest 通过能否写“GitHub Actions 已通过”？

## 参考答案

1. 失败可能出在检索、Tool 选择、diff 生成、apply 或测试环境，需要分阶段指标定位。
2. Judge 也会有偏差、位置效应和模型关联；需固定 rubric、打乱顺序、校准样例并人工抽查。
3. 不能。CI 结论必须来自对应 commit 的真实 workflow run。
