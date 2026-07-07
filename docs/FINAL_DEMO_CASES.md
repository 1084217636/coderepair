# 项目二最终 Demo 用例

本文档用于你学习和面试演示。目标不是展示“模型多聪明”，而是展示平台如何把一次代码变更做成可验证闭环。

## 1. 环境验证

在仓库根目录执行：

```bash
python3 -m compileall -q backend/app/gateway/routers backend/app/gateway/app.py backend/packages/harness/deerflow/code_change backend/tests/code_change
PYTHONPATH=backend:backend/packages/harness /tmp/deerflow-v7-test-venv/bin/python -m pytest backend/tests/code_change
```

预期：

```text
compileall 通过。
pytest 通过，当前为 18 passed。
```

如果 `/tmp/deerflow-v7-test-venv` 不存在，先创建：

```bash
python3 -m venv /tmp/deerflow-v7-test-venv
/tmp/deerflow-v7-test-venv/bin/pip install -q fastapi pytest httpx
```

## 2. Demo A：成功修复并生成 PR handoff

创建临时仓库：

```bash
tmp_repo=$(mktemp -d)
tmp_home=$(mktemp -d)
printf "def health():\n    return 'bad'\n" > "$tmp_repo/app.py"
cd "$tmp_repo" && git init -q
```

准备 patch：

```bash
cat > "$tmp_home/fix.patch" <<'PATCH'
diff --git a/app.py b/app.py
index 42b057a..85a7b89 100644
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
PATCH
```

创建项目：

```bash
cd /home/xiaobin/myproject/agent-code-change-platform
PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home/state" \
  project create demo \
  --repo-path "$tmp_repo" \
  --repo-url "git@github.com:example/demo.git" \
  --test-command "python3 -c \"import app; assert app.health() == 'ok'; print('tests ok')\""
```

入队任务：

```bash
PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home/state" \
  task enqueue demo "fix health function" --patch-file "$tmp_home/fix.patch"
```

Worker 执行：

```bash
PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$tmp_home/state" \
  worker run-once
```

预期输出：

```text
task=<task_id> status=PR_CREATED artifacts=<artifact_dir>
```

重点检查产物：

```bash
find "$tmp_home/state/projects/demo/tasks" -maxdepth 2 -type f | sort
```

你应该看到：

```text
requested_patch.diff
patch.diff
patch_check.log
patch_apply.log
test.log
task_report.md
audit.json
task.json
workspace_manifest.json
sandbox_policy.json
pr_body.md
pr_handoff.json
create_draft_pr.sh
```

面试讲法：

```text
这个 demo 展示的是需求进入平台后，不直接污染主仓库，而是在任务 workspace 中应用 patch、执行测试、记录审计，最后生成 PR handoff。
```

## 3. Demo B：失败任务和 retry

准备一个会失败的 patch：

```bash
bad_home=$(mktemp -d)
bad_repo=$(mktemp -d)
printf "def health():\n    return 'bad'\n" > "$bad_repo/app.py"
cd "$bad_repo" && git init -q

cat > "$bad_home/bad.patch" <<'PATCH'
diff --git a/app.py b/app.py
index 42b057a..85a7b89 100644
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'missing'
+    return 'ok'
PATCH
```

创建项目并执行：

```bash
cd /home/xiaobin/myproject/agent-code-change-platform
PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$bad_home/state" \
  project create demo \
  --repo-path "$bad_repo" \
  --test-command "python3 -c \"import app; assert app.health() == 'ok'\""

PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$bad_home/state" \
  task enqueue demo "try bad patch" --patch-file "$bad_home/bad.patch"

PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$bad_home/state" \
  worker run-once
```

预期：

```text
status=FAILED
```

查看 metrics：

```bash
PYTHONPATH=backend/packages/harness python3 -m deerflow.code_change.cli --home "$bad_home/state" \
  worker metrics --project demo
```

你应该重点看：

```text
failed_count
retryable_failed_count
attempts_total
status_counts
```

面试讲法：

```text
我没有假设 AI 一次就能改对。失败任务会保留 last_error、test.log、patch_apply.log 和 audit.json，并可以在未超过 max_attempts 时 retry。
```

## 4. Demo C：API 视角

API 入口在：

```text
backend/app/gateway/routers/code_change.py
```

核心接口：

```text
POST /api/code-change/projects
GET  /api/code-change/projects
POST /api/code-change/projects/{project_id}/tasks
POST /api/code-change/worker/run-once
GET  /api/code-change/projects/{project_id}/tasks/{task_id}
GET  /api/code-change/projects/{project_id}/tasks/{task_id}/report
GET  /api/code-change/projects/{project_id}/tasks/{task_id}/pr-body
GET  /api/code-change/metrics
POST /api/code-change/projects/{project_id}/tasks/{task_id}/retry
```

面试讲法：

```text
CLI 是本地学习和演示入口，FastAPI router 则把能力包装成内部研发效能平台 API。V4 后默认任务入队，Worker 执行长耗时逻辑，API 用来创建任务和查询状态。
```

## 5. 演示时重点展示哪些文件

优先展示：

```text
task.json               当前任务状态、attempt、workspace、PR handoff 路径
task_report.md          面向人的任务报告
audit.json              面向审计和复盘的结构化记录
test.log                测试证据
patch_check.log         git apply --check 证据
workspace_manifest.json workspace 文件统计和复制证据
sandbox_policy.json     执行命令边界
pr_body.md              PR 描述
pr_handoff.json         创建 PR 需要的结构化信息
create_draft_pr.sh      人工审核后执行的 draft PR 脚本
```

不要只展示终端一行 `PR_CREATED`，要展示这些 artifact。它们才是项目不像玩具的关键。
