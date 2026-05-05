# CodeRepair - 代码分析与自动修复研发辅助平台

一个面向工程场景的 Python 研发辅助平台，通过自然语言需求、代码检索、LLM 调用、验证执行，为开发者提供**可解释、可追踪**的代码修改建议。

## 文档入口

优先看这 3 份：

- `README.md`：项目定位、结构和主入口
- `SIMPLE_USAGE.md`：最短使用路径
- `TESTING_GUIDE.md`：测试与验收方式

和当前阶段最相关的补充文档：

- `docs/DOCKER_SETUP.md`：Docker 安装、镜像加速与项目接入
- `docs/MULTI_AGENT_BOUNDARY.md`：多智能体当前阶段边界与验收标准
- `docs/LANGGRAPH_LEARNING.md`：LangGraph 与当前 3 角色图的学习入口
- `docs/VECTOR_RAG.md`：当前向量 RAG 与本地向量库设计
- `docs/BENCHMARKING.md`：benchmark 套件与评估指标
- `docs/INTERVIEW_GUIDE.md`：面试讲法、高频追问与项目边界
- `docs/STUDY_PLAN.md`：按天拆好的学习与开发计划

## 当前架构状态

- 当前主链路是**单智能体串行编排**，入口在 `app.py`
- 当前已经补上一个**多智能体 MVP**：基于 LangGraph `StateGraph` 的 `planner -> implementer -> reviewer`
- 主 CLI 已接入 `apply -> validate -> rollback` 的保守闭环
- 已新增轻量 Tool Calling 审计层，仓库扫描、检索、LLM 调用、写回、验证、回滚、报告都会沉淀到 `tool_calls.json`
- 每次运行会额外生成交付型产物：`task_report.md`、`patch.diff`、`validate.log`、`review.json`
- Go 项目验证支持 `auto / local / docker` 三种模式，`auto` 会优先尝试 Docker
- 当前检索链已升级为“Ollama 语义 embedding + 本地 sqlite 向量库 + 词法兜底”的混合 RAG
- Go 结构分析已补充轻量调用关系与依赖跨度统计，并输出运行评估产物
- benchmark 已补充 `go-repair` 任务集，包含 30 个 Go 工程修改/定位场景
- `core/langgraph_workflow.py` 仍然是实验性 workflow scaffold，不是完整的 LangGraph 多智能体系统
- 如果你要让项目参与自身后续开发，推荐使用 `--self-dev` 模式

## 核心特性

### ✅ 问题解决

本平台在重构时**明确解决了两个关键问题**：

#### 1️⃣ RAG 检索污染（已解决）

**问题**：以前项目的 RAG 检索把"平台自己的代码"也传入了上下文，造成污染。

**解决方案**：
- 平台代码目录（platform_root）和目标项目目录（workspace_root）严格隔离
- `retrieval/filters.py` 中明确的 `PathFilter` 类实现检索范围控制
- 检索操作**只读取 workspace_root 内的文件**
- 排除规则明确：`.git`, `.venv`, `artifacts`, 平台源码目录等完全不被索引

核心实现见 [retrieval/filters.py](retrieval/filters.py#L1-L90)

#### 2️⃣ 黑盒执行（已解决）

**问题**：整个平台的执行流程不透明，看不出每一步在做什么。

**解决方案**：
- 10 个清晰的执行阶段，每阶段都有日志输出
- 每个日志行包含技术细节：使用的模块、处理的文件数、token 数等
- 所有中间结果都保存到 `artifacts/session_*/` 目录
- 用户能清楚看每个阶段的完整日志和输出

### 🔄 工作流程

```
用户输入
  ↓
[Stage 1] 任务规划 & 分类
  - 识别需求类型（Bug 修复 / 新功能 / 继续追问）
  - 检测项目编程语言
  ↓
[Stage 2-3] 检索范围设置 & 仓库扫描
  - 初始化 PathFilter，明确平台 ↔ workspace 隔离
  - 扫描 workspace 合法文件（过滤平台代码）
  ↓
[Stage 4] 代码结构分析
  - Go 结构分析（包、导入、函数、方法、调用关系、依赖跨度）
  - 代码分块
  ↓
[Stage 5] 相关代码检索
  - 基于 Ollama embedding 的本地向量检索
  - 词法检索兜底并做混合排序
  - 返回 Top-K chunks
  ↓
[Stage 6] Prompt 组装
  - 构造系统提示（角色、职责、格式要求）
  - 构造用户提示（需求 + 检索结果 + 历史记录）
  ↓
[Stage 7] 调用 LLM
  - 发送 prompt 到 LLM API
  - 记录 request & response
  ↓
[Stage 8] 结果处理
  - 解析 LLM 输出代码块
  - 提取修改代码
  ↓
[Stage 9] 验证执行
  - 执行 go build / go test （根据语言类型）
  - 支持 auto / local / docker 三种验证模式
  - Docker 不可用时可自动降级到本地验证
  - 捕获输出与错误
  ↓
[Stage 10] 结果输出 & 会话保存
  - 输出最终建议到控制台
  - 保存 session 上下文（支持 follow-up）
  - 生成 artifacts（日志、prompt、diff、验证结果、运行评估）
```

### 📋 支持的任务类型

- **Bug 修复** (`bug_fix`)：分析问题根源，提供修复方案
- **新功能开发** (`feature`)：设计接口，生成实现代码
- **代码审查** (`review`)：指出问题，提出改进建议
- **继续追问** (`follow_up`)：基于前一轮上下文优化答案

### 🔄 多轮对话支持

平台支持**继续追问**功能，让用户在第二轮、第三轮时不需要重新开始完整流程：

```bash
# 第一轮：初始需求
python app.py -w /path/to/project -q "修复 bug: 函数返回值错误"

# 第二轮：基于第一轮反馈继续追问
python app.py -w /path/to/project -q "再优化一下性能" \
  --session-id 20250330_120000
```

在第二轮时，平台会：
- 加载上一轮的任务摘要、检索结果摘要、LLM 输出摘要
- 在 prompt 中包含历史上下文
- 加快响应速度，给出更合适的答案

## 项目结构

```
CodeRepair/
├── app.py                          # CLI 主入口（可直接运行）
├── config.py                       # 配置管理
├── requirements.txt                # Python 依赖
├── README.md                       # 本文件
│
├── core/                           # 核心编排逻辑
│   ├── logger.py                   # 统一日志（标准库 logging）
│   ├── planner.py                  # 任务分类与编排
│   ├── session.py                  # 会话管理（多轮对话）
│   └── pipeline.py                 # 流程管理
│
├── retrieval/                      # 代码检索模块 ⭐ RAG 污染修复在这里
│   ├── filters.py                  # 路径过滤（★ 平台 ↔ workspace 隔离）
│   ├── scanner.py                  # 仓库扫描
│   ├── chunker.py                  # 代码分块
│   ├── retriever.py                # 混合检索逻辑
│   ├── embeddings.py               # Ollama / hashing embedding
│   └── vector_store.py             # sqlite 向量库
│
├── analyzers/                      # 代码分析模块
│   ├── language_detector.py        # 语言检测
│   ├── go_ast.py                   # Go AST 分析（包、函数、方法、调用关系）
│   └── file_summary.py             # 文件摘要
│
├── llm/                            # LLM 调用层
│   ├── client.py                   # 统一 LLM 客户端
│   └── prompt_builder.py           # Prompt 组装
│
├── executors/                      # 验证与命令执行
│   └── validator.py                # 构建/测试/命令执行
│
├── outputs/                        # 结果输出与日志管理
│   ├── artifact_manager.py         # Artifacts 管理
│   └── formatters.py               # 结果格式化
│
├── examples/
│   └── sample_go_project/          # 示例 Go 项目（用于演示）
│
├── artifacts/                      # 执行结果（自动生成）
│   └── session_YYYYMMDD_HHMMSS/
│       ├── 01_input.txt            # 用户输入
│       ├── 02_analysis.json        # 任务分析
│       ├── 02_call_graph.json      # 调用关系与依赖跨度
│       ├── 02_go_precheck.json     # Go 工程预检
│       ├── 03_retrieval_results.json # 检索结果
│       ├── 04_prompt.txt           # 发送给 LLM 的 prompt
│       ├── 05_llm_response.md      # LLM 原始输出
│       ├── 06_extracted_code.json  # 提取出的代码块
│       ├── 07_validation_output.json # 验证命令输出
│       ├── 08_apply_result.json    # 写回 / 回滚结果
│       ├── 09_result.md            # 最终结果摘要
│       ├── 10_evaluation.json      # 运行评估指标
│       ├── session.json            # 会话上下文（用于 follow-up）
│       └── runner.log              # 完整运行日志
│
└── tests/                          # 测试套件
```

## 安装与配置

### 1. 克隆或创建项目

```bash
cd /path/to/CodeRepair
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置 LLM API

复制 `.env.example` 到 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置你的 LLM 配置：

```env
# 默认推荐 Groq（快速测试）
LLM_PROVIDER=groq
GROQ_API_KEY=gsk-your-api-key-here
GROQ_MODEL=llama-3.3-70b-versatile

# 或者使用 OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-your-api-key-here
# OPENAI_MODEL=gpt-4

# 或者使用本地 Ollama
# LLM_PROVIDER=ollama
# OLLAMA_API_BASE=http://localhost:11434/v1
# OLLAMA_MODEL=llama2

LLM_TEMPERATURE=0.7
LLM_TIMEOUT=90

# 其他配置
LOG_LEVEL=INFO
DEBUG=false
```

**支持的 LLM 提供商**：
- Groq（默认，适合快速测试）
- OpenAI
- Ollama
- AiCanAPI
- 未配置 API Key 时自动回退 mock 模式

## 快速开始

### 产品化 fix 入口

除了兼容原来的 `app.py` 入口，现在也可以用更接近真实研发工具的命令：

```bash
./.venv/bin/python cli.py fix \
  --repo examples/sample_go_project \
  --task "修复 Calculate 函数返回值错误，并输出完整文件代码" \
  --apply-file main.go \
  --validate "go test ./..." \
  --validation-mode local
```

运行后会在 `artifacts/session_*/` 下生成 `task_report.md`、`patch.diff`、`validate.log`、`review.json`、`summary.json`、`tool_calls.json` 等产物，便于复盘和接入研发流程。

### 配置检查 demo

面向策划配置/服务端配置交付前校验，可以检查必填字段、重复 ID、引用缺失和字段类型漂移：

```bash
./.venv/bin/python cli.py check-config \
  --repo . \
  --file examples/game_config/heroes.json \
  --required id,name,role,hp
```

示例输出会标记 `missing_required_field`、`duplicate_id`、`mixed_field_type`、`broken_reference` 等问题。

### 测试补全建议 demo

面向研发流程中的单元测试补全，可以扫描 Go 函数和已有 `_test.go` 文件，输出缺失测试与边界用例建议：

```bash
./.venv/bin/python cli.py suggest-tests \
  --repo examples/sample_go_project
```

### 自举开发模式

当你想让 CodeRepair 分析它自己这个仓库、辅助后续需求开发时，可以显式开启：

```bash
./.venv/bin/python app.py \
  --workspace . \
  --focus-file llm/client.py \
  --query "请分析 llm/client.py 的改造点，并给出低风险修改建议" \
  --provider aicanapi \
  --model claude-opus-4-6 \
  --self-dev \
  --no-validate
```

默认情况下，平台会排除 `core/`、`llm/`、`retrieval/` 等平台源码目录；`--self-dev` 会放开这层限制，`--focus-file` 则可以把分析范围压到单文件或单目录，便于项目自举开发。

### 多智能体模式

如果你希望让多个角色协作生成建议，可以使用：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "修复 Calculate 函数返回值错误的问题" \
  --provider aicanapi \
  --model claude-sonnet-4-6 \
  --mode multi \
  --no-validate
```

当前多智能体 MVP 包含：

- planner
- implementer
- reviewer

如果 reviewer 给出 `VERDICT: revise`，系统会再触发一轮 implementer 修订。
当前这条链是用 LangGraph `StateGraph` 实现的最小闭环，不是完整的 agent platform。

### 写回、验证与回滚

如果你想把生成结果保守地写回单文件，并在失败时自动回滚，可以直接用：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "修复 main.go 里的逻辑错误，并返回完整文件代码" \
  --apply-file main.go \
  --validation-mode auto
```

默认行为：

- `--validation-mode auto` 优先尝试 Docker，失败时自动降级本地验证
- `--rollback-on-failure` 默认开启，写回后验证失败会自动恢复到备份版本
- `--validate-cmd` 可以覆盖默认验证命令，例如 `--validate-cmd "go test ./..."`

### 方式 1：修复示例项目中的 Bug

```bash
# 进入项目目录
cd CodeRepair

# 激活虚拟环境
source venv/bin/activate

# 运行示例（修复示例 Go 项目中的 Bug）
python app.py \
  --workspace examples/sample_go_project \
  --query "修复 Calculate 函数返回值错误的问题" \
  --no-validate
```

**期望输出**：
- 终端会打印 10 个执行阶段的日志
- 结果摘要里会直接打印 `Session ID`
- 会看到 LLM 的代码建议
- 使用 `--no-validate` 时会显示“已跳过验证”
- 所有结果会保存到 `artifacts/session_*/` 目录

### 方式 2：对自己的项目进行分析

```bash
python app.py \
  --workspace /path/to/your/project \
  --query "这里的 string 处理有什么问题吗？"
```

### 方式 3：继续追问（Multi-turn）

```bash
# 第一次询问
python app.py \
  --workspace /path/to/project \
  --query "优化这个函数的性能" \
  --no-validate

# 从输出中复制 Session ID，例如 20260331_103000
SESSION_ID=20260331_103000

# 第二次基于第一次结果继续追问
python app.py \
  --workspace /path/to/project \
  --query "再增加一下错误处理" \
  --session-id $SESSION_ID \
  --no-validate
```

## 命令行选项

```bash
python app.py --help

Usage: app.py [OPTIONS]

Options:
  -w, --workspace, --repo TEXT
                            目标项目的根目录路径 [required]
  -q, --query, --task TEXT  用户需求或问题（自然语言）[required]
  -s, --session-id TEXT     上一轮的 session ID（用于继续追问）
  --no-validate             是否跳过验证步骤（默认执行验证）
  --provider TEXT           覆盖使用的 LLM Provider
  --model TEXT              覆盖使用的模型名
  --temperature FLOAT       覆盖温度参数
  --apply-file TEXT         将第一个完整代码块保守写回目标文件
  --validation-mode [auto|local|docker]
                            auto 优先 Docker，失败时降级本地
  --validate-cmd TEXT       覆盖默认验证命令
  --rollback-on-failure / --no-rollback-on-failure
                            写回后验证失败时是否自动回滚
  --self-dev                允许把平台自身代码作为 workspace 分析
  --focus-file TEXT         仅聚焦某个文件或目录，减少扫描范围和上下文长度
  --mode [single|multi]     single 为单智能体，multi 为多智能体协作
  --help                    显示帮助信息
```

## 执行结果示例

### 控制台输出

```
[2025-03-30 12:00:15] INFO | CodeRepairPlatform:run | ============================================================
[2025-03-30 12:00:15] INFO | CodeRepairPlatform:run | [Stage 1] 任务规划与分类
[2025-03-30 12:00:15] INFO | CodeRepairPlatform:run | ============================================================
[2025-03-30 12:00:15] INFO | TaskPlanner:classify_task | [Stage 1.1] 开始任务分类 | input_length=42
[2025-03-30 12:00:15] INFO | TaskPlanner:classify_task | [Stage 1.1] 检测到关键词 → 分类为 BUG_FIX
[2025-03-30 12:00:15] INFO | TaskPlanner:detect_language | [Stage 1.2] 开始语言检测 | workspace_root=/path/to/project
[2025-03-30 12:00:15] INFO | TaskPlanner:detect_language | [Stage 1.2] 主要语言检测为 GO
[2025-03-30 12:00:15] INFO | TaskPlanner:plan | [Stage 1] 规划完成 | task_type=bug_fix | language=go

[2025-03-30 12:00:16] INFO | CodeRepairPlatform:run | [Stage 2] 设置检索范围
[2025-03-30 12:00:16] INFO | CodeRepairPlatform:run |   - 平台根目录: /home/user/CodeRepair
[2025-03-30 12:00:16] INFO | CodeRepairPlatform:run |   - 项目根目录: /home/user/sample_go_project
[2025-03-30 12:00:16] INFO | CodeRepairPlatform:run |   - 排除规则已激活（防止平台代码污染）

[2025-03-30 12:00:16] INFO | PathFilter:__init__ | [PathFilter] 初始化完成 | platform_root=... | workspace_root=...

[2025-03-30 12:00:16] INFO | RepositoryScanner:scan | [Stage 3] 仓库结构分析 | workspace_root=...
[2025-03-30 12:00:16] INFO | RepositoryScanner:scan | [Stage 3] 扫描完成 | total_files=2 | go_files=2 | py_files=0

... (更多阶段输出) ...

[2025-03-30 12:00:18] INFO | LLMClient:call | [Stage 7] 调用 LLM | model=gpt-4
[2025-03-30 12:00:20] INFO | LLMClient:call | [Stage 7] LLM 调用完成 | tokens_used=456 | finish_reason=stop

[2025-03-30 12:00:21] INFO | Validator:run_command | [Stage 9] 执行验证命令 | cmd=go build ./...
[2025-03-30 12:00:22] INFO | Validator:run_command | [Stage 9] 命令执行成功 | exit_code=0

[2025-03-30 12:00:22] INFO | CodeRepairPlatform:run | [Stage 10] 结果输出与会话保存
[2025-03-30 12:00:22] INFO | CodeRepairPlatform:run | ============================================================
[2025-03-30 12:00:22] INFO | CodeRepairPlatform:run | 执行完成！
[2025-03-30 12:00:22] INFO | CodeRepairPlatform:run | Session 目录: /home/user/CodeRepair/artifacts/session_20250330_120000
[2025-03-30 12:00:22] INFO | CodeRepairPlatform:run | ============================================================

============================================================
执行完成 - 结果摘要
============================================================

任务类型: bug_fix

## LLM 建议

根据代码分析，我发现了 `Calculate` 函数中的 Bug：
- 问题：函数返回 `result - 1` 而不是 `result`
- 修复建议：将返回值改为 `return result`

... (完整的 LLM 响应) ...

## 验证结果

✓ 验证通过

详细信息请查看 artifacts 目录下的完整日志。
```

### Artifacts 目录结构

每次执行都会在 `artifacts/session_YYYYMMDD_HHMMSS/` 下生成完整的执行记录：

```
artifacts/session_20250330_120000/
├── 00_tool_schema.json             # 工具 schema 与权限边界
│
├── 01_input.txt                    # 用户原始输入
│   └── 修复 Calculate 函数返回值错误的问题
│
├── 02_analysis.json                # 任务分析结果
│   └── {"task_type": "bug_fix", "language": "go"}
│
├── 03_retrieval_results.json       # 检索到的代码片段
│   └── 包含 top-5 chunks 及其相关度评分
│
├── 04_prompt.txt                   # 发送给 LLM 的完整 prompt
│   └── [SYSTEM PROMPT]
│       ...
│       [USER PROMPT]
│       ...
│
├── 05_llm_response.md              # LLM 的原始输出
│   └── ```go
│       func (u *User) Calculate(x int) int {
│           result := x * u.Age
│           if result > 1000 {
│               return 1000
│           }
│           return result  // 修复：移除 - 1
│       }
│       ```
│
├── 07_validation_output.json       # 验证命令的执行结果
│   └── {
│         "cmd": "go build ./...",
│         "exit_code": 0,
│         "stdout": "",
│         "stderr": "",
│         "success": true
│       }
│
├── 09_result.md                    # 最终结果摘要
│   └── (人类友好的执行总结)
│
├── 10_evaluation.json              # 单次运行评估指标
│
├── task_report.md                  # 面向交付/复盘的任务报告
├── patch.diff                      # 本次写回产生的 unified diff
├── validate.log                    # 验证命令、stdout/stderr 与退出码
├── review.json                     # reviewer 结论或单智能体审查占位
├── summary.json                    # 质量评估摘要：验证、回滚、人工接管标记
├── tool_calls.json                 # 工具调用审计链路
│
├── session.json                    # 会话上下文（用于 follow-up）
│   └── {
│         "session_id": "20250330_120000",
│         "task_type": "bug_fix",
│         "language": "go",
│         "workspace_root": "/path/to/project",
│         "user_query": "修复...",
│         "created_at": "2025-03-30T12:00:00",
│         "retrieval_summary": "...",
│         "llm_output_summary": "..."
│       }
│
└── runner.log                      # 完整的运行日志
    └── [2025-03-30 12:00:15] INFO - [Stage 1] 任务规划
        [2025-03-30 12:00:16] INFO - [Stage 2-3] 检索范围设置
        [2025-03-30 12:00:16] INFO - [Stage 4] 代码结构分析
        ... (所有 10 个阶段的完整日志)
```

## 关键设计决策

### 1. 严格的检索范围隔离（解决 RAG 污染）

**问题**：RAG 检索容易把平台代码也索引进去，污染 LLM 输入。

**设计**：
- `retrieval/filters.py` 的 `PathFilter` 类明确了"平台根"和"工作区根"的概念
- 检索时只读取 workspace_root 目录内的文件
- platform_root 目录被硬编码为排除列表
- 可配置的 `EXCLUDE_PATTERNS` 和 `INCLUDE_EXTENSIONS`

**代码体现**：
```python
# core 中
PLATFORM_ROOT = Path(__file__).parent

# retrieval/filters.py 中
def is_valid_path(self, file_path: Path) -> bool:
    # 检查必须在 workspace 内
    file_path.relative_to(self.workspace_root)
    
    # 检查必须在 platform 外
    try:
        file_path.relative_to(self.platform_root)
        return False  # 在 platform 内，排除！
    except ValueError:
        pass  # 不在 platform 内，这是好的
    # ...
```

### 2. 清晰的 10 阶段执行流程（解决黑盒问题）

每个阶段都有明确的日志和中间结果保存：

```
Stage 1: [任务规划] 分类 & 语言检测
Stage 2-3: [检索准备] 平台 ↔ workspace 隔离 & 仓库扫描
Stage 4: [代码分析] AST 提取
Stage 5: [代码检索] BM25 相似度
Stage 6: [Prompt 组装] 构建输入
Stage 7: [LLM 调用] API 请求
Stage 8: [结果处理] 解析输出
Stage 9: [验证执行] go build / go test
Stage 10: [结果输出] 保存 & 总结
```

### 3. 支持多轮对话（继续追问）

**设计**：
- `core/session.py` 保存会话上下文到 JSON 文件
- 下一轮可以加载上一轮的 session，获取检索结果和 LLM 输出摘要
- Prompt 中包含历史记录，让 LLM 有上下文进行优化

### 4. 模块职责清晰（便于讲解）

```
core/planner.py       → 任务分类、编排
retrieval/filters.py  → RAG 范围控制
retrieval/scanner.py  → 文件扫描
retrieval/chunker.py  → 代码分块
retrieval/retriever.py → 相似度检索
analyzers/go_ast.py   → AST 解析
llm/client.py         → LLM API 封装
llm/prompt_builder.py → Prompt 组装
executors/validator.py → 命令执行
outputs/artifact_manager.py → 结果保存
```

每个模块都能单独讲清楚"我做什么""为什么这样做"，非常适合简历讲解。

## 技术选择理由

| 组件 | 选择 | 理由 |
|------|------|------|
| CLI | Click | 轻量级，易讲解，不依赖重框架 |
| 日志 | loguru | 彩色输出，易阅读，性能好 |
| LLM | OpenAI SDK | 标准化，兼容多个提供商 |
| 检索 | 简单 BM25 | MVP 版本够用，留有向量库的升级空间 |
| Go 分析 | 正则 + 轻量 AST | 不希望过度复杂，功能够用即可 |
| 命令执行 | subprocess | 标准库，真实执行 |
| 会话存储 | JSON | 轻量级，易查看，易集成 |

## 为什么不用大框架？

- **LangChain**：过度设计，不利于讲清思路
- **LangGraph**：绑定度太高，不推荐作为学习项目
- 我们的方案：自己实现清晰的 pipeline，更能展示设计能力

## 扩展方向

未来可以不改核心的情况下：

1. **检索升级**：将 BM25 替换为向量数据库（Milvus / Weaviate）
2. **分析升级**：集成 tree-sitter 做完整的 AST 解析
3. **验证升级**：支持更多自定义命令、预定义的测试流程
4. **UI 升级**：添加简单的 Web 界面或 VSCode 插件
5. **多语言**：支持更多编程语言（Python / Java / Rust 等）

所有这些都不需要改动核心的 `core/`, `llm/`, `outputs/` 模块。

## 常见问题

### Q: 如何更换 LLM 提供商？

A: 编辑 `.env` 文件，改变 `OPENAI_API_BASE` 即可：
```env
# 改为本地 Ollama
OPENAI_API_BASE=http://localhost:11434/v1

# 改为 Siliconflow
OPENAI_API_BASE=https://api.siliconflow.cn/v1
```

### Q: 检索为什么只返回 5 个 chunks？

A: 这是 `config.py` 中的 `RETRIEVAL_TOP_K=5`。可以修改以得到更多或更少的结果。

### Q: 怎样添加新的验证命令？

A: 编辑 `executors/validator.py`，添加新方法即可：
```python
def run_custom_command(self, cmd: str) -> Dict[str, Any]:
    return self.run_command(cmd)
```

### Q: Artifacts 占用太多空间怎么办？

A: 现在支持自动清理旧 session。

CLI 临时控制：
```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "分析 Calculate 函数" \
  --artifacts-keep 10 \
  --artifacts-retention-days 7 \
  --no-validate
```

`.env` 固定配置：
```env
ARTIFACT_AUTO_CLEANUP=true
ARTIFACT_RETENTION_SESSIONS=20
ARTIFACT_RETENTION_DAYS=14
```

### Q: 怎么跑一组可比较的 benchmark？

A: 运行：
```bash
./.venv/bin/python scripts/run_benchmarks.py --provider groq --validation-mode local --limit 2
```

报告会落到 `artifacts/benchmark_reports/`。

## 和讲解简历时有用的点

这个项目可以讲清楚：

1. **问题驱动**："我看到原项目的 RAG 检索把平台代码也混进去了，这样污染了 LLM 的上下文，所以我......"

2. **设计能力**："我用 `PathFilter` 类明确隔离了平台和工作区目录，这样检索时就只会读目标项目的代码。"

3. **工程化思维**："每个执行阶段都有清晰的日志和中间结果，不是黑盒。用户能看到 platform 在做什么。"

4. **系统性思维**："不是堆框架，而是自己设计了一个 10 阶段的 pipeline，每个阶段职责清晰。"

5. **多轮对话**："支持用户第二轮、第三轮继续追问，通过保存会话上下文来加快响应。"

6. **可观测性**："所有执行过程都保存到了 artifacts，支持后续审计和分析。"

## 开发与测试

### 快速测试

```bash
# 测试任务分类
python -c "from core.planner import TaskPlanner; p = TaskPlanner(); print(p.classify_task('修复一个 bug'))"

# 测试路径过滤
python -c "from retrieval.filters import PathFilter; from pathlib import Path; pf = PathFilter(Path('.'), Path('./examples/sample_go_project')); print(len(pf.scan_valid_files()))"
```

### 单元测试（待补充）

```bash
pytest tests/
```

## 许可证

MIT

## 贡献

欢迎 Issue 和 Pull Request。

---

**最后更新**：2025-03-30

**作者**：CodeRepair Team
