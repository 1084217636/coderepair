项目二：面向 Go 单仓场景的研发辅助平台  核心开发

项目描述：基于 Python 实现面向 Go 单仓代码仓库的研发辅助平台，并使用 LangGraph 构建多智能体协作链路，围绕任务评估、上下文增强、局部代码修复、执行验证、结果留痕与失败回滚形成闭环，支持以 CLI / 工具方式接入研发流程，提升代码问题定位、修改与验证效率。

技术栈：Python、LLM、多 Provider 路由、LangGraph、轻量 AST、Hybrid RAG、Ollama Embedding、Docker、Mock、Diff/Artifacts、Backup/Rollback

核心功能：
- 设计需求理解、复杂度评估、仓库扫描、上下文增强、代码生成、执行验证与结果留痕的多阶段执行链路。
- 基于 StateGraph 设计 `planner / implementer / reviewer` 三阶段协作流程，支持审查反馈驱动的单轮修正闭环。
- 基于错误类型、修改范围、目录深度与代码复杂度设计任务分级规则，并支持按 provider / model 切换推理后端，控制推理成本。
- 基于 Go 轻量 AST 提取 `package / import / function / method / call relation` 等结构信息，并补充依赖跨度分析。
- 引入 Ollama 语义 embedding 与本地持久化向量检索，结合仓内代码、文档及 `Dockerfile / go.mod / Makefile` 等工程文件实现 Hybrid RAG。
- 设计 `apply / validate / rollback` 保护机制，支持本地与 Docker 双模式验证，并对规划、执行、审查、验证等阶段统一留痕，沉淀 diff、日志、评估指标与执行产物用于回溯分析。
