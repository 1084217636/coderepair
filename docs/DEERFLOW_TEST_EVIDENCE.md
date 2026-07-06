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
