# DeerFlow 二开模块卡片

## 1. CodeChangeStore

位置：

```text
backend/packages/harness/deerflow/code_change/store.py
```

职责：

```text
管理 project 和 task 的本地 JSON 存储。
```

关键函数：

```text
create_project
list_projects
get_project
new_task_dir
save_task
append_timeline
```

数据位置：

```text
DEER_FLOW_HOME/code-change
或当前目录 .deer-flow/code-change
```

## 2. State Machine

位置：

```text
backend/packages/harness/deerflow/code_change/state_machine.py
```

职责：

```text
约束任务状态不能乱跳，形成可审计任务流。
```

当前状态：

```text
CREATED
QUEUED
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

## 3. Repo Scanner

位置：

```text
backend/packages/harness/deerflow/code_change/repo_scanner.py
```

职责：

```text
扫描目标仓库，识别 Go / Python / JS / TS / Java / Markdown / YAML / JSON 文件。
```

排除：

```text
.git
.venv
node_modules
dist
build
__pycache__
.deer-flow
```

## 4. Context Retriever

位置：

```text
backend/packages/harness/deerflow/code_change/context_retriever.py
```

职责：

```text
根据需求关键词，对路径、摘要、内容做轻量打分，召回 Top-K 相关文件。
```

当前是轻量关键词召回，不是完整向量 RAG。这样更适合第一阶段闭环。

## 5. Test Runner

位置：

```text
backend/packages/harness/deerflow/code_change/test_runner.py
```

职责：

```text
在目标仓库目录执行 test_command，把 stdout/stderr 保存到 test.log。
```

当前执行方式：

```text
subprocess.run(shell=True, cwd=repo_path)
```

V5 再接 DeerFlow sandbox。

## 6. Report Writer

位置：

```text
backend/packages/harness/deerflow/code_change/report_writer.py
```

职责：

```text
生成 task_report.md 和 audit.json。
```

报告内容：

```text
任务 ID
项目 ID
需求
状态
召回上下文
Patch 结果
测试结果
PR 草稿路径
错误信息
```

## 7. CLI

位置：

```text
backend/packages/harness/deerflow/code_change/cli.py
```

职责：

```text
提供无需前端和 API 的最小演示入口。
```

命令：

```text
project create
project list
project status
task run
task enqueue
worker run-once
```

面试价值：

```text
这证明二开不是只改 README，而是已经有可运行的 project-based workflow。
```

## 8. Patcher

位置：

```text
backend/packages/harness/deerflow/code_change/patcher.py
```

职责：

```text
应用统一 diff，生成 patch.diff、patch_check.log、patch_apply.log，并统计修改文件、增删行。
```

关键函数：

```text
apply_patch_file
apply_patch_text
extract_changed_files
validate_patch_paths
write_pr_body
```

安全边界：

```text
拒绝绝对路径
拒绝包含 .. 的路径
先执行 git apply --check
check 通过后才执行 git apply
```

产物：

```text
patch.diff
patch_check.log
patch_apply.log
pr_body.md
audit.json
```

面试价值：

```text
这让项目从“只跑测试和写报告”升级成“代码变更、测试验证、PR 草稿”的研发效能闭环。
```

## 9. Code Change Router

位置：

```text
backend/app/gateway/routers/code_change.py
backend/app/gateway/app.py
```

职责：

```text
把 project/task/report/timeline 能力暴露成 FastAPI 接口，使项目从 CLI 工具升级为研发效能平台 API。
```

核心接口：

```text
POST /api/code-change/projects
GET  /api/code-change/projects
GET  /api/code-change/projects/{project_id}
GET  /api/code-change/projects/{project_id}/timeline
POST /api/code-change/projects/{project_id}/tasks
GET  /api/code-change/projects/{project_id}/tasks/{task_id}
GET  /api/code-change/projects/{project_id}/tasks/{task_id}/report
GET  /api/code-change/projects/{project_id}/tasks/{task_id}/pr-body
POST /api/code-change/worker/run-once
```

当前边界：

```text
V4 默认创建 QUEUED 任务；worker/run-once 用于本地演示和测试。生产化应把 worker 独立成常驻进程。
```

## 10. Worker

位置：

```text
backend/packages/harness/deerflow/code_change/worker.py
```

职责：

```text
把任务创建和任务执行拆开：API/CLI 可以只创建 QUEUED 任务，Worker 再消费队列并执行 patch/test/report。
```

关键函数：

```text
create_task
execute_task
run_task_now
run_next_task
retry_task
```

数据结构：

```text
task_queue.jsonl
task.json
requested_patch.diff
timeline.jsonl
```

当前边界：

```text
V5 增加了手动 retry、attempt_count 和 metrics，但队列仍是单机 JSONL。
多 worker 并发、租约、退避重试和死信队列留到后续生产化版本。
```

面试价值：

```text
能解释为什么 V3 同步 API 会阻塞，以及如何演进成公司里的 Task Service + Worker 模式。
```

## 11. Worker Metrics

位置：

```text
backend/packages/harness/deerflow/code_change/store.py
backend/app/gateway/routers/code_change.py
```

职责：

```text
统计当前项目或全局任务状态，给控制台、运维面板和面试演示提供可观察性入口。
```

关键函数：

```text
CodeChangeStore.list_tasks
CodeChangeStore.task_metrics
GET /api/code-change/metrics
```

核心指标：

```text
total_tasks
status_counts
queue_depth
failed_count
retryable_failed_count
exhausted_failed_count
attempts_total
```

面试价值：

```text
能说明平台不只是“让 Agent 跑一下”，而是把任务状态、失败率和队列积压作为研发效能系统的一部分来观察。
```

## 12. Workspace Sandbox

位置：

```text
backend/packages/harness/deerflow/code_change/workspace.py
backend/packages/harness/deerflow/code_change/worker.py
```

职责：

```text
为每个任务创建 artifacts/workspace 本地隔离工作区，让 patch/test 不直接污染项目主仓库。
```

关键结构：

```text
Workspace
prepare_workspace
Task.source_repo_path
Task.workspace_path
Task.sandbox_kind
```

执行链路：

```text
scan original repo
  -> retrieve context from original repo
  -> copy repo to workspace
  -> apply patch in workspace
  -> run tests in workspace
  -> report workspace evidence
```

当前边界：

```text
local-copy 是文件系统隔离，不是容器隔离。它能防止主仓库被 patch 污染，但不能限制 CPU、内存、网络和系统调用。
```

面试价值：

```text
能回答“AI 改错代码怎么办”：不让 Agent 直接改主分支或主仓库，而是在可丢弃 workspace 中改，测试通过后再进入 PR/人工审核。
```

## 13. Sandbox Policy

位置：

```text
backend/packages/harness/deerflow/code_change/sandbox_policy.py
backend/packages/harness/deerflow/code_change/test_runner.py
```

职责：

```text
约束测试命令的执行方式，避免 test_command 直接以 shell=True 执行任意命令。
```

关键结构：

```text
SandboxPolicy
SandboxPolicyViolation
build_command
write_policy
```

默认策略：

```text
allowed_executables = python / python3 / pytest / go / npm / pnpm / yarn / mvn / gradle
timeout_seconds = 120
max_log_bytes = 64000
shell=False
```

产物：

```text
sandbox_policy.json
test.log
```

当前边界：

```text
还不是容器隔离。V7 解决的是命令执行边界和审计证据，CPU/内存/网络限制要靠后续 Docker/DeerFlow sandbox。
```

## 14. PR Handoff

位置：

```text
backend/packages/harness/deerflow/code_change/pr_handoff.py
```

职责：

```text
在 patch/test 通过后生成可人工审核的 GitHub draft PR 交付包。
```

产物：

```text
pr_handoff.json
create_draft_pr.sh
```

关键内容：

```text
repo_url
source_repo_path
base_branch
branch_name
commit_message
patch_path
changed_files
test_result
gh pr create --draft command
```

当前边界：

```text
系统不自动 push、不自动创建 PR。V8 的目标是把任务闭环交付到“人类可审核执行”的最后一步。
```

## 15. V3 API 当前边界

```text
V3 仍同步执行任务，适合演示和本地平台闭环；生产化需要任务队列和 worker。
```

性能瓶颈：

```text
patch/test 命令可能耗时较长，同步 HTTP 请求会占用请求线程。
```

优化方向：

```text
API 只创建任务，Redis/DB 队列交给 worker；前端轮询 task status 或走 SSE。
```
