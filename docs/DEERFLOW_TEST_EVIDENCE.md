# DeerFlow 二开测试证据

## 1. 当前基线

日期：2026-07-04

说明：

```text
当前环境没有 uv，也没有系统 pytest。
因此本轮使用 compileall + CLI 闭环验证。
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
