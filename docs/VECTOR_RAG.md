# 向量 RAG 设计说明

## 当前实现

项目当前已经从“纯关键词检索”升级为“本地持久化向量检索 + 词法检索兜底”的混合 RAG。

默认配置：

- `RAG_BACKEND=hybrid`
- `EMBEDDING_PROVIDER=ollama`
- `OLLAMA_EMBED_MODEL=embeddinggemma`
- `VECTOR_EMBEDDING_DIM=384`
- `RETRIEVAL_TOP_K=5`
- `VECTOR_RETRIEVAL_CANDIDATES=20`

## 架构

执行链路如下：

1. `PathFilter` 限定检索范围，避免平台代码污染
2. `RepositoryScanner` 扫描 workspace 合法文件，包含 `Dockerfile / Makefile / go.mod / README.md` 等工程文件
3. `CodeChunker` 对源码和工程文件分块
4. `OllamaEmbedder` 优先调用本地 Ollama 生成语义向量；不可用时自动回退 `HashingEmbedder`
5. `SQLiteVectorStore` 将向量与元数据持久化到本地 sqlite
6. `Retriever` 执行向量检索，并与词法检索结果做混合排序
7. Top-K 结果注入 Prompt

## 为什么选 Ollama

当前版本优先追求：

- 本地可跑
- 无需额外 API 成本
- 可以稳定落到主链和测试

因此默认采用 Ollama 本地 embedding 模型，并保留 hashing fallback，避免本地未安装 Ollama 时主链直接失效。

这意味着：

- 已经具备“语义向量 + 持久化 + 相似度检索”能力
- 本地未启动 Ollama 时仍可降级运行
- 后续仍可继续替换成更强的 embedding 模型或外部向量数据库

## 向量库位置

默认向量库文件：

- `.coderepair_vector_db/vectors.sqlite3`

每个 workspace 会按路径生成独立 collection 名称，避免不同项目之间互相污染。

## 最小运行方式

```bash
ollama serve
ollama pull embeddinggemma
```

如需自定义模型：

```env
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBED_MODEL=embeddinggemma
OLLAMA_API_BASE=http://localhost:11434/v1
```

## 当前边界

- 当前向量库仍是 sqlite 线性扫描，不是 ANN 检索
- 默认更偏“代码 + 工程文件检索增强”，不是完整知识库
- 主流程仍受文件范围和扫描策略影响
- 若要进一步增强，可继续补 BM25、跨 session 检索缓存或外部向量数据库
