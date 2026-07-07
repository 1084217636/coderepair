# DeerFlow 二开测试证据

## 1. 当前基线

日期：2026-07-04

说明：

```text
当前环境没有 uv，也没有系统 pytest。
因此本轮使用 compileall + CLI 闭环验证；pytest 测试文件已补充，安装依赖后可直接跑。
```

## 2. 语法验证

命令：

```bash
cd agent-code-change-platform/backend
python3 -m compileall -q packages/harness/deerflow/code_change tests/code_change
```

结果：

```text
通过。
```

## 3. CLI 入口验证

命令：

```bash
cd agent-code-change-platform/backend
PYTHONPATH=packages/harness python3 -m deerflow.code_change.cli --help
```

结果：

```text
通过，输出 project / task 子命令。
```

## 4. V1 闭环验证

命令：

```bash
tmp_repo=$(mktemp -d)
tmp_home=$(mktemp -d)
printf 'def health():\n    return "ok"\n' > "$tmp_repo/app.py"

PYTHONPATH=packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home" \
  project create demo \
  --repo-path "$tmp_repo" \
  --test-command "python3 -c 'print(\"tests ok\")'"

PYTHONPATH=packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home" \
  task run demo "check health function"

PYTHONPATH=packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home" \
  project status demo
```

结果：

```text
created project demo
task=task_xxx status=REVIEWING
project=demo
```

生成产物：

```text
projects.json
projects/demo/project.json
projects/demo/timeline.jsonl
projects/demo/tasks/<task_id>/task.json
projects/demo/tasks/<task_id>/task_report.md
projects/demo/tasks/<task_id>/test.log
projects/demo/tasks/<task_id>/audit.json
```

## 5. 未完成验证

当前未跑：

```bash
uv run pytest tests/code_change
```

原因：

```text
当前机器缺少 uv。
```

也未跑：

```bash
python3 -m pytest tests/code_change
```

原因：

```text
当前系统 Python 缺少 pytest。
```

下一步安装依赖后应执行：

```bash
cd agent-code-change-platform/backend
uv run pytest tests/code_change
```

## 6. V2 Patch / Test / PR Draft 闭环验证

日期：2026-07-06

命令摘要：

```bash
python3 -m compileall -q backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --help
```

CLI 端到端：

```bash
tmp_repo=$(mktemp -d)
tmp_home=$(mktemp -d)
patch_file="$tmp_home/fix.patch"
printf "def health():\n    return 'bad'\n" > "$tmp_repo/app.py"
cd "$tmp_repo" && git init -q

# fix.patch 将 app.health() 从 bad 改成 ok

PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home/state" \
  project create demo \
  --repo-path "$tmp_repo" \
  --test-command "python3 -c \"import app; assert app.health() == 'ok'; print('tests ok')\""

PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home/state" \
  task run demo "fix health function" --patch-file "$patch_file"
```

结果：

```text
task=<task_id> status=PR_CREATED
test_log=tests ok
```

生成产物：

```text
patch.diff
patch_check.log
patch_apply.log
pr_body.md
task_report.md
test.log
audit.json
timeline.jsonl
```

本轮未跑：

```text
PYTHONPATH=backend/packages/harness python3 -m pytest backend/tests/code_change
```

原因：

```text
当前系统 Python 缺少 pytest。
```

## 7. V3 FastAPI Router 验证

日期：2026-07-06

新增内容：

```text
backend/app/gateway/routers/code_change.py
backend/tests/code_change/test_code_change_router.py
/api/code-change/projects
/api/code-change/projects/{project_id}/tasks
/api/code-change/projects/{project_id}/timeline
/api/code-change/projects/{project_id}/tasks/{task_id}/report
/api/code-change/projects/{project_id}/tasks/{task_id}/pr-body
```

语法验证：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
```

结果：

```text
通过。
```

临时 venv 依赖：

```bash
python3 -m venv /tmp/deerflow-v3-test-venv
/tmp/deerflow-v3-test-venv/bin/pip install -q fastapi pytest httpx2
```

API smoke 结果：

```text
create_status= 200
task_status= 200 PR_CREATED
report_status= 200
pr_status= 200
timeline_events= 2
```

pytest 结果：

```bash
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v3-test-venv/bin/python -m pytest backend/tests/code_change
```

```text
collected 9 items
9 passed in 0.30s
```

V3 当前边界：

```text
API 同步执行 patch/test/report，适合本地演示；生产化需要队列、worker、sandbox 和任务状态轮询。
```

## 8. V4 Queue / Worker 验证

日期：2026-07-06

新增内容：

```text
TaskStatus.QUEUED
backend/packages/harness/deerflow/code_change/worker.py
task_queue.jsonl
CLI: task enqueue
CLI: worker run-once
API: /api/code-change/worker/run-once
```

验证命令：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v3-test-venv/bin/python -m pytest backend/tests/code_change
```

实际结果：

```text
collected 11 items
11 passed in 0.38s
```

CLI queue/worker smoke：

```text
task=<task_id> status=QUEUED
task=<task_id> status=PR_CREATED
queue_exists=True
pr_body_exists=True
test_log=tests ok
```

V4 当前边界：

```text
单机 JSONL 队列，不支持多 worker 分布式抢占；后续需要 Redis/PostgreSQL 队列、租约、重试和 sandbox。
```

## V5 Worker 指标与失败重试

本版新增：

```text
Task.attempt_count / max_attempts / last_error
Task.queued_at / started_at / finished_at
retry_task
CLI: task retry
CLI: worker metrics
API: /api/code-change/metrics
API: /api/code-change/projects/{project_id}/tasks/{task_id}/retry
```

验证命令：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v3-test-venv/bin/python -m pytest backend/tests/code_change
```

实际结果：

```text
compileall：通过。
collected 14 items
14 passed in 0.56s
```

CLI metrics smoke：

```bash
PYTHONPATH=backend/packages/harness /tmp/deerflow-v3-test-venv/bin/python -m deerflow.code_change.cli --home /tmp/deerflow-v5-empty-state worker metrics
```

输出摘要：

```text
total_tasks = 0
queue_depth = 0
failed_count = 0
retryable_failed_count = 0
attempts_total = 0
```

预期测试覆盖：

```text
1. 成功任务 attempt_count = 1，并写 started_at / finished_at。
2. 失败 patch 进入 FAILED，并记录 last_error。
3. retry 后任务重新进入 QUEUED。
4. 第二次失败后 exhausted_failed_count = 1。
5. Router 支持 metrics 和 retry endpoint。
```

当前边界：

```text
V5 只做显式手动 retry 和本地 metrics，不做自动退避、worker lease、DLQ 和 sandbox。
这些能力留到下一版，避免一次性把 MVP 写成不可维护的大改。
```

## V6 隔离 workspace 执行验证

本版新增：

```text
backend/packages/harness/deerflow/code_change/workspace.py
Task.source_repo_path
Task.workspace_path
Task.sandbox_kind
worker 在 workspace 中 apply patch / run tests
task_report.md 输出 sandbox/source/workspace
```

验证命令：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v3-test-venv/bin/python -m pytest backend/tests/code_change
```

实际结果：

```text
compileall：通过。
collected 15 items
15 passed in 0.58s
```

测试覆盖：

```text
1. prepare_workspace 复制 repo，并忽略 .git。
2. patch 应用到 artifacts/workspace，不污染原仓库。
3. test_command 在 workspace 中运行。
4. API 返回 sandbox_kind=local-copy 和 workspace_path。
5. task_report/audit 留存 workspace 证据。
```

当前边界：

```text
local-copy 只能解决“不污染主仓库”，还不能解决 CPU/内存/网络隔离。
下一版应接 Docker 或 DeerFlow sandbox。
```

## V7 Sandbox Policy 与执行边界验证

本版新增：

```text
backend/packages/harness/deerflow/code_change/sandbox_policy.py
sandbox_policy.json
workspace_manifest.json
TestResult.timed_out
TestResult.log_truncated
TestResult.policy_path
test_runner shell=False
```

验证命令：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v7-test-venv/bin/python -m pytest backend/tests/code_change
```

实际结果：

```text
compileall：通过。
collected 17 items
17 passed, 1 warning in 0.53s
```

测试覆盖：

```text
1. shell operator `&&` 被 sandbox policy 阻断。
2. python3 测试命令 shell=False 正常执行。
3. workspace_manifest.json 记录 file_count / ignored_dirs。
4. sandbox_policy.json 随任务产物保存。
5. API 返回 workspace_manifest_path。
```

当前边界：

```text
V7 不是 Docker sandbox；它强化了命令执行边界，但不能限制 CPU/内存/网络。
```

## V8 GitHub Draft PR 交付包验证

本版新增：

```text
backend/packages/harness/deerflow/code_change/pr_handoff.py
Task.pr_handoff_path
Task.pr_create_script_path
pr_handoff.json
create_draft_pr.sh
```

验证命令：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v7-test-venv/bin/python -m pytest backend/tests/code_change
```

实际结果：

```text
collected 18 items
18 passed, 1 warning in 0.51s
```

测试覆盖：

```text
1. patch/test 通过后生成 pr_body.md。
2. 生成 pr_handoff.json。
3. repo_url 存在时生成 gh pr create --draft 命令。
4. API 返回 pr_handoff_path / pr_create_script_path。
```

当前边界：

```text
V8 只生成 PR 交付包，不自动 push，不自动创建真实 GitHub PR。
这是刻意保守的边界：AI 准备材料，人类审核后执行。
```

## V9 最终学习包验证

本版新增：

```text
docs/FINAL_PROJECT_LEARNING_PACKAGE.md
docs/FINAL_RESUME_AND_INTERVIEW_PACK.md
docs/FINAL_DEMO_CASES.md
```

同步更新：

```text
docs/VERSION_TASK_TRACKER.csv
docs/PERFORMANCE_AND_EVOLUTION.md
docs/NEXT_IMPLEMENTATION_PLAN.md
docs/AUTUMN_RECRUIT_STUDY_GUIDE.md
docs/DEERFLOW_CODE_MAP.md
docs/DEERFLOW_INTERVIEW_QA.md
```

验证命令：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v7-test-venv/bin/python -m pytest backend/tests/code_change
git diff --check
```

实际结果：

```text
compileall 通过。
pytest：18 passed, 1 warning in 1.59s。
git diff --check 通过。
```

CLI demo smoke：

```text
Demo A：成功 patch -> worker run-once -> status=PR_CREATED，生成 13 个 task artifact。
Demo B：错误 patch -> worker run-once -> status=FAILED，metrics 显示 failed_count=1、retryable_failed_count=1、attempts_total=1。
```

V9 说明：

```text
V9 不新增核心代码功能，而是把项目二收口成可学习、可演示、可写简历、可面试追问的最终版本。
```
