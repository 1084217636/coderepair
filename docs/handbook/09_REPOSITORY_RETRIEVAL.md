# 09 仓库扫描与上下文检索

## 为什么不能把整个仓库塞给模型

真实仓库可能有几万文件，远超模型上下文窗口。全部发送还会增加延迟、token 成本，并把无关配置和敏感文件暴露给模型。系统要先筛选候选文件，再让 Agent 精读。

当前链路分两步：

```text
scan_repo(repo_path)
→ CodeFile 列表
→ retrieve_context(requirement, files, Top-K)
→ Agent 可进一步 read_file
```

## scan_repo 做什么

`repo_scanner.py` 递归遍历仓库，但会跳过：

```text
.git, .venv, venv, node_modules, dist, build, __pycache__, .deer-flow
```

只收集已支持后缀，例如 `.go`、`.py`、`.ts`、`.tsx`、`.java`、`.yaml`、`.json`。
每个 `CodeFile` 保存相对路径、语言、大小和前几行摘要。

为什么不读取二进制文件？模型无法直接利用，大文件还会浪费内存。为什么跳过 `.git`？里面有内部元数据，既无必要也会扩大攻击面。

## retrieve_context 怎样打分

轻量版本按三类匹配：

- 词项出现在路径：权重高，因为文件名常表达职责。
- 出现在摘要：次高。
- 出现在全文：基础权重。

最后按分数和路径排序，返回固定数量。这个方案简单、可解释、无需额外服务，适合小型演示仓库。

## 中文需求怎样处理

只识别 ASCII 标识符时，需求“修复登录接口”无法产生词项，Go/Python 文件只能得到相同兜底分数，结果接近按文件名排序。当前 `tokenize` 已保留连续中文片段，并生成二元、三元 n-gram，例如“登录”和“接口”。这比完全丢弃中文可靠，但仍没有分词、同义词和代码 symbol 对齐。

更完整的做法包括：

- 为中文需求抽取关键术语和可能的英文标识符。
- 使用 ripgrep/BM25 做词法召回。
- 按函数、类或语法树 symbol 建索引。
- Embedding 召回语义相近代码。
- Reranker 对候选 chunk 重排。

不要因为代码里有 `Top-K` 就说成完整向量 RAG。

## 文件级检索的边界

当前 snippet 只截取文件开头。如果目标函数在 2,000 行文件末尾，模型可能看不到。`code_change_read_file` 允许 Agent 按行范围继续读取，但前提是搜索先找到正确文件。

`scan_repo` 还有最大文件数限制。简单按字典序取前 500 个文件，在大仓库里可能漏掉后面的目录。公司化版本应建立增量索引，而不是每个任务全盘扫描。

## 安全边界

读文件 Tool 必须：

- 只接受仓库相对路径。
- 拒绝绝对路径和 `..`。
- resolve 后再次确认仍在 repo root 内，防止软链接逃逸。
- 限制单次行数和字符数。
- 不允许读取未登记仓库。

路径检查要在服务端做，不能相信模型“不会越界”。

## 怎样评测检索

为固定任务人工标注至少一个相关文件集合。对每个需求运行检索，计算：

```text
Recall@5 = Top 5 中命中的相关文件数 / 所有相关文件数
```

还可记录首个相关文件排名 MRR。只有固定任务和标注答案，才能比较 tokenizer、BM25 或 Embedding 改动是否真正提升。

当前 20 用例主要验证 Patch/Test 状态和安全拦截，不应把它包装成检索 Recall 评测。

## 面试取舍

> 我先用可解释的文件级词法检索完成端到端链路，因为个人项目仓库规模不大，也不想为了技术名词引入向量库。它的中文和大仓库召回有限，所以我把 Recall@5 作为后续指标；需要扩展时会按 symbol/chunk 建 BM25 与 Embedding 混合索引，再用 reranker 控制送入模型的上下文。

## 本章代码阅读任务

阅读顺序：先看扫描过滤，再手算检索分数，最后看 Agent 如何二次按行读取。

1. 打开 `backend/packages/harness/deerflow/code_change/repo_scanner.py`，按 `SKIP_DIRS`、`LANG_BY_SUFFIX`、`scan_repo`、`first_non_empty_lines` 的顺序读。你要说出目录过滤、后缀过滤、`max_files` 和 summary 上限分别在哪里生效。暂不研究 AST。
2. 打开 `backend/packages/harness/deerflow/code_change/context_retriever.py`，先读 `tokenize` 的英文标识符与中文 n-gram，再逐行算一次 `retrieve_context` 的 path、summary、content 分数。确认 snippet 固定取文件开头 800 字符。
3. 打开 `backend/packages/harness/deerflow/code_change/agent_patch.py` 的 `code_change_search` 和 `code_change_read_file`。记录搜索返回的字段，以及读文件的 `start_line`、`end_line`、400 行和 `MAX_READ_CHARS` 边界。跟到 `_safe_repo_file` 的 resolve 检查即可。
4. 打开 `backend/tests/code_change/test_repo_scanner.py`，读两个测试。第一个验证跳过 `.git` 并召回 `health.go`；第二个验证 `login_handler`、“登录”和“接口”都进入词项。看到断言即可，暂不学习 fixture。

看到什么程度：给出“修复登录接口 login_handler”时，能手算一份候选文件为什么得分更高，并能指出文件级检索在长文件和 500 文件上限下可能漏召回。

暂不要求：不实现 BM25、Embedding、向量库或 AST 索引，也不研究复杂中文分词；先掌握当前词法算法的输入、分数和上限。

验收动作：自己创建三个命名不同的小文件，用一个中英混合需求运行检索，预测并核对 Top-3 顺序与 reason 字段。

## 本章自测

1. 为什么不能把整个仓库直接发给模型？
2. `scan_repo` 过滤了哪三类内容，为什么？
3. 当前检索怎样给候选打分？
4. 中文 n-gram 修复了什么，还没有解决什么？
5. `code_change_read_file` 为什么仍要做 resolve 后的 root 检查？
6. 当前 20 用例为什么不能当作 Recall@5 评测？

## 参考答案

1. 整仓内容可能超过上下文，增加 token 和延迟，并暴露无关配置或敏感内容。系统应先召回少量候选，再按行精读。
2. 它跳过 `.git`、依赖和构建缓存目录；只接收支持的文本后缀；遇到读取错误就跳过。这样减少二进制、生成物、依赖和元数据噪声。
3. 需求词项命中路径加 3 分，命中摘要加 2 分，命中全文加 1 分；Go/Python 零命中文件有 1 分兜底，最后按分数降序和路径排序取 Top-K。
4. 当前 n-gram 让连续中文需求不再变成空词项，也能命中“登录”“接口”等片段。它没有真正中文分词、同义词、symbol 索引、语义召回或 rerank。
5. 拒绝 `..` 仍不足以防软链接逃逸。服务端把路径 resolve 成真实路径后，还要确认它仍位于登记仓库根目录内。
6. 当前 20 用例主要使用预制 Patch 检查 apply、test、任务状态和越权拦截，没有为每个需求标注相关文件集合，因此不能计算 Recall@5。
