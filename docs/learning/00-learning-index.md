# DeerFlow CodeOps 学习入口

文档对应提交：`7c9059b1`（生成时基线；行号变化时以符号名为准）
生成或最后校验时间：2026-08-04
适用分支：`agent-code-change-platform`

## 学习目标

本项目的目标是理解如何接手复杂 Agent 开源项目，并在其上增加可追踪、可测试、可审核的代码变更控制面。学习者具备 Python 基础语法，但尚不能独立阅读完整 async/FastAPI/Agent/Worker 系统。

## 推荐顺序

1. 先阅读 `README_zh.md` 与现有 `docs/README_STUDY.md`，启动 Gateway 并完成一次最小请求。
2. 阅读 `backend/app/gateway/routers/code_change.py` 的路由，再追 `worker.py` 的任务执行主链。
3. 依次理解 `models.py`、`state_machine.py`、`store.py`、`workspace.py`、`patcher.py`、`test_runner.py` 和 `report_writer.py`。
4. 注入非法 Patch、测试超时或 Worker 重试，观察状态、timeline 和审计产物。
5. 选择一个缺失的小功能，先由学习者预测修改面并写伪代码，再进行 Codex 评审和小步实现。

## 事实边界

- 【上游能力】DeerFlow 的 Agent harness、Skills、Tools、Sub-Agents、Memory、Sandbox 抽象及基础 Gateway 能力来自上游。
- 【当前二开】Project/Task、状态机、轻量代码检索、workspace、Patch/Test、Worker、报告和 PR Handoff 属于本项目增量。
- 【未来方案，当前未实现】真实 GitHub 自动建 PR、完整容器隔离、PostgreSQL/Redis Stream 生产化和多 Worker 集群。
