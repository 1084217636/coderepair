# 03 FastAPI 控制面与任务入口

## 问题 1：一个代码变更任务怎样进入系统

### 面试官问

从用户提交需求开始，把完整 HTTP 调用链讲一遍。

### 30 秒回答

用户在 `/workspace/code-change` 控制台创建 Project，登记仓库路径和测试 profile，再通过 `POST /api/code-change/projects/{project_id}/tasks` 提交 requirement、patch mode 和可选 Patch。FastAPI 用 Pydantic 校验请求，通过依赖获取当前用户隔离的 Store，`create_task` 记录源 Git commit、任务目录和 Agent 关联 ID，然后把状态从 CREATED 迁到 QUEUED，并写入 JSONL 队列。Worker 使用专用 Token 调用 run-once，从队列原子领取一个任务，再执行 Workspace、检索、Patch、测试和报告流程。

### 详细回答

Project 和 Task 分两步创建。Project 是长期配置，包含代码仓库、默认分支、测试 profile 和 owner。Task 是一次具体变更，包含自然语言需求、Patch 模式、固定源 commit、执行次数和状态。

创建 Task 时，`create_task` 会先检查模式：Agent 模式不能同时携带外部 Patch，external 模式不能填写 Agent model name。如果有外部 Patch，会检查非空和最大字节数，然后把它原子写入任务目录。接着用 `git rev-parse HEAD^{commit}` 记录当前 commit。这样 Worker 晚一点执行时，不会因为登记仓库又有新提交而改变任务输入。

任务选择 enqueue 后，状态变为 QUEUED，Store 写 `task.json` 和一条 JSONL 队列记录。HTTP 请求到这里就可以结束。执行任务的入口是 `/worker/run-once`，它比普通业务接口多一个专用 `X-Code-Change-Worker-Token` 校验。Worker 领取不到任务时返回 `NOOP`。

这条链把提交和执行分开。用户重试 HTTP 创建请求仍然需要上层幂等策略，当前没有提供客户端 request id；任务一旦创建，内部状态和每次 attempt 都会被记录。

### 结合当前 CodeRepair 源码

- `frontend/src/app/workspace/code-change/code-change-console.tsx` 管理 Project、Task、轮询、报告和审核界面状态。
- `frontend/src/core/code-change/api.ts` 把页面操作映射为 REST 请求。
- `app/gateway/routers/code_change.py` 定义 `ProjectCreateRequest`、`TaskRunRequest` 和对应 Endpoint。
- `code_change/worker.py::create_task` 校验 PatchMode、固定 `source_commit`、创建 Task 和入队。
- `code_change/store.py::new_task_dir` 生成 `task_时间_uuid` 目录。
- `CodeChangeStore.enqueue_task` 追加 `task_queue.jsonl`。
- `run_worker_once` 调用 `run_next_task`，但要先通过 `require_internal_worker`。
- `code_change_worker_auth.py` 只为这个 Worker 路径检查专用 Token。

### 技术选型与替代

为什么不在创建 Task 的 Handler 中直接执行？模型和测试耗时不稳定，HTTP 连接断开不应该取消或丢失任务事实。异步任务还能统一做领取、超时、重试和指标。

公司版本可以让 API 写数据库并投递消息队列，Worker 常驻消费。当前 run-once 和 JSONL 适合本机演示和测试，但没有消息队列的确认、消费组和跨机容错。

### 边界与追问

当前创建 Task 没有 `client_request_id`，所以不能声称 HTTP 层已经实现防重复提交。Task 内部有唯一 task id，但那是在服务端创建后生成的。

## 问题 2：Project、Task 和 Artifact 为什么要分开

### 面试官问

为什么不只建一个 Task 表，把仓库和结果都放进去？

### 30 秒回答

Project 表示可重复使用的受控执行配置，Task 表示一次变更实例，Artifact 表示这次执行留下的文件证据。分开后，一个 Project 可以运行多次 Task；每个 Task 固定自己的 commit、状态、Patch、测试和审核记录。这样既减少重复配置，也能保证一次任务的输入和产物可追溯。

### 详细回答

Project 保存相对稳定的数据：仓库路径、仓库 URL、默认分支、测试命令、测试 profile 和 owner。Task 保存会变化的数据：requirement、状态、attempt、claim、PatchResult、TestResult、Workspace 和错误码。

Artifact 不应该全部塞进 Task JSON。Patch、测试日志和报告可能较大，而且人需要直接查看。当前任务目录保存：

```text
task.json
requested_patch.diff
patch.diff
patch_check.log
patch_apply.log
test.log
workspace_manifest.json
task_report.md
audit.json
pr_body.md
pr_handoff.json
create_draft_pr.sh
human_review.json
sandbox_policy.json
```

Task 中只保存这些产物的路径和摘要结果。这个设计类似 Go 服务把数据库中的业务状态与对象存储中的大文件分开。

固定 `source_commit` 很重要。Project 的 `repo_path` 会变化，但 Task 需要可复现。任务创建时记录 commit，Worker 用 `git archive` 导出该 commit，不读取后来未提交的工作区变化。

### 结合当前 CodeRepair 源码

- `models.py::Project` 和 `models.py::Task` 是两个 dataclass。
- `Task` 中的 `artifact_dir`、`workspace_path`、`patch_result`、`test_result` 指向本次执行事实。
- `store.py` 按 `projects/{project_id}/tasks/{task_id}` 管理目录。
- `report_writer.py` 写任务报告，`pr_handoff.py` 写交接材料，`review.py` 写人工审核 JSON。

### 技术选型与替代

生产系统更适合用关系数据库保存 Project、Task、Transition 和 Claim，用对象存储保存 Patch、日志和报告。关系数据库可以加唯一约束、事务和条件更新，对多 Worker 更可靠。

当前文件模型的好处是没有外部依赖，演示时能直接打开每个证据文件。缺点是查询、并发和跨机共享能力弱。

### 边界与追问

当前 Artifact 目录在本机文件系统，不是 S3 或共享存储。部署多个 Worker 到不同机器时，需要先改存储层，否则另一个 Worker 看不到 Workspace 和日志。

## 问题 3：用户隔离和接口权限怎样实现

### 面试官问

用户 A 能不能通过修改 project id 读取用户 B 的任务？

### 30 秒回答

控制面不会使用客户端提交的 owner。Gateway 从服务端认证上下文获取 effective user id，按 owner 构造 `CodeChangeStore`。非 default 用户的数据位于 `code-change/users/{owner}` 下，列表只扫描当前 owner 目录；单对象读取和保存还会检查对象的 owner。系统不会转到其他 owner 目录查找同名资源。Worker 接口另有专用 Token，普通登录用户不能触发执行。

### 详细回答

用户隔离要从入口决定命名空间，不能先读取全局对象再靠前端隐藏。

`get_code_change_store(request)` 优先读取可信内部 owner，否则读取当前认证用户。它创建一个绑定 owner 的 Store。Store 的 `owner_dir` 决定 Projects 索引、任务队列和任务目录从哪里读取。用户输入中的 project id 只在这个 owner 目录内解析。

读取单个 Project、Task 或保存 Task 时，`_ensure_owner` 还会比较对象里的 owner id 与 Store owner。这是第二层防线。列表接口主要依赖 owner 目录和 owner 专属索引隔离，不应把它说成数据库行级权限。

仓库路径也有限制。Project 创建时 `ensure_repo_path` 会把路径 resolve，再检查它是否位于 `CODE_CHANGE_ALLOWED_REPO_ROOTS` 下。这样用户不能让 Worker 对宿主机任意目录执行扫描和测试。

Worker run-once 是更高权限的内部操作。即使用户能创建 Task，也不能靠普通认证令牌触发 Worker；它需要专用 Header Token，并且这个 Token 只应作用于该路径。

### 结合当前 CodeRepair 源码

- `code_change.py::get_code_change_store` 决定 owner。
- `store.py::__init__` 为 owner 计算 `owner_dir`。
- `store.py::_ensure_owner` 在读取和保存对象时再次检查。
- `models.py::ensure_repo_path` 检查允许的仓库根目录。
- `code_change.py::require_internal_worker` 保护 `/worker/run-once`。

### 技术选型与替代

文件目录隔离适合本机版本。数据库版本应给 Project、Task、Artifact 都增加 `owner_id`，所有查询条件都带 owner，并在关键唯一索引中包含 owner。权限要求更高时可以使用 PostgreSQL Row Level Security。

内部 Worker 可以使用 mTLS、服务身份或短期签名 Token。当前专用静态 Token 简单可测，但需要 Secret 管理和轮换。

### 边界与追问

owner 隔离不是 Linux 容器隔离。当前多个用户的 Worker 仍运行在同一个宿主机进程权限下，所以生产环境还要用容器、Kubernetes ServiceAccount、网络策略和资源限额缩小影响范围。
