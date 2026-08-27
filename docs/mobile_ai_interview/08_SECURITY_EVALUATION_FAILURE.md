# 08 安全、评测、故障与演进

## 问题 1：这个 Coding Agent 的威胁模型是什么

### 面试官问

如果输入需求、代码仓库和模型输出都不可信，你做了哪些安全限制？

### 30 秒回答

我按入口、模型能力、文件系统、执行和人工权限分层防护。入口有 owner 隔离、功能开关、专用 Worker Token、允许仓库根目录和服务端 test profile；模型只有 search、read、typed submit 三个 Tool；Patch 拒绝路径穿越和 `.git`；执行使用固定 commit 的 Workspace、`shell=False`、命令白名单、精简环境、超时和进程组清理；测试通过后仍需人工审核。当前没有容器和网络隔离，所以我把它定义为受控本地执行，不说生产沙箱。

### 详细回答

威胁来源不只是一段恶意 Prompt。

用户输入可能要求读取越权仓库、提交超大 Patch 或执行任意命令。代码仓库本身可能在注释中包含 Prompt Injection，诱导模型泄露信息。模型可能幻觉路径、生成危险代码或假称测试完成。测试代码本身也可能是恶意程序。

因此防线不能只写在 system prompt 中。

Gateway 从认证上下文决定 owner，Store 按 owner 分目录；Project 路径必须位于允许根目录。Code Change 功能默认关闭，Worker endpoint 需要专用 Token。测试命令来自服务端 profile。

Patch Agent 没有 shell 和写文件权限，读文件必须是索引内相对路径。提交 Patch 时检查次数、大小和路径。

Worker 在副本中应用 Patch，测试命令不用 shell 解释，环境变量经过筛选，超时杀整个进程组。最终还有人工审核。

这些措施是纵深防御。每层都假设上一层可能失效。

### 结合当前 CodeRepair 源码

- 入口：`routers/code_change.py`、`code_change_worker_auth.py`。
- owner：`store.py::owner_dir` 和 `_ensure_owner`。
- 仓库根：`models.py::ensure_repo_path`。
- Agent Tool：`agent_patch.py::build_code_change_tools`。
- Patch 路径：`patcher.py::validate_patch_paths`。
- 命令策略：`sandbox_policy.py`。
- 超时与环境：`test_runner.py`。
- 人工审核：`review.py`。

### 技术选型与替代

生产版本应把 Workspace 和测试放进短生命周期容器，使用非 root 用户、只读基础镜像、临时卷、seccomp、网络默认拒绝、资源 quota 和执行超时。Secret 只按任务需要注入，日志要脱敏。

Agent 还可以增加 Prompt Injection 检测和 Tool 参数策略，但它们不能替代真正权限隔离。

### 边界与追问

当前 `SandboxPolicy.network_disabled` 默认是 false，也没有网络隔离执行器。local-copy 只保护源仓库不被直接修改，不能限制测试进程访问宿主机其他资源。

## 问题 2：固定 20 case 到底测了什么

### 面试官问

你说有 20 个评测用例，能证明 Agent 修复成功率吗？

### 30 秒回答

不能。这 20 个固定 case 只测 external Patch 的确定性执行链，没有调用在线模型。用例包括 10 个成功 Patch、4 个上下文不匹配、3 个路径穿越和 3 个测试失败，输出 Patch apply rate、test pass rate、task success rate、unsafe block rate 和平均时间。它证明 Worker 门禁对这些固定输入的行为，不证明检索 Recall、模型生成率、Token 成本或人工接受率。

### 详细回答

评测首先为每个 case 创建临时 Git 仓库，提交一个只有 `value()` 的 fixture，再创建 Project。每个 case 提供固定 unified diff 和固定测试命令，调用 `run_task_now` 走 external 模式。

10 个 success case 的 Patch 上下文正确，测试期望值与修改一致，预期到 HANDOFF_READY。

4 个 invalid context 使用不存在的旧值，预期 `git apply --check` 失败。

3 个 unsafe path 试图修改 `../escape-*.py`，预期路径规则阻止。

3 个 test failure 的 Patch 可以应用，但测试故意期望另一个值，预期测试失败。

由于测试集合故意混入失败样本，整体 task success rate 不应该被解释成产品质量。指标只是验证每类 case 是否按设计进入正确状态。

`human_acceptance_rate` 明确写成 `None`，因为没有真实 reviewer 数据。

### 结合当前 CodeRepair 源码

- `code_change/evaluation.py::fixed_cases` 定义精确 case 组成。
- `run_evaluation` 创建临时仓库和本地 Store。
- 每个任务通过 `run_task_now(... patch_text=...)` 执行，因此是 external 模式。
- 输出 `evaluation.json` 和 `evaluation.md`。
- Markdown 末尾明确写着不测 LLM retrieval、Token 或 autonomous generation。

### 技术选型与替代

真正 Agent eval 需要另一套固定任务。每个任务应给出源 commit、自然语言需求、允许修改范围和验收测试，实际调用模型。指标至少包括 retrieval Recall@K、typed submit rate、Patch apply rate、test pass rate、task success、平均 Tool 次数、Token、耗时、越权拦截和人工接受率。还要固定模型版本、Prompt 和运行次数，报告波动范围。

### 边界与追问

简历可以写"建立 20 case 确定性回归套件，覆盖成功、上下文冲突、路径穿越和测试失败"，不能写"Agent 修复率达到某个百分比"。

## 问题 3：有哪些重要故障窗口，系统怎样恢复

### 面试官问

Worker 在不同阶段崩溃会发生什么？

### 30 秒回答

任务领取靠 lease 和 heartbeat，Worker 崩溃后 lease 到期，其他 Worker 可以重新 claim；claim id 作为 fencing token，旧 Worker恢复后不能覆盖新结果。Workspace 用 staging 后再替换，准备失败不会留下半份正式目录。Patch 和报告使用临时文件 replace 减少半写。但文件 Store 没有完整事务，进程在状态迁移和保存之间崩溃仍可能丢失内存进度，重跑也可能覆盖部分 Artifact，所以生产版应把 Task 和 Attempt 放进数据库事务。

### 详细回答

可以按阶段分析。

入队后、领取前崩溃：Task 已经是 QUEUED，之后的 Worker 仍能扫描 JSONL 并领取。

领取后、执行中崩溃：heartbeat 停止，lease 到期后其他 Worker 可以领取。新 Worker会从任务基线重新准备 Workspace并执行。

旧 Worker长暂停后恢复：它保存前校验 claim id。如果任务已被新 Worker领取，抛出 `StaleTaskClaim`，旧结果不会写回 task.json。不过当前 Artifact 没有按 attempt 分目录，旧 Worker 在发现 claim 失效前仍可能写 Patch 或测试日志。这是文件版本尚未解决的窗口。

Workspace复制中崩溃：正式 Workspace 只有在 staging 完成后才替换，随机临时目录可能残留，但不会把半份目录当成成功结果。

Patch 应用后、测试前崩溃：修改只发生在任务 Workspace。重新执行会重新准备固定 commit 的 Workspace，再应用 Patch，不会污染源仓库。

状态已在内存迁移、task.json 未保存时崩溃：文件实现可能仍显示旧状态。这个窗口当前没有 WAL 或数据库事务彻底解决。

### 结合当前 CodeRepair 源码

- claim 恢复：`store.py::_claim_expiry`、`_claim_task_file`。
- fencing：`assert_task_claim`、`save_task(expected_claim_id=...)`。
- heartbeat：`worker.py::_TaskClaimHeartbeat`。
- Workspace staging：`workspace.py::prepare_workspace`。
- JSON 原子替换：`store.py::_write_json`。
- Patch 原子替换：`worker.py::_write_requested_patch`。

### 技术选型与替代

生产设计会把 Task 和 TaskAttempt 分开。Worker 用数据库条件更新领取 attempt，所有状态迁移追加事件。Artifact 先上传对象存储，再在事务里登记 URI。执行阶段要能根据 task id 幂等重建 Workspace。

对于真正外部副作用，例如创建 PR，需要 provider operation id 和幂等查询。超时后不能直接再创建一次，要先查询上次请求是否成功。

### 边界与追问

当前文件 Store 能演示协议，但不能保证网络文件系统上的 `flock` 和 `O_EXCL` 具有与本地文件系统完全相同的语义。多机版本不应直接复用这套实现。

## 问题 4：如果要升级成公司可用版本，优先改什么

### 面试官问

给你两个月把项目升级到团队使用，你的顺序是什么？

### 30 秒回答

我先替换执行安全和状态存储，而不是先加更多模型功能。第一阶段用 PostgreSQL 保存 Project、Task、Attempt、Transition 和 Claim，接可靠任务队列；第二阶段把 Workspace 和测试迁到短生命周期容器，补网络、资源和 Secret 策略；第三阶段接 GitHub App，实现幂等 Draft PR；最后建立真实 Agent eval 和可观测性，包括 Tool trace、Token、耗时、错误分类和人工接受率。

### 详细回答

第一优先级是数据一致性。文件 Store 无法支撑多机 Worker。数据库需要 owner 维度索引、状态版本、claim lease、attempt 记录和事务迁移。队列至少提供确认、重投和死信能力，业务仍按 task id 幂等。

第二优先级是执行隔离。每次任务创建临时容器或 Pod，checkout 固定 commit。源代码和输出目录分开挂载，使用非 root、只读 rootfs、无默认网络、CPU/内存/磁盘配额和总超时。测试所需依赖通过固定镜像或受控缓存提供。

第三优先级是外部协作。用 GitHub App 的安装 Token 创建分支和 Draft PR，记录 repo id、commit、PR number、URL 和 provider request id。操作前要求 APPROVED，创建后才能迁 PR_CREATED。

第四优先级是评测和观测。每个 Run 关联 task id、model、prompt version、tool calls、Token、延迟和错误。建立固定在线 Agent 数据集并多次运行，区分系统失败、检索失败、生成失败、Patch 失败和测试失败。

### 结合当前 CodeRepair 源码

当前已经存在可替换边界：

- `CodeChangeStore` 可以抽象为数据库 Repository。
- `run_next_task` 可以替换队列领取实现。
- `prepare_workspace` 可以替换为 SandboxProvider。
- `run_tests` 可以替换为远程执行器。
- `write_pr_handoff` 可以升级为 GitHub Provider。
- `evaluation.py` 可以保留确定性套件，再新增 Agent eval。

### 技术选型与替代

队列可选 Redis Streams、Kafka、RabbitMQ 或云任务服务。Code Change Task 更像有状态作业，不追求极高吞吐，PostgreSQL 队列加 `SKIP LOCKED` 也可能够用。选型要看任务量、运维能力和投递语义，不应因为简历想写 Kafka 就强行加入。

### 边界与追问

这些是演进设计，不是当前已实现能力。面试时先说当前事实，再说如果进入公司场景会怎样替换，避免把架构图当成运行证据。
