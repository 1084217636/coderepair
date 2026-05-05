# 项目二简历定稿

## 已确认终稿（与导出稿一致）

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

## 面试可追问版

项目二：面向 Go 单仓场景的研发辅助平台  核心开发

项目描述：基于 Python 实现面向 Go 单仓代码仓库的研发辅助平台，并使用 LangGraph 构建多智能体协作链路；围绕任务评估、上下文增强、局部代码修复、执行验证、结果留痕与失败回滚形成闭环，重点解决大模型直接改代码时“上下文不准、修改不稳、结果不可验证”的问题。

技术栈：Python、LLM、多 Provider 路由、LangGraph、轻量 AST、Ollama Embedding、Hybrid RAG、Docker、Mock、Diff/Artifacts、Backup/Rollback

核心功能：

- 设计需求理解、复杂度评估、仓库扫描、上下文准备、代码生成、执行验证与结果留痕的多阶段执行链路，将单智能体主链与多智能体协作链统一到同一套执行框架中。
- 基于 StateGraph 设计 `planner / implementer / reviewer` 三阶段协作流程，并通过单轮修正闭环降低复杂任务下一次生成直接写回的风险。
- 设计 PathFilter 与工程文件白名单机制，隔离平台源码、缓存目录与无关文件污染，支持 `go.mod / Dockerfile / Makefile / README` 等工程文件进入检索与写回链路。
- 基于 Go 轻量 AST 提取 `package / import / function / method / call relation` 等结构信息，并补充依赖跨度分析，用于复杂度评估、上下文组织与问题定位。
- 引入 Ollama 语义 embedding 与本地持久化向量检索层，结合词法召回实现 Hybrid RAG；在本地模型不可用时提供 hashing fallback，保证检索链可用性与低成本演示能力。
- 设计 `apply / validate / rollback` 保护机制，支持本地与 Docker 双模式验证，并沉淀 diff、日志、评估结果与执行产物，便于定位失败原因和复盘修复过程。
- 补充运行评估指标，对检索命中、修复状态、验证结果与执行模式进行量化记录，支持比较单智能体与多智能体、词法检索与混合检索的效果差异。

## 最终简历格式版

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

## 当前稳定版

**项目名称**

面向 Go 单仓场景的研发辅助平台

**项目描述**

基于 Python 实现面向 Go 单仓场景的研发辅助平台，围绕任务评估、上下文增强、局部代码修复、执行验证与结果留痕形成辅助闭环，重点提升代码问题定位与修复效率，并保证修改结果具备可验证性和可回溯性。

**技术栈**

Python、Go 仓库分析、LLM、多 Provider 路由、LangGraph、轻量 AST、RAG、Docker、Mock、Diff/Artifacts、Backup/Rollback

**核心功能**

- 设计多阶段研发辅助流程，覆盖需求理解、复杂度评估、仓库扫描、上下文准备、代码生成、执行验证与结果留痕。
- 基于 LangGraph StateGraph 设计 `planner / implementer / reviewer` 3 阶段协作流程，支持审查反馈驱动的单轮修正闭环。
- 设计任务分级与模型路由机制，结合错误类型、修改范围、目录深度与代码复杂度选择不同 provider 与 model。
- 基于 Go 轻量 AST 提取 `package / import / function / type` 等结构信息，并结合仓内代码检索实现上下文增强。
- 设计 `apply / validate / rollback` 保护机制，支持本地与 Docker 两种验证模式，并输出 diff、日志与执行产物用于回溯分析。

## 推荐终稿

**项目名称**

面向 Go 单仓场景的 Agent 研发辅助平台

**项目概述**

基于 Python 实现面向 Go 单仓代码库的研发辅助平台，并使用 LangGraph 构建多智能体协作链路，围绕任务评估、上下文增强、局部代码修复、执行验证与结果留痕形成闭环。

**核心功能**

- 设计需求理解、复杂度评估、仓库扫描、上下文准备、代码生成、执行验证与结果留痕的多阶段执行链路。
- 基于 StateGraph 设计 `planner / implementer / reviewer` 三阶段协作流程，支持审查反馈驱动的单轮修正闭环。
- 设计任务分级与模型路由规则，结合错误类型、修改范围、目录深度与代码复杂度控制推理成本。
- 基于 Go 轻量 AST 提取 `package / import / function / type` 等结构信息，并结合仓内代码检索实现上下文增强。
- 设计 `apply / validate / rollback` 保护机制，支持本地与 Docker 双模式验证，输出 diff、日志与执行产物用于回溯分析。

## 增强版

适用条件：补上 `Dockerfile / go.mod / Makefile` 等关键工程文件的检索与写回支持后使用。

**核心功能**

- 设计多阶段研发辅助流程，覆盖需求理解、复杂度评估、仓库扫描、上下文准备、代码生成、执行验证与结果留痕。
- 基于 LangGraph StateGraph 设计 `planner / implementer / reviewer` 3 阶段协作流程，支持审查反馈驱动的单轮修正闭环。
- 设计任务分级与模型路由机制，结合错误类型、修改范围、目录深度与代码复杂度选择不同 provider 与 model。
- 基于 Go 轻量 AST 提取 `package / import / function / type` 等结构信息，并支持 `Dockerfile / go.mod / Makefile` 等关键工程文件检索。
- 设计 `apply / validate / rollback` 保护机制，支持本地与 Docker 两种验证模式，并输出 diff、日志与执行产物用于回溯分析。

## 假设完成版

适用条件：已补齐评估体系、Go 调用关系分析、真实语义 embedding 与工程文件支持后使用。

**项目名称**

面向 Go 单仓场景的 Agent 研发辅助平台

**项目概述**

基于 Python 实现面向 Go 单仓代码库的研发辅助平台，并使用 LangGraph 构建多智能体协作链路，围绕任务评估、上下文增强、局部代码修复、执行验证与结果留痕形成闭环。

**核心功能**

- 设计需求理解、复杂度评估、仓库扫描、上下文准备、代码生成、执行验证与结果留痕的多阶段执行链路，并建立检索命中率、修复成功率与验证通过率评估体系。
- 基于 StateGraph 设计 `planner / implementer / reviewer` 三阶段协作流程，支持审查反馈驱动的单轮修正闭环，并对单智能体与多智能体效果进行对比评估。
- 基于 Go AST 提取 `package / import / function / type` 等结构信息，并补充调用关系、依赖跨度分析，支持更细粒度的上下文构建与任务分级。
- 引入真实语义 embedding 与本地向量库，结合仓内代码、文档及 `Dockerfile / go.mod / Makefile` 等工程文件实现混合 RAG 检索。
- 设计 `apply / validate / rollback` 保护机制，支持本地与 Docker 双模式验证，输出 diff、日志与执行产物用于回溯分析。

## 边界提醒

- 当前不要写 Redis 已落地。
- 当前不要写完整 Snapshot 系统，实际是 Backup/Rollback。
- 当前不要写 Go 调用关系图已完成，现阶段以轻量结构分析为主。
