# 10 仓库扫描、检索与代码上下文

Coding Agent 在生成 Patch 前必须先定位相关代码。当前实现是轻量 Hybrid Code Retrieval，不使用向量数据库。它扫描允许的源码文件并切分代码块，组合 lexical、symbol 和可选 semantic 三类信号，再按 Token Budget 选择上下文。Agent 仍可通过 search 和 bounded read 获取更精确的代码。

## 为什么分成 search 与 read

一次把整个仓库塞进上下文既昂贵又会产生噪声。Search 用低成本缩小候选范围，Read 再获取准确行级内容。它们共同形成 coarse-to-fine 检索：

```text
registered repo / pinned workspace
→ scan_repo: 跳过 .git、构建产物、二进制和超限文件
→ chunk source and extract language symbols
→ lexical + symbol + optional embedding scores
→ weighted fusion: rank top-k with reasons
→ build_retrieval_context: pack under token budget
→ code_change_search returns candidates
→ code_change_read_file reads bounded exact lines
```

## 三类召回信号

- Lexical：比较 query 与文件路径、代码文本、摘要中的标识符和中文 n-gram。它适合函数名、报错文本和精确关键词。
- Symbol：Python 使用 AST，Go、TypeScript、JavaScript 和 Java 使用轻量语言规则提取 function、class/type、method 和 interface。query 命中符号名时单独加分。
- Semantic：配置 `CODE_CHANGE_EMBEDDING_MODEL/API_KEY/BASE_URL` 后，为 query 和代码块请求 OpenAI-compatible Embedding，并计算余弦相似度。Provider 不可用时回退到 lexical + symbol。

`retrieve_context` 融合三类分数，返回 chunk 行号、symbols、各信号得分和 reason。`build_retrieval_context` 按排名加入代码块，达到 Token Budget 后停止，不会把整个 Repository 复制进 Prompt。

检索质量不能用“最终 Patch 成功”单一指标替代。Patch 失败可能来自模型推理、diff 格式或测试；应分别记录目标文件是否进入 top-k、Agent 实际读取了什么、最终修改了什么。

## 本章代码阅读任务

### 扫描、检索、Tool、测试分开问

按阅读顺序一次只问一个文件：

> 我正在学习 CodeRepair 仓库检索，现在只看【当前文件和函数】。请先说明它位于“登记仓库到 Agent 看到代码”的哪一步，再按代码块解释输入路径、过滤规则、索引结构、query 分词、评分、top-k、读取行数限制和返回格式。用一个中文修复需求手算至少两个文件为什么得分不同，并指出路径逃逸、二进制文件、超长文件怎样处理。最后说明当前方法的召回边界和 3 道带答案的自测题。

不要把“支持可配置 Embedding”说成“本次评测已经启用 Embedding”。2026-08-28 的 12-task 评测没有配置 Embedding，Recall@5 100% 来自 lexical + symbol fallback。

- 阅读顺序：`repo_scanner.py` → `embeddings.py` → `context_retriever.py` 的 `CodeChunk`、符号提取、三路评分、融合和 `build_retrieval_context` → `agent_patch.py` 的初始 Context 与 search/read Tool → 对应测试。
- 看到什么程度：能解释扫描过滤、chunk、三类信号、fallback、融合 reason、Top-K、Token Budget 与 bounded read。
- 暂不要求：不学习向量数据库、Cross Encoder、GraphRAG 或复杂 Reranker。
- 验收动作：增加一个中文需求测试，检查目标文件是否进入检索结果，并分析一次误召回。

## 本章自测

1. 为什么不能直接把整个仓库放进 prompt？
2. 为什么 Semantic Provider 失败后仍能运行？
3. Recall@5 为 100% 为什么不能证明 Agent 一定修复成功？

## 参考答案

1. 会超出上下文、增加成本和延迟，并让模型被大量无关代码干扰。
2. Embedding 是可选信号。检索器捕获 Provider 不可用状态，把 semantic score 置空，继续融合 lexical 和 symbol 分数。
3. Recall@5 只检查目标文件是否进入前五。模型还可能读错位置、推理错误、生成损坏 Diff，或者最终测试失败。本次 12 个任务中 Recall@5 是 100%，最终测试通过率仍只有 83.33%。
