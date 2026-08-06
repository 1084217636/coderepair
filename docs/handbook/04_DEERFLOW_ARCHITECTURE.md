# 04 原版 DeerFlow 总体结构

## 先看大图

DeerFlow 2.0 是通用 Agent Harness，不是专门的代码修复工具。它把聊天入口、模型、Agent 图、Tool、Skill、Middleware、记忆和沙箱组织在同一个仓库中。

```text
Next.js Frontend
       │ HTTP / SSE
       ▼
FastAPI Gateway ── Authentication / Thread / Run / Model API
       │
       ▼
LangGraph Runtime ── Lead Agent ── Tool / Skill / Sub-Agent
       │                              │
       ├── Checkpoint / Memory        └── SandboxProvider
       └── Run events / tracing
```

Code Change 是旁边新增的一条领域链路：

```text
Gateway /api/code-change
       │
       ├── owner-scoped Project / Task Store
       ├── Code Change Patch Agent
       └── Queue → Worker → Workspace/Test → Review
```

它复用了 Gateway 用户上下文和 DeerFlow Agent factory，但没有把上游所有模块复制一遍。

## Frontend 做什么

`frontend/` 是 Next.js 应用。上游主要页面用于 Thread 聊天、Agent 设置、Artifact、Tool、Skill 和 Memory。本项目新增 `/workspace/code-change` 控制台，用于登记仓库、提交任务、查看状态和人工审批。

前端不执行 Git、Patch 或测试。浏览器是不可信边界，不能拿到内部 Worker token，也不能决定真正执行的命令。

## Gateway 做什么

`backend/app/gateway/` 是 FastAPI 服务。它负责：

- 登录、Cookie、JWT、CSRF 和用户上下文。
- Thread/Run 等上游 API。
- Model、Agent、Skill、Memory 等配置接口。
- Code Change 的 Project、Task、Report、Review API。

Gateway 应该尽快返回，不应该长期承担测试执行。当前同步入口只用于本地演示。

## Agent Runtime 做什么

LangGraph 把一次 Agent 运行表示成有状态图。消息进入模型，模型可以选择调用 Tool，Tool 结果再回到模型，直到模型结束或到达限制。Thread 表示会话，Run 表示一次运行。

`create_deerflow_agent` 是 SDK 级工厂。Code Change 使用它创建一个权限很小的 Agent，不挂载通用 bash/write_file，只挂载搜索、读文件和提交 Patch。

## SandboxProvider 做什么

SandboxProvider 是 DeerFlow 对执行环境的抽象。不同实现可以是本地目录、容器或远程沙箱。它负责按 thread 获取隔离环境以及生命周期管理。

需要诚实区分：Code Change 当前的确定性 Worker 仍主要使用 `local-copy` Workspace，虽然上游 DeerFlow 有 SandboxProvider。只有 Patch/Test 真正通过 Provider 在容器或远程沙箱执行后，才能说个人二开完成了容器级沙箱接入。

## 配置与数据放在哪里

上游模型、Sandbox、数据库等配置来自 `config.yaml` 和环境变量。Code Change 的本地数据默认放在 `DEER_FLOW_HOME/code-change` 下，再按 owner、project、task 分目录。

这套文件布局便于学习和查看证据，但它不是分布式数据库。两个 Pod 各用本地磁盘时会看到不同任务，因此公司部署必须使用共享持久层或外部数据库。

## 上游能力与个人贡献表

| 模块 | 来源 | 面试口径 |
| --- | --- | --- |
| LangGraph Agent factory | DeerFlow 上游 | 当前 Patch Agent 直接复用 |
| Gateway Thread/Run | DeerFlow 上游 | 已阅读；Code Change 尚未建立持久化记录 |
| Tool/Skill/Middleware 框架 | DeerFlow 上游 | 能解释扩展点和调用顺序 |
| 通用 SandboxProvider | DeerFlow 上游 | 当前二开仍有 local-copy 边界 |
| Code Change Project/Task | 个人二开 | 自己的领域模型 |
| Patch Agent 三个受控 Tool | 个人二开 | 模型只能提候选，不能执行 |
| Store、Queue、lease、Worker | 个人二开 | 本地可靠性原型与演进设计 |
| Patch/Test/Report/Review | 个人二开 | 确定性执行与人工门禁 |
| Code Change 控制台 | 个人二开 | 基础前端，不包装成前端主项目 |

## 为什么先学总体结构

如果一开始钻进 `worker.py`，很容易把 API、Agent 和 Worker 看成一个进程。先分清组件边界，后面才能回答面试官常问的：“A 请求落到 Gateway 1，Worker 在另一台机器，状态和结果怎样传递？”

## 本章代码阅读任务

阅读顺序：先看上游 factory，再看个人 Agent、Gateway 与执行 Workspace。

1. 读 `backend/packages/harness/deerflow/agents/factory.py::create_deerflow_agent` 的函数签名。记录 model、tools、system_prompt、middleware、features、checkpointer、name，并看到最终 `create_agent(...)`。
2. 读 `backend/packages/harness/deerflow/code_change/agent_patch.py` 的 `build_code_change_tools`、`create_code_change_agent`、`generate_patch_with_agent`。重点看 `middleware=[]`，确认没有自动挂通用 Sandbox 或 bash Tool。
3. 读 `backend/app/gateway/routers/code_change.py` 的 router 前缀、`get_code_change_store`、`run_project_task`，理解 Gateway 如何把可信 owner 和请求变成 Task。
4. 对比 `backend/packages/harness/deerflow/sandbox/sandbox_provider.py::SandboxProvider.acquire/get/release` 与 `backend/packages/harness/deerflow/code_change/workspace.py::Workspace/prepare_workspace`。

看到什么程度：能画上游和个人二开两张图，每个方框标注来源；能指出二开复用 factory 和用户上下文的位置。

暂不要求：不跟 `_assemble_from_features` 的完整 Middleware 顺序，不研究全部 Thread/Run Router，也不读 E2B、AIO 等 Provider 实现。

验收动作：给图中每个组件写一句职责，并用源码位置证明“上游已有 / 我新增 / 目标架构”三种口径。

## 本章自测

1. DeerFlow 上游的核心定位是什么？
2. Code Change 复用了哪两个直接入口？
3. 为什么 `SandboxProvider` 存在不等于 Code Change 已用容器沙箱？
4. Frontend、Gateway、Agent 和 Worker 分别做什么？
5. 面试时怎样区分上游与个人贡献？

## 参考答案

1. 它是通用 Agent Harness，组织模型、Tool、Middleware、Thread/Run、Memory、Sub-Agent、SandboxProvider 和工作台，不是专门的代码修复产品。
2. 它复用 Gateway 用户上下文做 owner 隔离，并调用 `create_deerflow_agent` 创建受限 Patch Agent。Project/Task、Worker 和审批流程是领域二开。
3. `SandboxProvider` 是上游接口。Code Change 当前 Patch/Test 的 `sandbox_kind` 是 `local-copy`，执行仍在宿主机目录；只有 Worker 通过 Provider 在容器或远程环境执行，才能说完成接入。
4. Frontend 收集输入和展示状态；Gateway 认证、建任务和查询审批；Agent 搜索、读代码并提交候选；Worker 领取任务、应用 Patch、运行测试并写证据。
5. 先说上游通用 Agent 基础设施，再列自己新增的 `deerflow.code_change`、Router、领域模型、调度、受控 Tool、Workspace/Test/Report/Review 和控制台，不能把 factory 或 Sandbox 抽象说成自研。
