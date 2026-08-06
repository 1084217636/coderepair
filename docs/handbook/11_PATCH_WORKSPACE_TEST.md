# 11 unified diff、Workspace 与测试

## unified diff 是什么

Git 常见 Patch 格式会描述旧文件、新文件和变更行：

```diff
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def answer():
-    return 1
+    return 2
```

它比“请把第 2 行换掉”更稳定，因为包含文件路径和上下文，也能由 `git apply` 检查。

## Patch 校验分几层

### 1. 格式与大小

候选必须非空且不超过限制，必须能提取 changed files。

### 2. 路径

拒绝绝对路径、`..` 和 `.git` 元数据。路径校验必须在写文件前完成。

### 3. git apply --check

它只检查 Patch 是否能应用到当前 Workspace，不真正改文件。失败通常说明源码版本不对、上下文不匹配或 diff 损坏。

### 4. git apply

检查通过后才实际应用。返回码和输出分别写入 log。

### 5. 测试

Patch 能应用不代表代码正确。测试模板在变更后的 Workspace 中执行，退出码为 0 才算通过。

## 为什么需要独立 Workspace

若直接在注册仓库上 `git apply`：

- 失败 Patch 可能留下半成品。
- 两个 Task 会互相污染。
- 测试生成的文件会改脏真实仓库。
- 回滚和保留证据都困难。

`create_task` 先记录 Git commit。`prepare_workspace` 在有 `source_commit` 时使用 `git archive` 导出该提交到 staging，再原子替换 Task 的 Workspace；没有 commit 参数时才回退到过滤目录后的复制。这样未提交的工作区改动不会混入固定基线。

每个 Task 有独立目录，所以不同 Task 不会互相污染，真实仓库也保持不变。当前同一 Task 的重试会复用 Workspace 与 artifact 文件名，因此还不是完整的 attempt 级证据保留。

## 为什么固定 source commit

创建或执行任务时记录 `git rev-parse HEAD`。报告、Patch 和 handoff 都关联这个 SHA。

若不固定：上午基于 A commit 测试成功，下午脚本先 `git pull` 到 B，再把同一 Patch 应用并推送。测试证据已经不能证明最终变更。更严格的方案直接 checkout 记录的 SHA，再创建任务分支。

## 测试模板怎样防命令注入

安全 API 只接收 profile：

```text
python-pytest  → ["python3", "-m", "pytest", "-q"]
go-test        → ["go", "test", "./..."]
frontend-check → ["pnpm", "check"]
```

服务端保存 argv 数组，不经过 shell。还要移除 `python -c`、任意参数拼接等逃逸入口。

需要自定义项目命令怎么办？由管理员在服务端配置新的受审模板，而不是让普通 API 用户传字符串。模板还应限制工作目录、超时、日志大小、CPU/内存与网络。

## 为什么最小化子进程环境变量

默认 `subprocess.run` 会继承 Gateway 的所有环境变量，其中可能有模型 key、数据库密码和内部 token。即使命令模板固定，项目测试代码本身也可能读取环境。

Worker 应构造最小 env，只保留 PATH、HOME、LANG 等执行必需项；更好的容器 Sandbox 使用单独 ServiceAccount 和 Secret 范围。

## 超时和日志截断

测试可能死循环，也可能输出数 GB 日志。策略应有：

- `timeout_seconds`
- `max_log_bytes`
- 超时后终止整个进程组，而不仅是父进程
- 记录 `timed_out` 和 `log_truncated`

当前实现调用 `subprocess.Popen`。在 POSIX 上使用 `start_new_session=True` 创建独立进程组，超时后通过 `killpg` 终止整组，并记录 exit code 124；非 POSIX 环境回退为终止直接进程，孙进程仍是边界。日志超过上限时保留开头并添加 truncated 标记，还没有保留尾部。

## 测试通过还不够

一个模板只能覆盖项目已有测试。还应检查：

- changed files 是否符合需求。
- 是否新增对应测试。
- 是否引入依赖或配置变化。
- 是否有安全与兼容性风险。
- 是否需要人工运行额外 smoke test。

因此成功终点是 `HANDOFF_READY`，不是自动 merge。

## 本章代码阅读任务

阅读顺序：先固定源码，再校验与应用 Patch，最后阅读命令模板和测试进程。

1. 打开 `backend/packages/harness/deerflow/code_change/workspace.py`，按 `resolve_source_commit`、`prepare_workspace`、`_export_commit` 的顺序读。确认 Git 仓库与 40 位 commit 的校验、staging 发布、`git archive` 和 `workspace_manifest.json` 字段。暂不研究 tarfile 库细节。
2. 打开 `backend/packages/harness/deerflow/code_change/patcher.py`，按 `extract_changed_files`、`validate_patch_paths`、`count_changed_lines`、`apply_patch_text`、`run_git_apply` 的顺序读。写出 `git apply --check` 与真正 apply 分别产生哪个日志。
3. 打开 `backend/packages/harness/deerflow/code_change/test_profiles.py` 的 `DEFAULT_TEST_PROFILES` 和 `load_test_profiles`，再读 `sandbox_policy.py` 的 `build_command`。理解 profile 如何变成固定命令，命令怎样经过 `shlex.split` 和可执行文件 allowlist。
4. 打开 `backend/packages/harness/deerflow/code_change/test_runner.py`，依次跟 `run_tests`、`_kill_process_tree`、`build_test_environment`。找到 cwd、`shell=False`、env、timeout、POSIX process group、exit code 和日志上限。明确它仍没有容器隔离。
5. 对照 `backend/tests/code_change/test_workspace.py`、`test_patcher.py`、`test_test_runner.py`，各选一个成功测试和一个失败测试。每个测试写明它验证的产物或拒绝条件。

看到什么程度：拿到一份 diff 时，能按顺序解释固定 SHA、导出 Workspace、路径校验、check、apply、test 和 artifact；还能说出 timeout 与日志截断的当前边界。

暂不要求：不研究 Git diff 算法、tarfile 内部和各操作系统进程管理细节，也不实现容器 Sandbox；先掌握当前确定性执行顺序。

验收动作：在临时 Git 仓库手工执行一次 `git apply --check` 和 `git apply`，再运行一条成功与一条超时测试，对照四类日志字段。

## 本章自测

1. `git apply --check` 与 `git apply` 的区别是什么？
2. 为什么 Workspace 不能直接使用登记仓库？
3. `source_commit` 解决了哪种证据漂移？
4. test profile 为什么比请求中的命令字符串安全？
5. 最小环境变量能防住所有恶意测试吗？
6. 当前超时和日志截断有哪些未完成边界？

## 参考答案

1. `--check` 只验证 diff 能否应用，不改文件；真正 `git apply` 才修改 Workspace。两步各自记录返回码和日志，check 失败就不会继续。
2. 直接修改登记仓库会让失败 Patch、并行任务和测试生成物互相污染，也难以回滚。每个 Task 的 Workspace 把副作用限制在 artifact 目录。
3. 它把 Patch、测试和 handoff 绑定到同一 Git commit，避免测试基于 A 版本、交接时仓库已变成 B 版本。当前 Workspace 用 `git archive` 导出该 commit。
4. 普通用户只能选择服务端定义的名称，不能提交 `python -c` 或任意参数。Router 解析 profile，Worker 执行固定命令，命令还经过 executable allowlist。
5. 不能。最小 env 减少 Gateway Secret 泄露，但项目测试仍在宿主机进程中运行，可能读取其他可访问文件或联网。完整隔离需要容器、资源限制和网络策略。
6. POSIX 上当前会终止整个进程组，非 POSIX 只保证终止直接进程；日志只保留开头加截断标记，不保留尾部。同一 Task 重试也会覆盖同名日志。
