# 05 Workspace、Patch 校验与确定性测试

## 问题 1：为什么要固定 Git commit 并创建独立 Workspace

### 面试官问

为什么不直接在项目仓库里应用 Patch，失败后再 reset？

### 30 秒回答

直接修改登记仓库会把用户未提交改动、并发任务和失败回滚混在一起。CodeRepair 在任务创建时记录 40 位 `source_commit`，执行时用 `git archive` 导出该 commit 到任务独立 Workspace。Patch 和测试只作用于这份副本，所以源仓库不被直接污染，任务输入也能复现。当前 Workspace 是 local-copy，只提供文件级隔离，不是容器安全沙箱。

### 详细回答

固定 commit 解决的是输入漂移。假设任务上午创建，下午 Worker 才执行，而仓库中间又提交了代码。如果 Worker读取最新 HEAD，检索、Patch 上下文和测试结果都不再对应创建时的输入。记录 commit 后，任务有明确基线。

独立 Workspace 解决的是副作用隔离。每个 Task 的 Workspace 位于自己的 Artifact 目录。Agent 读取这里，Patch 应用在这里，测试也在这里运行。即使 Patch 失败或测试生成临时文件，登记仓库保持不变。

创建 Workspace 时先写 staging 目录，成功后再替换正式 workspace。准备失败时删除 staging，并保留旧 Workspace。这比先删旧目录再复制稳妥，因为复制中断不会让任务只剩半份代码。

使用 `git archive` 还有一个含义：只导出 commit 中受 Git 管理的内容，不包含源仓库当前未提交文件和 `.git` 元数据。Workspace 无法在里面直接创建真实分支，这也符合当前只生成候选和报告的边界。

### 结合当前 CodeRepair 源码

- `worker.py::create_task` 调用 `resolve_source_commit`。
- `workspace.py::resolve_source_commit` 执行 `git rev-parse --verify HEAD^{commit}`。
- `prepare_workspace` 使用随机 staging 目录和 tar archive。
- `_export_commit` 执行 `git archive`，再用 tarfile 解包。
- `workspace_manifest.json` 记录 commit、路径、文件数量、总字节数和耗时。
- `Task.sandbox_kind` 当前写入 `local-copy`。

### 技术选型与替代

替代方式包括 `git worktree`、临时 clone、OverlayFS 和短生命周期容器。`git worktree` 更节省空间，但会共享 `.git` 管理状态；容器可以加进程、网络和资源隔离，但部署复杂度更高。

当前本地项目用 `git archive + copy`，优点是输入干净、实现直接、容易测试。公司版本更适合把 commit checkout 到临时容器卷中，再设置只读源挂载和可写工作层。

### 边界与追问

local-copy 不能阻止恶意测试访问宿主机可见的文件或网络，也没有 CPU、内存和磁盘配额。简历只能写独立 Workspace，不能写生产级容器 Sandbox。

## 问题 2：一个 unified diff 怎样被校验和应用

### 面试官问

模型提交一段 diff 后，你怎样防止路径穿越，并判断它能否应用？

### 30 秒回答

系统先从 `diff --git`、`---` 和 `+++` 行提取变更路径，拒绝空路径、绝对路径、包含 `..`、反斜杠转义和 `.git` 元数据的 Patch。然后把候选写入 Artifact，先运行 `git apply --check` 验证上下文，检查通过才运行 `git apply`。检查和应用日志分别保存，任何一步失败都不会进入测试状态。

### 详细回答

Patch 处理分三层。

第一层是文本大小和非空检查。Agent 提交上限是 256 KB；外部任务请求的上限是 2 MB。两个入口上限不同，因为 Agent 输出需要更严的成本和滥用控制。

第二层是路径检查。系统不应把 Patch 中的路径直接拼到 Workspace。`extract_changed_files` 从标准 diff 头提取路径，去掉 `a/`、`b/` 和时间戳部分。`validate_patch_paths` 要求至少有一个路径，并拒绝绝对路径、父目录跳转、`.git` 和不支持的转义形式。

第三层是 Git 语义检查。`git apply --check` 会验证 hunk 上下文、文件存在性和 Patch 格式。只有返回码为 0 才真正执行 `git apply`。

系统还统计增删行数，但它只用于报告，不用于证明质量。`git apply` 成功也只说明文本变更能应用，不说明代码能编译或行为正确。

### 结合当前 CodeRepair 源码

- `patcher.py::extract_changed_files` 解析 diff 路径。
- `validate_patch_paths` 抛出 `PatchRejected`。
- `count_changed_lines` 统计普通 `+` 和 `-` 行，跳过文件头。
- `run_git_apply` 使用参数数组调用 subprocess，没有 `shell=True`。
- `apply_patch_text` 写 `patch.diff`、`patch_check.log` 和 `patch_apply.log`。
- Worker 检查 `PatchResult.applied`，失败时记录 `PATCH_APPLY_FAILED`。

### 技术选型与替代

为什么用 Git diff，而不是让模型返回修改后的完整文件？diff 更容易人工审核，也能精确显示变更范围，Git 还能检查上下文。但 diff 对模型格式要求较高，行号和上下文容易错。

可以改用结构化 edit，例如 path、old text、new text，或使用 AST 变换。结构化 edit 对局部替换更稳定，AST 对单语言重构更安全，但跨语言通用性不如 unified diff。

### 边界与追问

路径检查不等于内容安全。Patch 仍可能加入后门、泄露日志或削弱鉴权，所以还要测试、人工 review 和后续安全扫描。

## 问题 3：测试命令为什么不能由用户随便填写

### 面试官问

测试不就是执行一条命令吗，为什么还要 test profile 和 SandboxPolicy？

### 30 秒回答

测试命令本质上是代码执行权限。CodeRepair 创建 Project 时只接受服务端登记的 test profile，再由服务端映射成命令。运行时用 `shlex.split` 解析参数，拒绝 `&&`、管道、重定向和命令替换，只允许白名单可执行文件；subprocess 使用 `shell=False`、清理环境、限制时间和日志大小，超时时杀整个进程组。这样比直接执行客户端字符串更可控。

### 详细回答

如果 API 接受任意 `test_command`，攻击者可以把它变成删除文件、读取 Secret 或下载程序的命令。即使前端只提供下拉框，也不能相信客户端，服务端必须自己选择命令。

当前 test profile 默认面向 Python、Go 和前端，例如 `python-pytest`、`go-test`、`frontend-check`。Project 保存最终解析后的命令和 profile 名称。

执行时，`build_command` 使用 `shlex.split` 得到参数数组，检查显式 shell 操作符，并对首个 executable 做白名单匹配。像 `python3.12` 可以规范为允许的 `python3` major，但不会接受任意 `python3evil` 前缀。

测试环境只继承 PATH、语言、虚拟环境和 Go 缓存等少量变量。HOME、缓存和临时目录指向任务 Artifact，减少读取用户真实 Home 的机会。POSIX 下启动新 session，超时时用 `killpg` 杀死整个进程组，避免父进程退出但子进程继续占用资源。

### 结合当前 CodeRepair 源码

- `code_change.py::get_code_change_test_profiles` 加载服务端配置。
- `store.create_project` 保存服务端解析后的 test command。
- `sandbox_policy.py::build_command` 拒绝 shell operator 并检查 executable。
- `test_runner.py::build_test_environment` 构造精简环境。
- `run_tests` 使用 `Popen(... shell=False, start_new_session=True)`。
- `_kill_process_tree` 在 POSIX 上调用 `os.killpg`。
- Policy 默认 timeout 为 120 秒，日志上限 64 KB。

### 技术选型与替代

参数白名单只能限制入口命令。例如允许 `python` 后，测试代码本身仍然可以访问网络和文件。更强方案是容器运行时、seccomp、只读 rootfs、无权限用户、网络策略、CPU 和内存 limit。

当前 `SandboxPolicy.network_disabled=False`，字段只是记录意图，没有实现网络隔离。因此不能说测试已经断网。

### 边界与追问

`shell=False` 能避免常见 shell 注入，但不能把不可信程序变安全。测试仓库本身就是代码，执行它需要 OS 级隔离。当前版本只做到命令和进程管理的第一层防线。

## 问题 4：为什么说后半段是确定性 Workflow

### 面试官问

既然前面用了模型，为什么你还强调确定性验证？

### 30 秒回答

确定性不是说所有测试结果永远一样，而是同样的输入会走明确的程序规则，状态和证据可以检查。固定 commit、同一 Patch、同一 test profile 下，路径校验、`git apply --check`、退出码判断和状态迁移都由普通代码决定，不靠模型自然语言判断。模型只产出候选，系统用可复现的程序规则决定是否进入 HANDOFF_READY。

### 详细回答

模型可能对同一需求生成不同 Patch，所以生成阶段是概率性的。后续程序不会再问模型"这个 Patch 是否安全"或"测试是否通过"，而是执行固定逻辑。

Workspace 是否成功，看 Git commit 能否导出。Patch 是否可应用，看路径规则和 `git apply` 返回码。测试是否通过，看命令退出码是否为 0。状态是否能迁移，看 `ALLOWED_TRANSITIONS`。人工是否批准，看保存的 review decision。

这种设计带来两个好处。

一是故障归因更清楚。生成失败、Patch 格式错误、测试失败和审核拒绝对应不同阶段，不会都归结为一句"Agent 失败"。

二是评测可以分层。确定性套件先验证执行面；模型评测再单独测检索、生成、Token 和接受率。两层数据不能混报。

### 结合当前 CodeRepair 源码

- 输入基线：`Task.source_commit` 和 `workspace_manifest.json`。
- Patch 事实：`PatchResult`、check/apply log。
- 测试事实：`TestResult.exit_code`、duration、timed_out 和 test log。
- 状态事实：`state_machine.py::ALLOWED_TRANSITIONS`。
- 人工事实：`human_review.json`。

### 技术选型与替代

还可以在确定性门禁后加入模型 Review，帮助发现测试没覆盖的问题。但模型 Review 只能作为附加信号，不能替代编译、测试和人工权限决策。

### 边界与追问

测试也可能 flaky，依赖网络或时间。真正的公司系统还要记录依赖版本、容器镜像 digest、重试规则和 flaky test 标签，才能提高复现程度。当前项目固定了源码 commit，但没有做到完整构建环境可复现。
