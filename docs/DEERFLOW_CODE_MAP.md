# DeerFlow 二开代码地图

本项目基于 GitHub 上的 `bytedance/deer-flow` 进行二次开发，不复刻 DeerFlow，而是在它的 Agent harness 底座上补一个项目级研发任务助手闭环。

## 1. 原 DeerFlow 关键目录

| 目录 | 作用 | 二开关注点 |
| --- | --- | --- |
| `backend/app/gateway/` | FastAPI 网关，提供 threads、runs、memory、skills、models 等 API | 后续 V2 接 `code_change` router |
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
Repo Scan
  ↓
Context Retrieve
  ↓
Run Tests
  ↓
Task Report
  ↓
Timeline / Audit
```

## 3. 新增文件地图

| 文件 | 职责 |
| --- | --- |
| `models.py` | Project、Task、TaskStatus、TaskStep、CodeFile、RetrievedContext、TestResult |
| `store.py` | JSON 文件存储，保存 project、task、timeline |
| `state_machine.py` | 任务状态机和阶段跳转校验 |
| `repo_scanner.py` | 扫描仓库文件，排除 `.git`、`.venv`、`node_modules` 等噪音 |
| `context_retriever.py` | 基于需求关键词召回相关代码文件 |
| `test_runner.py` | 执行项目测试命令并保存 `test.log` |
| `report_writer.py` | 生成 `task_report.md` 和 `audit.json` |
| `cli.py` | 命令行入口：project create/list/status、task run |

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
RUNNING_TESTS
  ↓
run_tests
  ↓
REVIEWING / FAILED
  ↓
write_reports
  ↓
task.json / task_report.md / test.log / audit.json
```

## 5. 当前产物结构

```text
.deer-flow/code-change/
├── projects.json
└── projects/
    └── demo/
        ├── project.json
        ├── timeline.jsonl
        └── tasks/
            └── task_xxx/
                ├── task.json
                ├── task_report.md
                ├── test.log
                └── audit.json
```

## 6. 下一步接入点

V2 再接：

```text
backend/app/gateway/routers/code_change.py
backend/packages/harness/deerflow/code_change/patcher.py
```

V3 再考虑：

```text
DeerFlow sandbox
DeerFlow memory
DeerFlow tools
GitHub PR
IM webhook
```
