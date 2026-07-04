# 项目级 AI 代码变更平台 MVP 计划

下一步文件级修改计划见 [NEXT_IMPLEMENTATION_PLAN.md](NEXT_IMPLEMENTATION_PLAN.md)。

## 1. 项目定位

本项目基于 `bytedance/deer-flow` 克隆而来，最终简历名称建议：

```text
基于 DeerFlow 的项目级 AI 代码变更与 PR 自动化平台
```

核心叙事：

```text
不是重新造一个聊天式代码助手，而是在开源 Agent 框架基础上补充企业研发流程需要的项目级上下文、任务状态机、代码检索、沙箱测试、Diff 解释和 PR 草稿能力。
```

DeerFlow 2.0 已有 sub-agents、memory、sandbox、skills、tools 等底座；本项目只做一个明确缺口：

```text
project-based code change workflow
```

## 2. CodeRepair 归并方式

原 `CodeRepair` 不再单独保留为项目，但它的工程经验迁移到本项目：

| CodeRepair 原能力 | 在本项目中的落点 |
| --- | --- |
| `core/task_state.py` | 代码变更任务状态机 |
| `retrieval/context_policy.py` | 代码上下文召回排序 |
| scanner / chunker | 仓库扫描、文件摘要、函数粒度 chunk |
| docker runner | 沙箱运行测试命令 |
| tool server allowlist | 工具权限、timeout、dry-run、rollback 约束 |
| eval cases | demo 仓库和验收用例 |
| task report / patch / test log | 任务产物标准 |

迁移原则：

```text
只迁移设计和必要小模块，不把 CodeRepair 整仓复制进 DeerFlow。
```

## 3. MVP 闭环

第一版只完成一个简单功能闭环：

```text
创建项目
  ↓
绑定仓库
  ↓
创建代码变更任务
  ↓
召回相关代码
  ↓
生成修改计划
  ↓
生成并应用 patch
  ↓
运行测试命令
  ↓
生成 Diff 解释
  ↓
生成 PR 草稿
  ↓
记录项目历史
```

## 4. 项目级上下文命令

先实现最小命令或 API：

```text
/project create <name>
/project list
/project switch <name>
/project status
/project archive <name>
```

每个 project 保存：

```text
project_id
name
repo_url
repo_path
default_branch
tech_stack
test_command
created_at
updated_at
memory
timeline
```

## 5. 任务状态机

建议状态：

```text
CREATED
PLANNING
RETRIEVING_CONTEXT
GENERATING_PATCH
APPLYING_PATCH
RUNNING_TESTS
REVIEWING
PR_CREATED
FAILED
ROLLED_BACK
```

每一步都要记录：

```text
step_name
status
input_summary
output_summary
started_at
finished_at
error_message
artifact_paths
```

## 6. 数据模型

最小表结构：

```text
project
repository
task
task_step
code_patch
test_result
agent_memory
audit_log
```

第一版可以先用 SQLite / JSON 文件，后续再迁移 PostgreSQL。

## 7. 产物标准

每个任务必须生成：

```text
task_report.md
patch.diff
test.log
pr_body.md
audit.json
```

`pr_body.md` 必须包含：

```text
需求摘要
修改文件
核心改动
测试结果
风险点
回滚建议
```

## 8. Demo Case

只准备 3 个：

```text
1. 给 Go demo 仓库新增一个健康检查接口。
2. 修复一个明确的 Go 单测失败。
3. 给已有 HTTP 参数补校验和错误码。
```

验收标准：

```text
任务能从 CREATED 走到 REVIEWING 或 PR_CREATED。
能看到 patch.diff。
能看到 test.log。
能看到 pr_body.md。
project status 能显示历史任务。
```

## 9. 第一轮开发顺序

```text
1. 找到 DeerFlow 现有 memory、sandbox、tool、task 相关目录。
2. 新增 project workflow 的最小数据结构。
3. 新增 project create/list/status 的 CLI 或 API。
4. 新增 code-change task runner。
5. 接入本地 repo scanner。
6. 先用 mock LLM 生成固定 patch。
7. 运行 test_command。
8. 输出 task_report.md / patch.diff / test.log / pr_body.md。
```

第一轮不要做：

```text
完整前端
复杂多智能体
真实自动合并
企业权限系统
大规模向量库
多语言全覆盖
```

## 10. 简历表述

```text
- 基于开源 Agent 框架 DeerFlow 二次开发项目级代码变更平台，补充 named project、project memory、timeline 和 task tracking，使 Agent 支持跨会话的仓库级需求闭环。
- 设计代码变更任务状态机，覆盖需求录入、上下文召回、Patch 生成、沙箱测试、Diff 解释和 PR 草稿生成等阶段，并记录 task_step、test_result 和 audit_log。
- 构建轻量代码仓库 RAG 流程，结合目录结构、文件摘要、函数符号和历史修改记录召回相关上下文，降低模型误改无关文件概率。
- 引入 Docker / 临时分支执行测试命令，保存 patch.diff、test.log、task_report.md 和 pr_body.md，失败任务可基于日志进入二次修复。
```
