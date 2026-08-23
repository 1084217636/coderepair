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

## 当前证据边界

20 个 external-patch cases 只测确定性执行与安全拒绝，不是 LLM 修复率。Anchored Benchmark 只测字符/估算 token、硬保留和截断，不是回答质量。fake-model 测试证明 graph 协议接通，不证明真实模型泛化。

## 本章代码阅读任务

- 阅读顺序：`code_change/evaluation.py` → `anchored_branch/benchmark.py` → `token_usage_middleware.py` → `.github/workflows/code-change-platform.yml`。
- 看到什么程度：任何指标都能回答样本是什么、变量是否固定、数据从哪来、没有测什么。
- 暂不要求：不购买在线模型额度或搭建 LangSmith 服务。
- 验收动作：设计 10 个小仓库任务的 Agent eval schema，至少记录 seed/模型、retrieval、trajectory、patch、test、token、latency 和 failure category。

## 本章自测

1. 为什么最终测试通过率不足以诊断 Agent？
2. LLM-as-a-judge 有什么风险？
3. 本地 pytest 通过能否写“GitHub Actions 已通过”？

## 参考答案

1. 失败可能出在检索、Tool 选择、diff 生成、apply 或测试环境，需要分阶段指标定位。
2. Judge 也会有偏差、位置效应和模型关联；需固定 rubric、打乱顺序、校准样例并人工抽查。
3. 不能。CI 结论必须来自对应 commit 的真实 workflow run。
