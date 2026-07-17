# DeerFlow 二开代码地图

本项目基于 GitHub 上的 `bytedance/deer-flow` 进行二次开发，不复刻 DeerFlow，而是在它的 Agent harness 底座上补一个项目级研发任务助手闭环。

## 1. 原 DeerFlow 关键目录

| 目录 | 作用 | 二开关注点 |
| --- | --- | --- |
| `backend/app/gateway/` | FastAPI 网关，提供 threads、runs、memory、skills、models 等 API | V3 已接 `code_change` router |
| `backend/app/gateway/routers/` | API 路由模块 | 参考 `memory.py`、`skills.py` 的 Pydantic + APIRouter 风格 |
| `backend/packages/harness/deerflow/agents/` | Lead agent、thread state、goal state、middleware | V1 不改，V2 后再接 Agent |
| `backend/packages/harness/deerflow/agents/memory/` | 长期记忆、memory updater、prompt 注入 | 后续 project memory 可参考 |
| `backend/packages/harness/deerflow/sandbox/` | Local / container sandbox 抽象、文件和命令工具 | 后续把 test runner 接入 sandbox |
| `backend/packages/harness/deerflow/tools/` | 内置工具、task tool、tool search | 后续把代码变更能力包装成 tool |
| `backend/packages/harness/deerflow/skills/` | skill 安装、解析、权限、安全扫描 | 后续可把 code-change 固化为 skill |
| `backend/packages/harness/deerflow/persistence/` | SQLAlchemy persistence、run/thread metadata | V1 先用 JSON 文件，后续再接 persistence |
| `frontend/` | Next.js 前端 | 第一阶段不改 |

## 2. 本次二开新增目录

```text
backend/packages/harness/deerflow/code_change/
```

它是独立 MVP 包，不侵入原 Agent 主链路：

```text
Project
  ↓
Task
  ↓
Queue / Worker
  ↓
Repo Scan
  ↓
Context Retrieve
  ↓
PATCH_RECEIVED / VALIDATING_PATCH / Apply Patch
  ↓
Run Tests
  ↓
PR Handoff
  ↓
Task Report
  ↓
Timeline / Audit
```

## 3. 新增文件地图

| 文件 | 职责 |
| --- | --- |
| `models.py` | Project、Task、TaskStatus、TaskStep、CodeFile、RetrievedContext、PatchResult、TestResult |
| `store.py` | JSON 文件存储，保存 project、task、timeline |
| `state_machine.py` | 任务状态机和阶段跳转校验 |
| `worker.py` | 创建 QUEUED 任务、消费队列、执行 scan/patch/test/report |
| `repo_scanner.py` | 扫描仓库文件，排除 `.git`、`.venv`、`node_modules` 等噪音 |
| `context_retriever.py` | 基于需求关键词召回相关代码文件 |
| `patcher.py` | 校验并应用 unified diff，生成 patch 日志和 PR 草稿 |
| `workspace.py` | 为每个任务准备 local-copy workspace，避免污染主仓库 |
| `sandbox_policy.py` | 保存命令白名单、超时、日志截断等执行边界 |
| `test_runner.py` | 使用 shell=False 执行项目测试命令并保存 `test.log` |
| `pr_handoff.py` | 生成 `pr_handoff.json` 和 `create_draft_pr.sh` |
| `report_writer.py` | 生成 `task_report.md`、patch 摘要和 `audit.json` |
| `cli.py` | 命令行入口：project create/list/status、task run |
| `.github/workflows/code-change-platform.yml` | 二开分支专属 CI：定向 Ruff、code_change pytest、Gateway/package import smoke |

## 4. 当前 CLI 链路

```text
python -m deerflow.code_change.cli project create demo
  ↓
CodeChangeStore.create_project
  ↓
projects.json / project.json / timeline.jsonl

python -m deerflow.code_change.cli task run demo "需求"
  ↓
run_task
  ↓
Task CREATED
  ↓
PLANNING
  ↓
scan_repo
  ↓
RETRIEVING_CONTEXT
  ↓
retrieve_context
  ↓
PATCH_RECEIVED / VALIDATING_PATCH / APPLYING_PATCH（带 --patch-file 时）
  ↓
apply_patch_file
  ↓
RUNNING_TESTS
  ↓
run_tests
  ↓
REVIEWING
  ↓
write_pr_body（带 patch 且测试通过时）
  ↓
HANDOFF_READY / FAILED
  ↓
write_reports
  ↓
task.json / task_report.md / test.log / audit.json

python -m deerflow.code_change.cli task enqueue demo "需求"
  ↓
Task QUEUED
  ↓
task_queue.jsonl

python -m deerflow.code_change.cli worker run-once
  ↓
run_next_task
  ↓
HANDOFF_READY / FAILED
```

## 5. 当前产物结构

```text
.deer-flow/code-change/
├── projects.json
├── task_queue.jsonl
└── projects/
    └── demo/
        ├── project.json
        ├── timeline.jsonl
        └── tasks/
            └── task_xxx/
                ├── task.json
                ├── patch.diff
                ├── patch_check.log
                ├── patch_apply.log
                ├── pr_body.md
                ├── pr_handoff.json
                ├── create_draft_pr.sh
                ├── workspace_manifest.json
                ├── sandbox_policy.json
                ├── task_report.md
                ├── test.log
                └── audit.json
```

## 6. API 接入点

V3 已接：

```text
backend/app/gateway/routers/code_change.py
/api/code-change/projects
/api/code-change/projects/{project_id}
/api/code-change/projects/{project_id}/timeline
/api/code-change/projects/{project_id}/tasks
/api/code-change/projects/{project_id}/tasks/{task_id}
/api/code-change/projects/{project_id}/tasks/{task_id}/report
/api/code-change/projects/{project_id}/tasks/{task_id}/pr-body
/api/code-change/projects/{project_id}/tasks/{task_id}/retry
/api/code-change/worker/run-once
/api/code-change/metrics
```

收尾后生产化再考虑：

```text
Docker / DeerFlow sandbox
DeerFlow memory 或 persistence
Redis Stream / PostgreSQL queue
Prometheus / Grafana
GitHub App 权限审批
```
