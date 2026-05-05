# CodeRepair - 快速入门指南

## 📦 安装

### 1. 进入项目目录

```bash
cd /home/xiaobin/myproject/CodeRepair
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置 LLM（重要）

复制示例配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 LLM API Key：

```env
# 默认推荐 Groq（快速测试）
LLM_PROVIDER=groq
GROQ_API_KEY=gsk-xxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.3-70b-versatile

# 或切换到 OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
# OPENAI_MODEL=gpt-4

# 或切换到 Ollama
# LLM_PROVIDER=ollama
# OLLAMA_API_BASE=http://localhost:11434/v1
# OLLAMA_MODEL=llama2

LLM_TEMPERATURE=0.7
LLM_TIMEOUT=90
```

**支持的 LLM 提供商**：
- Groq（默认，推荐快速测试）
- OpenAI
- 本地 Ollama
- 未配置 Key 时会自动走 mock 模式

---

## 🚀 快速开始

### 方式 1：运行演示（推荐，不需要配置 LLM）

```bash
# 这会展示平台的所有关键功能（无需 API Key）
python examples/demo.py
```

**输出**：
- 任务分类示例
- 路径过滤演示
- 仓库扫描结果
- Go AST 分析
- Prompt 组装
- 验证执行结果
- 会话管理

### 方式 2：完整运行（需要配置 LLM API）

对示例项目进行 Bug 修复：

```bash
python app.py \
  --workspace examples/sample_go_project \
  --query "修复 Calculate 函数中 return result - 1 的错误，应该返回 result" \
  --no-validate
```

如果你想启用真实验证，请先确保本机安装了 `go`，并去掉 `--no-validate`。

**期望输出**：
```
[2025-03-30 12:00:15] INFO | ... | [Stage 1] 任务规划与分类
[2025-03-30 12:00:15] INFO | ... | [Stage 2-3] 检索范围设置
[2025-03-30 12:00:16] INFO | ... | [Stage 4] 代码结构分析
[2025-03-30 12:00:16] INFO | ... | [Stage 5] 检索相关代码
[2025-03-30 12:00:17] INFO | ... | [Stage 6] 构造 Prompt
[2025-03-30 12:00:18] INFO | ... | [Stage 7] 调用 LLM
[2025-03-30 12:00:19] INFO | ... | [Stage 8] 结果处理
[2025-03-30 12:00:20] INFO | ... | [Stage 9] 执行验证命令
[2025-03-30 12:00:21] INFO | ... | [Stage 10] 结果输出与会话保存
Session ID: 20260331_103000
```

### 方式 3：对自己的项目运行

```bash
python app.py \
  --workspace /path/to/your/go/project \
  --query "优化这个并发处理的性能" \
  --no-validate
```

### 方式 4：多轮对话（继续追问）

```bash
# 第一轮
python app.py \
  --workspace /path/to/project \
  --query "修复这个 bug" \
  --no-validate

# 从输出中复制 Session ID
SESSION_ID="20260331_103000"

# 第二轮：基于第一轮继续追问
python app.py \
  --workspace /path/to/project \
  --query "再考虑更多的边界情况" \
  --session-id $SESSION_ID \
  --no-validate
```

---

## 📋 命令行选项

```bash
python app.py --help

Usage: app.py [OPTIONS]

Options:
  -w, --workspace PATH     目标项目根目录 [required]
  -q, --query TEXT         用户需求或问题 [required]
  -s, --session-id TEXT    上一轮 session ID（用于继续追问）[optional]
  --no-validate            跳过验证步骤 [optional]
  --help                   显示帮助信息

Examples:
  # 修复 Bug
  python app.py -w ./examples/sample_go_project \
    -q "修复 Calculate 函数"

  # 继续追问
  python app.py -w ./examples/sample_go_project \
    -q "再加上错误处理" -s 20250330_120000

  # 跳过验证
  python app.py -w ./examples/sample_go_project \
    -q "分析代码质量" --no-validate
```

---

## 📂 输出结果位置

所有执行结果都保存在 `artifacts/session_YYYYMMDD_HHMMSS/` 目录中：

```
artifacts/
└── session_20250330_120000/
    ├── 01_input.txt                # 用户输入
    ├── 02_analysis.json            # 任务分析结果
    ├── 03_retrieval_results.json   # 检索到的代码片段
    ├── 04_prompt.txt               # 发送给 LLM 的 Prompt
    ├── 05_llm_response.md          # LLM 的原始输出
    ├── 06_extracted_code.json      # 从 LLM 输出中提取的代码块
    ├── 07_validation_output.json   # 验证命令结果
    ├── 09_result.md                # 最终结果摘要
    ├── session.json                # 会话上下文（用于 follow-up）
    └── runner.log                  # 完整日志
```

查看最新的结果：

```bash
# 查看完整日志
tail -100 artifacts/session_*/runner.log

# 查看 LLM 输出
cat artifacts/session_*/05_llm_response.md

# 查看执行总结
cat artifacts/session_*/09_result.md
```

---

## 🔧 配置说明

### config.py 中的关键参数

```python
# LLM 请求参数
LLM_MODEL = "gpt-4"           # 模型名称
LLM_TEMPERATURE = 0.7         # 创意度（0-1，越低越稳定）
LLM_MAX_TOKENS = 4096         # 最大输出 tokens

# 检索参数
RETRIEVAL_TOP_K = 5           # 返回的相关代码片段数
CHUNK_SIZE = 500              # 代码块大小（字符数）
CHUNK_OVERLAP = 100           # 相邻块的重叠部分

# 验证参数
VALIDATION_TIMEOUT = 30       # 命令执行超时（秒）

# 排除规则
EXCLUDE_PATTERNS = [
    ".git", ".venv", "artifacts",
    "__pycache__", "*.pyc", ...
]

# 包含的文件扩展名
INCLUDE_EXTENSIONS = {
    "go": [".go"],
    "python": [".py"]
}
```

---

## 🧪 测试演示模块

如果你想快速体验而不需要配置 LLM：

```bash
# 运行编练脚本（展示所有模块）
python examples/demo.py

# 或者逐个测试模块
python -c "
from core.planner import TaskPlanner
p = TaskPlanner()
print(p.classify_task('修复一个 bug'))
"
```

---

## ❓ 常见问题

### Q: 缺少 API Key 怎么办？

A: 运行 `examples/demo.py` 不需要 API Key。如果要运行完整的 `app.py`，需要在 `.env` 中配置。
A: 不配置 API Key 也能运行 `app.py`，系统会自动回退 mock 模式；如果只是想先打通主流程，建议加上 `--no-validate`。

### Q: 怎样使用其他 LLM 提供商（如 Siliconflow）？

A: 编辑 `.env` 文件：
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxx
OPENAI_API_BASE=https://api.siliconflow.cn/v1
OPENAI_MODEL=gpt-4  # 根据提供商支持修改模型名
```

### Q: 为什么没有检索到相关代码？

A: 
- 检查目标项目是否在 `--workspace` 中正确指定
- 确保项目包含与查询相关的代码
- 增加 `RETRIEVAL_TOP_K` 的值
- 查看 `artifacts/session_*/03_retrieval_results.json` 看检索结果

### Q: 怎样调整 LLM 的输出风格？

A: 修改 `.env` 中的 `LLM_TEMPERATURE`：
- `0.0`：最保守，输出非常确定
- `0.7`（推荐）：平衡的创意
- `1.0+`：最创意，输出多样

### Q: 如何跳过验证步骤？

A: 对于某些情况（如代码审查），可以跳过验证：
```bash
python app.py --workspace ... --query ... --no-validate
```

---

## 📚 项目结构及各模块说明

```
CodeRepair/
├── core/              # 核心编排
│   ├── planner.py     # 任务分类 & 语言检测
│   ├── session.py     # 会话管理（多轮对话）
│   └── logger.py      # 统一日志输出
│
├── retrieval/         # 代码检索 ⭐ 解决 RAG 污染
│   ├── filters.py     # 严格的平台 ↔ 工作区隔离
│   ├── scanner.py     # 仓库文件扫描
│   ├── chunker.py     # 代码分块
│   └── retriever.py   # 相似度检索
│
├── analyzers/         # 代码分析
│   ├── go_ast.py      # Go AST 解析
│   └── language_detector.py
│
├── llm/               # LLM 调用
│   ├── client.py      # LLM API 封装
│   └── prompt_builder.py  # Prompt 组装
│
├── executors/         # 命令执行
│   └── validator.py   # go build / go test
│
├── outputs/           # 结果管理
│   ├── artifact_manager.py  # Artifacts 保存
│   └── formatters.py        # 结果格式化
│
└── examples/
    ├── demo.py                # 演示脚本
    └── sample_go_project/     # 示例项目
```

---

## 🎯 下一步

1. ✅ **运行演示**：`python examples/demo.py`
2. ✅ **配置 API**：编辑 `.env`
3. ✅ **运行示例**：`python app.py -w examples/sample_go_project -q "..."`
4. ✅ **查看结果**：在 `artifacts/` 目录中查看完整日志
5. ✅ **尝试多轮**：用 `--session-id` 继续追问

---

## 💡 工程设计要点

这个项目展示了几个重要的工程设计理念：

1. **清晰的问题解决**：
   - ✅ 解决了 RAG 污染（通过 PathFilter）
   - ✅ 解决了黑盒问题（通过 10 阶段日志）

2. **系统化的流程**：
   - 10 个清晰的执行阶段
   - 每个阶段都可观测和可审计
   - 支持多轮对话

3. **模块职责清晰**：
   - 每个模块做一件事，做好
   - 便于讲解、测试和扩展

4. **生产质量的细节**：
   - 完整的错误处理
   - 真实的命令执行验证
   - 所有过程都有留痕

---

**最后更新**：2025-03-30

**需要帮助**？查看 [README.md](README.md) 或通过示例代码学习。
