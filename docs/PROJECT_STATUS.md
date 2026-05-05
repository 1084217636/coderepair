# 项目现状与后续方向

## 当前定位

CodeRepair 现在是一个基于 Python 实现的 Go 仓库研发辅助平台原型，重点覆盖：

- 任务分类与阶段编排
- Go 仓库扫描与轻量 AST 提取
- 检索增强、向量 RAG 与平台代码隔离
- 多 Provider LLM 调用
- 本地 / Docker 验证、结果留痕与最小写回闭环
- benchmark 评估与 artifact 自动清理
- Tool Calling 审计、标准任务报告、patch/validation/review 交付产物

## 当前架构

核心入口与职责如下：

- `app.py`：主 CLI 与单次修复流程编排
- `core/`：规划、会话、复杂度评估、工作流 scaffold
- `llm/`：LLM 客户端与 Prompt 构造
- `retrieval/`：扫描、切块、检索、路径隔离
- `docs/VECTOR_RAG.md`：当前向量 RAG 设计说明
- `analyzers/`：语言检测与 Go 结构分析
- `executors/`：本地编译/测试验证
- `patcher/`：文件写回、备份、回滚
- `outputs/`：diff、artifact、结果摘要
- `core/tool_calling.py`：工具 schema、权限边界和调用审计
- `sandbox/`：Docker 沙盒验证与降级能力

## 单智能体 / 多智能体现状

当前项目只有稳定的“单智能体编排”能力：

- `app.py` 使用一个主编排器串起分析、检索、提示构造、调用 LLM、解析输出、验证与留痕
- `core/langgraph_workflow.py` 是一个顺序工作流 scaffold，不是成熟的多智能体协作系统
- 仓库里没有真正的 agent-to-agent 分工、消息传递、角色隔离或并行子代理执行
- 自举开发时可通过 `--self-dev --focus-file <path>` 让平台分析自身局部代码

当前也已经有一个“多智能体 MVP”：

- 入口仍在 `app.py`
- 角色为 `planner / implementer / reviewer`
- 使用 LangGraph `StateGraph` 实现最小状态图
- reviewer 可触发一轮 implementer 修订
- 轨迹会留痕到 `04_multi_agent_trace.json` / `04_multi_agent_trace.md`

但它目前仍属于可用原型，不等同于成熟的 agent graph 系统。

如果后续要对外说明，建议写成：

- 已实现单智能体研发辅助主链路
- 已实现基于 LangGraph 的 `planner / implementer / reviewer` 多智能体 MVP
- 预留了更复杂的工作流和路由扩展位

## 当前已验证可用的功能

- `groq` 真实调用
- `aicanapi` 真实调用
- mock 回退
- Go 仓库扫描与路径过滤
- 轻量 AST 提取
- 基于检索结果的 Prompt 构建
- 本地 sqlite 向量库 + 混合 RAG 检索
- BM25 词法检索与可选轻量 rerank
- `go build` / `go test` 本地验证
- `validation-mode=auto/local/docker` 的验证入口
- Docker 不可用时自动降级到本地验证
- artifacts 留痕
- benchmark 报告输出与 variant 对比报告
- artifacts 自动清理（防止 session 无限增长）
- 显式 `--apply-file` 的保守式单文件写回
- 写回后验证失败自动回滚到备份版本
- `--apply-file` 已做 workspace 边界校验，拒绝 `../` 或绝对路径逃逸
- `cli.py fix --repo ... --task ...` 产品化入口
- `cli.py check-config` 配置检查入口，覆盖必填字段、重复 ID、引用缺失与类型漂移
- `cli.py suggest-tests` Go 单测补全建议入口，输出缺失测试目标和边界用例
- `task_report.md`、`patch.diff`、`validate.log`、`review.json`、`summary.json`、`tool_calls.json` 标准交付产物
- `go-repair` benchmark 套件包含 30 个 Go 工程任务 case

## 仍待补齐的重点

- 真正的多智能体编排
- 更完整的 Go AST 依赖/调用关系
- 更强的代码与文档 RAG
- 多文件级别的正式 snapshot / rollback 生命周期
- 面向用户的更稳定自动修复闭环
- 多智能体链路的 provider 稳定性与更强的上下文压缩
- 更强的 rerank（如 cross-encoder）和更大规模 case 集
- 面向大规模仓库时的 ANN 向量索引升级

## 推荐使用顺序

1. 先看 `README.md`
2. 再看 `SIMPLE_USAGE.md`
3. 测试时看 `TESTING_GUIDE.md`
4. 需要 provider 配置时看 `docs/LLM_SETUP.md`
5. 需要 Docker 安装时看 `docs/DOCKER_SETUP.md`
6. 需要确认多智能体阶段边界时看 `docs/MULTI_AGENT_BOUNDARY.md`
