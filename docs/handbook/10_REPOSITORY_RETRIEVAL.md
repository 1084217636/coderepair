# 10 仓库扫描、检索与代码上下文

Coding Agent 在生成 Patch 前必须先定位相关代码。当前实现采用轻量确定性检索，不使用向量数据库：扫描允许的源码文件，为需求与文件内容分词，按匹配得分返回少量上下文，再由 Agent 按行精读。

## 为什么分成 search 与 read

一次把整个仓库塞进上下文既昂贵又会产生噪声。Search 用低成本缩小候选范围，Read 再获取准确行级内容。它们共同形成 coarse-to-fine 检索：

```text
registered repo / pinned workspace
→ scan_repo: 跳过 .git、构建产物、二进制和超限文件
→ tokenize requirement and files
→ retrieve_context: rank top-k
→ code_change_search returns candidates
→ code_change_read_file reads bounded exact lines
```

## 当前能力与 RAG 演进

当前 tokenization 支持标识符与中文 n-gram，优点是可解释、无外部服务、测试稳定；局限是语义召回弱、无法理解跨文件依赖。需要演进时，可以在不改变 Tool 协议的前提下加入 AST/symbol index、BM25、Embedding、hybrid retrieval 和 rerank，并用固定查询集评估 recall@k、MRR、上下文 token 和延迟。

检索质量不能用“最终 Patch 成功”单一指标替代。Patch 失败可能来自模型推理、diff 格式或测试；应分别记录目标文件是否进入 top-k、Agent 实际读取了什么、最终修改了什么。

## 本章代码阅读任务

### 扫描、检索、Tool、测试分开问

按阅读顺序一次只问一个文件：

> 我正在学习 CodeRepair 仓库检索，现在只看【当前文件和函数】。请先说明它位于“登记仓库到 Agent 看到代码”的哪一步，再按代码块解释输入路径、过滤规则、索引结构、query 分词、评分、top-k、读取行数限制和返回格式。用一个中文修复需求手算至少两个文件为什么得分不同，并指出路径逃逸、二进制文件、超长文件怎样处理。最后说明当前方法的召回边界和 3 道带答案的自测题。

不要提前引入未实现的向量库或 AST 索引。

- 阅读顺序：`backend/packages/harness/deerflow/code_change/repo_scanner.py` → `backend/packages/harness/deerflow/code_change/context_retriever.py` → `backend/packages/harness/deerflow/code_change/agent_patch.py` 的 search/read Tool → `backend/tests/code_change/test_repo_scanner.py`。
- 看到什么程度：能解释扫描过滤、分词、排名、top-k 与 bounded read 的边界。
- 暂不要求：不实现向量库或 AST 索引。
- 验收动作：增加一个中文需求测试，检查目标文件是否进入检索结果，并分析一次误召回。

## 本章自测

1. 为什么不能直接把整个仓库放进 prompt？
2. 轻量文本检索相比 Embedding 的优势和短板是什么？
3. 如果引入向量库，应该先定义哪些离线指标？

## 参考答案

1. 会超出上下文、增加成本和延迟，并让模型被大量无关代码干扰。
2. 它简单、可解释、可复现，但对同义词、跨文件语义和复杂依赖召回较弱。
3. 固定 query/相关文件标注，测 recall@k、MRR、token、索引/查询延迟，并保持生成模型和后续流程不变。
