# 01 Go 后端开发者怎样理解 AI 平台

## 问题 1：这个项目从系统架构上是什么

### 面试官问

你先不要讲模型，能不能从后端系统架构介绍一下 CodeRepair？

### 30 秒回答

CodeRepair 是基于 DeerFlow 二次开发的 Client-Server Coding Agent 平台。浏览器是客户端，Nginx 是统一入口，FastAPI Gateway 是控制面，负责项目、任务、身份和运行状态；Worker 是执行面，负责准备固定 Git commit 的独立 Workspace、获取上下文、生成或接收候选 Patch、校验、应用和运行测试。模型只负责提出候选修改，普通程序负责验证，最后还要人工审核。我把它理解为一个带 AI 决策环节的后端任务系统，而不是一个聊天页面。

### 详细回答

我会先把系统拆成控制面和执行面。

控制面解决"谁发起了什么任务、任务处于什么状态、可以执行什么操作"。当前 Gateway 使用 FastAPI 提供 Project、Task、Worker、Review 和 Report 接口。Project 登记代码仓库和服务端批准的测试配置，Task 保存需求、源 commit、Patch 模式、状态、产物路径和领取信息。

执行面解决"如何安全地处理候选修改"。Worker 不直接修改登记仓库，而是根据任务创建时记录的 `source_commit` 导出一个 Workspace。外部 Patch 模式直接接收 unified diff；Agent 模式让受限 Agent 搜索和读取 Workspace，并通过类型化 Tool 提交候选 diff。两条路径随后汇合：检查路径、执行 `git apply --check`、应用 Patch、运行固定测试命令、写报告，等待人工审批。

这套拆分和普通 Go 后端服务很像。HTTP Handler 对应 FastAPI Router，Service 层对应 Worker 和 Store，领域对象对应 Project、Task、PatchResult、TestResult。区别在于系统中多了一个不确定的模型调用，所以不能把模型输出当成业务事实，必须在后面接确定性校验。

### 结合当前 CodeRepair 源码

- `backend/app/gateway/app.py` 创建 FastAPI 应用并注册 `code_change` 和 `anchored_branch` Router。
- `backend/app/gateway/routers/code_change.py` 是 Code Change 控制面入口。
- `backend/packages/harness/deerflow/code_change/models.py` 定义 Project、Task 和结果对象。
- `backend/packages/harness/deerflow/code_change/worker.py` 的 `execute_task` 编排执行链。
- `backend/packages/harness/deerflow/code_change/workspace.py` 创建固定 commit 的 Workspace。
- `backend/packages/harness/deerflow/code_change/agent_patch.py` 负责受限 Agent 生成候选 Patch。

可以用这条链概括：

```text
Browser
→ Nginx
→ FastAPI Gateway
→ Project / Task Store
→ Worker claim
→ pinned-commit Workspace
→ external Patch 或 restricted Patch Agent
→ validate / apply / test
→ report
→ human review
```

### 技术选型与替代

我选择控制面和执行面分离，是因为 HTTP 请求生命周期不适合承载几十秒甚至几分钟的模型调用和测试进程。同步执行虽然实现简单，但请求断开、超时和重试会把任务状态弄乱。任务化后，客户端只需要轮询状态或获取流式事件。

当前实现为了个人项目可运行，Store 使用文件，队列使用 JSONL。公司场景会换成 PostgreSQL 保存状态，用 Redis Streams、Kafka 或专门任务队列分发任务，Worker 可以水平扩展。设计边界不变，只替换基础设施。

### 边界与追问

上游 DeerFlow 的 Nginx、Gateway、Thread/Run、通用 Agent 和前端不是我从零实现的。我的二次开发是 Code Change 工作流和 Anchored Branch。

如果面试官问"是不是微服务"，我会说当前开发形态是一个包含 Gateway 和 Worker 职责的全栈仓库，具有控制面与执行面边界，但文件 Store 版本不具备生产级多机调度能力，不能为了术语好听就写成成熟微服务平台。

## 问题 2：Python async 和 Go goroutine 有什么区别

### 面试官问

你基本盘是 Go，为什么 AI 项目用了 Python？`async def` 和 goroutine 怎么理解？

### 30 秒回答

Python 是主流模型 SDK、LangChain 和 LangGraph 的直接生态，所以二次开发 DeerFlow 继续使用 Python更合适。`asyncio` 主要靠单线程事件循环在 `await` 处协作切换，适合 HTTP、模型调用和 SSE 这类 I/O 密集任务；goroutine 由 Go runtime 调度，可以在多个线程上运行，阻塞调用通常不会把整个调度器卡死。Python 的同步文件和 subprocess 操作如果直接放在 async 路径中，会阻塞事件循环，所以要用异步库或 `asyncio.to_thread` 隔离。

### 详细回答

`async def` 调用后返回 coroutine。只有被 `await`、创建为 Task 或交给事件循环运行，它才真正推进。执行到一个可等待的 I/O 时，当前 coroutine 主动让出事件循环，事件循环再运行其他就绪任务。这叫协作式调度。

goroutine 的使用感受不同。执行 `go f()` 后，Go runtime 把它交给调度器。runtime 维护 G、M、P，能够把大量 goroutine 映射到有限的系统线程。goroutine 遇到很多网络阻塞时，runtime 能调度其他 goroutine；CPU 工作也可能在多个线程并行执行。

Python async 的风险是"函数写成 async，不代表里面所有操作都异步"。例如在 `async def` 里直接 `Path.read_text()`、`subprocess.run()` 或使用同步 HTTP 客户端，事件循环在这些调用返回前无法服务其他请求。DeerFlow 的 Gateway 有后台 Run、SSE 心跳和多个接口，所以阻塞事件循环会影响所有并发请求。

Code Change Worker 当前有大量同步文件和 Git 操作，但 Worker 本身走同步任务执行链，并不伪装成 async。这个选择比在 async Handler 里直接跑 Git 和测试更清楚。

### 结合当前 CodeRepair 源码

- `backend/app/gateway/routers/anchored_branch.py` 中创建分支、读取 Checkpoint 和启动流式 Run 使用 `async def`，因为这些接口依赖异步 Store、Checkpointer 和 SSE。
- `backend/app/gateway/routers/code_change.py` 的多数接口是普通 `def`，FastAPI 会把同步 Endpoint 放到线程池执行，避免直接占住事件循环。
- `backend/packages/harness/deerflow/code_change/worker.py` 是同步 Worker 编排。
- `backend/packages/harness/deerflow/code_change/test_runner.py` 使用 `subprocess.Popen` 运行测试，位于 Worker 执行面，不在 SSE 事件循环中直接等待。
- `backend/app/gateway/app.py` 的 lifespan 中，对同步预热和文件清理使用了 `asyncio.to_thread`。

### 技术选型与替代

如果从零开发且模型生态允许，控制面也可以用 Go，Python Agent 服务只保留模型和 LangGraph。但这样会增加跨服务协议、部署和调试成本。个人项目复用 DeerFlow 时，继续使用 Python 能减少不必要的语言切分。

CPU 密集任务不能靠 asyncio 加速。可以用进程池、独立 Worker 或把工作下沉到容器。测试进程本来就应该由执行面管理，不应该塞进 Gateway 事件循环。

### 边界与追问

不能说 Python async 比 goroutine 更快。正确说法是它们的调度模型和使用边界不同。

如果追问 GIL，我会回答：CPython 同一进程中通常只有一个线程同时执行 Python 字节码，因此线程对 CPU 密集计算帮助有限，但 I/O 等待时可以释放 GIL。这个项目的并发重点是 HTTP、SSE、模型调用和外部测试进程，不是用 Python 线程做大规模 CPU 计算。

## 问题 3：FastAPI 的依赖注入怎么理解

### 面试官问

FastAPI 的 Router、Pydantic 和 `Depends` 分别做什么？和 Go 项目有什么对应关系？

### 30 秒回答

Router 负责把方法和路径映射到 Handler，Pydantic 模型负责请求反序列化和字段校验，`Depends` 负责在调用 Handler 前解析依赖。它和 Go 的路由注册、请求 DTO 校验、中间件或显式构造 Service 很接近。Code Change Router 用全局依赖检查功能开关，用请求依赖构造 owner 隔离的 Store，并通过服务端测试配置把客户端输入限制为测试 profile，而不是接受任意命令。

### 详细回答

FastAPI 读取函数签名来构建接口行为。`@router.post` 决定 HTTP 方法和路径。参数类型是 Pydantic `BaseModel` 时，框架会解析 JSON，检查长度、枚举和必填字段，失败时返回 422。参数写成 `Depends(get_code_change_store)` 时，FastAPI 会先调用依赖函数，再把返回值注入 Endpoint。

依赖注入在这里不是为了炫技，而是统一处理三个横切问题。

第一，功能开关。整个 Router 配置 `Depends(require_code_change_enabled)`，关闭时统一返回 404，避免每个接口重复判断。

第二，用户隔离。`get_code_change_store(request)` 从服务端认证上下文中取 owner，构造只访问该 owner 目录的 Store。客户端不能靠请求体指定 owner。

第三，配置控制。创建 Project 时，请求只提交 `test_profile`。服务端通过 `load_test_profiles()` 映射为真实测试命令，防止用户把 `rm` 或网络下载命令作为测试命令提交。

对应到 Go，我可能会定义 Handler 结构体，把 Store、Config 和 Auth Service 显式注入；也可能通过中间件把 user ID 放进 `context.Context`。FastAPI 使用函数签名和类型标注完成同样的装配。

### 结合当前 CodeRepair 源码

`backend/app/gateway/routers/code_change.py` 中：

- `router = APIRouter(... dependencies=[Depends(require_code_change_enabled)])` 是 Router 级功能开关。
- `ProjectCreateRequest`、`TaskRunRequest` 和 `TaskReviewRequest` 是请求 DTO。
- `patch_mode: Literal["external", "agent"]` 把模式限制为两个值。
- `patch_text` 有大小上限，`requirement` 有长度上限。
- `get_code_change_store` 根据认证用户创建 `CodeChangeStore(owner_id=owner_id)`。
- `get_code_change_test_profiles` 只返回服务器加载的 profile。
- `/worker/run-once` 还调用 `require_internal_worker` 检查专用 Worker Token。

### 技术选型与替代

FastAPI 的优点是类型声明、OpenAPI 和异步生态结合紧密，适合 AI 控制面。缺点是依赖函数过多时，实际调用链不如显式 Go 构造清楚，所以我会把业务编排放到 Worker 和 Store，不把所有逻辑都堆在 Endpoint。

替代方案包括 Flask、Django REST Framework 或 Go Gin。选型应看已有生态、团队语言和运行模型，不应只比较简单请求的基准吞吐量。

### 边界与追问

Pydantic 校验只能证明 JSON 形状正确，不能替代权限和业务状态校验。例如 `decision` 的字符串合法，不代表当前 Task 一定处于 `HANDOFF_READY`。后者仍由 `review_task` 检查。

## 问题 4：为什么 AI 系统仍然要以传统后端能力为基本盘

### 面试官问

这个项目最能体现你的 AI 能力，还是后端工程能力？

### 30 秒回答

我把它定位成 AI 应用基础设施项目，后端工程是基本盘。模型输出天然有不确定性，真正让功能可用的是状态机、身份隔离、任务领取、Workspace、路径校验、超时、测试和人工审批。AI 部分负责理解需求、检索和提出 Patch，后端部分决定这个候选能不能进入下一阶段。我的重点不是训练模型，而是把模型能力放进可审计、可失败、可恢复的系统边界。

### 详细回答

普通 CRUD 的输入通常是确定数据，校验通过后可以直接写数据库。LLM 的输出不是这样。它可能格式错误、引用不存在文件、越权修改路径、漏掉测试，也可能用自然语言声称"已完成"，实际上没有执行任何操作。

因此 Agent 平台至少需要三层边界。

第一层是能力边界。模型只能调用显式 Tool。CodeRepair 的 Patch Agent 没有 shell 和写文件 Tool，只有 search、read 和 typed submit。

第二层是执行边界。候选 Patch 在固定 commit 的 Workspace 中进行 `git apply --check`、应用和测试，不直接触碰登记仓库。

第三层是业务边界。状态机规定合法迁移，Worker 通过 claim、lease 和 heartbeat 避免多个执行者重复处理，测试通过只到 `HANDOFF_READY`，人工批准才到 `APPROVED`。

这也是我作为 Go 后端开发者进入 AI 工程的切入点。我不把重点放在背模型名，而是研究如何处理模型调用的超时、失败、幂等、权限、成本和证据。

### 结合当前 CodeRepair 源码

- 能力边界：`agent_patch.py` 的 `build_code_change_tools`。
- 执行边界：`workspace.py`、`patcher.py`、`test_runner.py`。
- 业务边界：`state_machine.py`、`store.py`、`review.py`。
- 证据边界：`report_writer.py`、`pr_handoff.py`、`evaluation.py`。

### 技术选型与替代

另一种做法是给通用 Agent 完整 shell 权限，让它自己修改、测试、提交。演示会更短，但权限太宽，过程也难审计。CodeRepair 选择"模型提案，程序执行"，牺牲一部分自主性，换取更清晰的安全边界和失败定位。

### 边界与追问

这个项目不涉及预训练、微调、分布式训练或推理引擎优化。适合的岗位方向是 AI Platform、Agent 工程、应用基础设施和后端研发，不应该包装成算法研究项目。
