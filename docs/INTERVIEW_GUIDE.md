# 面试讲解与高频追问

## 先讲什么

先用这 4 句把项目立住：

1. 这是一个面向 Go 单仓的研发辅助平台，不是单纯的聊天机器人。
2. 平台主链负责任务评估、检索、生成、验证、回滚和留痕。
3. 多智能体部分用 LangGraph `StateGraph` 实现 `planner / implementer / reviewer` 协作链。
4. 项目重点不是“多会调模型”，而是“怎么让修改可验证、可回滚、可复盘”。

## 整个流程里最重要的点

### 1. PathFilter

这是最值得被问的起点。

- 解决什么问题：避免平台源码、缓存目录和无关文件污染 RAG
- 为什么重要：不做这层，检索会把错误上下文塞给模型
- 追问点：为什么只扫 workspace、为什么还要额外排除平台源码

### 2. Hybrid RAG

- 现在是 `Ollama embedding + 本地 sqlite 向量检索 + 词法兜底`
- 设计原因：先保证单机可跑和低运维，再保留向外部向量库升级的空间
- 追问点：为什么不是 Milvus、为什么保留 fallback、为什么要支持工程文件

### 3. Go AST + 调用关系

- 现在能提取 `package / import / function / method / call relation`
- 还会输出依赖跨度摘要
- 追问点：这些信息怎么影响复杂度评估、怎么帮助检索组织

### 4. LangGraph 三角色

- `planner` 负责理解任务和整理执行计划
- `implementer` 负责给出实现
- `reviewer` 负责判定 `approve / revise`
- 追问点：为什么是 3 个角色、为什么主链不用 LangGraph 全包

### 5. apply / validate / rollback

- 写回前备份
- 写回后验证
- 失败自动回滚
- 全流程落 diff、日志、结果摘要
- 追问点：为什么这是保守闭环、不是直接改文件

### 6. 评估体系

- 单次运行会生成 `10_evaluation.json`
- benchmark 套件会比较 `single / multi`
- 追问点：你怎么证明这个系统有用、哪些指标最关键

## 高频问题

### Q1: 为什么平台主体用 Python，而目标是 Go 仓库？

因为平台要快速接 LLM、RAG、CLI、验证和多智能体编排，Python 在工程拼装和实验迭代上更高效；Go 相关部分通过 AST 和工程验证来完成仓库分析。

### Q2: 为什么不直接把用户问题丢给 Claude？

因为直接问模型缺上下文、结果不可验证、也不可回滚。这个平台把扫描、检索、验证、留痕和回滚补齐了。

### Q3: 为什么主链不用 LangGraph，全都自己实现？

主链里很多步骤是确定性工程流程，比如扫描、分块、验证、落盘、回滚，更适合自定义 pipeline；多角色协作和条件回环才更适合 LangGraph。

### Q4: 为什么是 3 个角色，不是 4 个或更多？

`planner / implementer / reviewer` 已经覆盖“计划、执行、审查”三个核心环节；继续拆角色会加长 prompt 和上下文，收益不稳定。

### Q5: 为什么现在不用 Milvus？

当前是单机、单仓、低运维成本优先的工具形态，所以先落本地持久化向量检索；如果扩成多用户、多仓库服务，再升级到 Qdrant 或 Milvus。

### Q6: 你怎么证明 multi 比 single 有价值？

单次运行会生成评估产物，benchmark 套件会在同一组 case 下比较不同执行模式的检索命中、验证结果和修复状态。

### Q7: 为什么要支持工程文件检索？

Go 单仓问题不只在 `.go` 文件里，`go.mod / Dockerfile / Makefile / README` 往往决定依赖、构建和部署语境，不进 RAG 会丢重要上下文。

### Q8: 这个项目最大的边界是什么？

- 任务分类还是轻量规则
- 当前更偏单机工具，不是多用户平台
- 向量检索是轻量本地方案，不是大规模 ANN 服务
- 回滚是 backup/rollback，不是完整 snapshot 系统

## 最值得主动讲的失败与取舍

### 1. RAG 污染

- 早期问题：平台源码和产物目录混进检索
- 修复：引入 `PathFilter` + workspace/platform 隔离

### 2. 模型改代码不稳

- 风险：生成内容看起来像代码，但不一定能落地
- 修复：加 `apply / validate / rollback`

### 3. 检索链可用性

- 风险：本地 embedding 服务可能不可用
- 修复：Ollama embedding 失败时 fallback 到 hashing，保证 demo 和测试可跑

## 面试时最稳的技术边界

- 已实现：单智能体主链、LangGraph 多智能体 MVP、Hybrid RAG、Go 轻量 AST、调用关系、工程文件支持、验证与回滚、运行评估
- 不要写满：Redis、完整 Snapshot、生产级向量数据库、并行 agent 平台

## 推荐讲法

“我把这个项目做成了一个面向 Go 单仓的研发辅助平台。主链不是直接调模型，而是先做任务分类、代码扫描、混合检索和上下文增强，再进入生成、验证、回滚和 artifacts 留痕。复杂任务会切到基于 LangGraph 的 `planner / implementer / reviewer` 三角色协作链。项目的核心价值不在于堆了多少 LLM 技术，而在于把修改结果变成了可验证、可回滚、可复盘的工程闭环。”
