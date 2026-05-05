# CodeRepair 简明使用说明

这份说明以“先跑起来、先看到效果”为目标，只写当前仓库里已经验证过的最小用法。

## 1. 直接运行演示

如果你只是想先确认项目能跑：

```bash
cd /home/xiaobin/myproject/CodeRepair
./.venv/bin/python examples/demo.py
```

这个命令不依赖真实 LLM，即使没配 API Key 也能看到：

- 任务分类
- Go 仓库扫描
- AST 提取
- Prompt 组装
- `go build` 验证
- artifacts 留痕

## 2. 跑主流程

对示例 Go 项目执行一次分析：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "修复 Calculate 函数返回值错误的问题" \
  --validation-mode auto
```

结果会落到 `artifacts/session_*/`，重点看：

- `02_analysis.json`
- `02_call_graph.json`
- `02_go_precheck.json`
- `03_retrieval_results.json`
- `04_prompt.txt`
- `05_llm_response.md`
- `07_validation_output.json`
- `09_result.md`
- `10_evaluation.json`

当前默认会使用 `hybrid` RAG：

- 本地 sqlite 向量库
- `Ollama embeddinggemma` 语义 embedding
- 词法检索兜底

向量索引会落到 `.coderepair_vector_db/vectors.sqlite3`。
如果本地没装 Ollama 或服务未启动，会自动回退到 hashing embedding。

推荐先准备本地 embedding：

```bash
ollama serve
ollama pull embeddinggemma
```

## 3. 切换 Provider / Model

可以不改代码，直接覆盖：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "分析 Calculate 函数" \
  --provider ollama \
  --model llama2 \
  --no-validate
```

常见 provider：

- `openai`
- `groq`
- `ollama`
- `aicanapi`

如果没有可用 API Key，非 `ollama` provider 会自动回退到 mock。
当前更稳的 Groq 默认模型是 `llama-3.3-70b-versatile`，AiCan 默认模型是 `claude-opus-4-6`。

## 3.1 多智能体模式

如果你想让多个角色协作完成一次任务，可以打开 `--mode multi`：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "修复 Calculate 函数返回值错误的问题" \
  --provider aicanapi \
  --model claude-sonnet-4-6 \
  --mode multi \
  --no-validate
```

当前 multi 模式包含：

- `planner`
- `implementer`
- `reviewer`

如果 reviewer 判定需要修改，会触发一轮 implementer 修订。
当前这条 3 角色链由 LangGraph `StateGraph` 编排。
轨迹会写入 `04_multi_agent_trace.json` 和 `04_multi_agent_trace.md`。

## 4. 最小写回闭环

当你已经确认 prompt 会产出“完整文件代码块”时，可以显式写回某个文件：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "修复 main.go 里的逻辑错误，并返回完整文件代码" \
  --apply-file main.go \
  --validation-mode auto
```

注意：

- `--apply-file` 是保守模式，只会取第一个代码块
- mock 回复默认不会自动写回文件
- 写回成功后会生成 `08_apply_result.json` 和 `08_applied_diff.md`
- `--validation-mode auto` 会优先尝试 Docker，不可用时自动降级到本地验证
- 默认 `--rollback-on-failure` 开启，写回后验证失败会自动恢复到备份版本
- 当前除了 `.go` 文件，也支持 `Dockerfile / Makefile / go.mod / README.md` 等工程文件进入检索与写回链

## 4.1 验证模式

普通用户最推荐直接用默认的 `auto`：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "请分析 Calculate 函数的问题并给出修复建议" \
  --provider aicanapi \
  --model claude-sonnet-4-6 \
  --validation-mode auto
```

可选模式：

- `auto`：优先 Docker，失败时降级到本地
- `local`：只跑本地命令
- `docker`：只跑 Docker；当前环境没有 Docker 时会标记为未验证

如果你需要覆盖默认验证命令，可以追加：

```bash
--validate-cmd "go test ./..."
```

## 5. 跑测试

推荐先跑这几组：

```bash
./.venv/bin/python -m pytest tests/test_app_cli_flow.py tests/test_patcher.py tests/test_sandbox.py -q
./.venv/bin/python -m pytest tests/test_langgraph_workflow.py -v
./.venv/bin/python -m pytest tests/test_integration.py -q
```

如果要跑更完整的演示测试：

```bash
./.venv/bin/python -m pytest tests/test_end_to_end_demo.py -v
```

如果你想直接产出一份可比较的 benchmark 报告：

```bash
./.venv/bin/python scripts/run_benchmarks.py --provider groq --validation-mode local --limit 2
```

如果你担心 `artifacts/session_*` 过多，可以临时加：

```bash
--artifacts-keep 10 --artifacts-retention-days 7
```

如果你想让项目直接协助后续开发，可以把当前仓库本身当作 workspace：

```bash
./.venv/bin/python app.py \
  --workspace . \
  --focus-file llm/client.py \
  --query "请分析当前仓库下一步最该补的验证闭环，并给出改造建议" \
  --provider aicanapi \
  --model claude-opus-4-6 \
  --self-dev \
  --no-validate
```

`--self-dev` 会允许扫描平台自身源码，`--focus-file` 可以把范围缩到单文件或单目录，适合后续迭代，不适合普通用户项目分析。

## 6. 当前最适合的定位

当前版本更适合：

- 作为 Go 仓库分析/修复助手原型
- 作为多 provider + 向量 RAG + 验证留痕的 Python 平台
- 作为单智能体主链路 + 多智能体 MVP 的研发辅助平台
- 作为后续继续接 Docker 沙盒、Redis 缓存、真实自动修复的基础版本
