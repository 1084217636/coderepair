# 01 项目解决什么问题

## 从一次普通改代码需求开始

团队里常有这样的需求：“登录接口空用户名时返回 500，请修掉并补测试。”人工处理通常要经历定位仓库、找文件、读上下文、修改、运行测试、整理 diff、写 PR 描述和等待审批。

大模型能加快前几步，但直接让模型接触真实仓库又有风险：

- 它可能读错上下文，修改了名称相似但无关的文件。
- 它可能生成语法正确却无法应用到当前版本的 Patch。
- 它可能执行危险命令或继承服务进程中的密钥。
- 它可能说“测试通过”，但实际上没有执行测试。
- 两个 Worker 可能同时处理同一个任务，生成互相覆盖的结果。
- 不同用户的仓库、日志和 Patch 可能串到一起。

Code Change 二开的目标不是让模型拥有更多权限，而是把这些不确定行为放进一个可观察、可拒绝、可重试的流程。

## 项目真正交付的东西

一次成功任务最终交付的是一组候选材料：

- 一份经过路径校验并能应用的 unified diff。
- 一次服务端批准测试模板的真实执行结果。
- 变更文件、增删行数、耗时、退出码和截断情况。
- 任务状态和时间线。
- 给人工审阅的 Markdown 报告。
- 一个 PR handoff 脚本或草稿材料。

它没有自动合并代码。当前终点是人工可审的 `HANDOFF_READY`，审批后是 `APPROVED`。只有未来真正调用 GitHub 并拿到 PR number、URL 后，才能进入 `PR_CREATED`。

## 为什么选择“控制面”这个定位

控制面负责决定任务是谁的、处于什么状态、谁能领取、允许执行什么、产生了哪些证据。真正耗时的 Patch 应用和测试由 Worker 执行。这样 API 进程不需要长期占着一次 HTTP 请求，也便于以后增加 Worker 数量。

当前 HTTP 路由创建 Task 后只入队，`/worker/run-once` 由内部身份触发一次消费。CLI 中的 `run_task_now` 可同步执行，便于本地测试；公司部署应使用持续运行的独立 Worker。不要把前端提交按钮说成浏览器亲自执行测试。

## 为什么基于 DeerFlow，而不是从零写脚本

一个纯脚本也能复制目录、应用 Patch 和跑测试，但它不能很好地承载 Agent 上下文、Tool 调用、Thread/Run、模型配置、鉴权和前端工作台。DeerFlow 已经解决通用 Agent Harness 问题，个人二开把精力放在代码变更领域的状态机、安全边界和可靠执行。

这也是二次开发的价值：不是改 Logo，也不是把上游 README 换个名字，而是找到上游通用能力和具体业务流程之间的缺口，然后增加一条完整纵向链路。

## 明确不做的范围

当前项目不承诺：

- 对任意大型仓库都能自动修复成功。
- 自动接受模型生成的代码并合并到主分支。
- 自研大模型训练或推理引擎。
- 已完成多机分布式一致性。
- 已在生产 Kubernetes 集群承载真实流量。
- 已测得真实人工接受率。

这些边界不会削弱项目。相反，能说明为什么没有盲目增加权限，以及下一步应怎样演进，是平台研发面试中很重要的判断力。

## 面试的一分钟回答

> 我基于 DeerFlow 2.0 二次开发了一个代码变更控制面。上游提供通用 Agent、Tool、Thread/Run 和 SandboxProvider；我新增了 owner 隔离的 Project/Task、任务状态机、带租约的 Worker 领取、受控 Patch Agent、Workspace 应用与测试、报告、人工审批和 PR handoff。Task 支持外部 Patch 和 Agent Patch 两种模式，模型只能搜索、读文件并 typed submit 候选，之后统一进入确定性 Worker。当前版本适合本地与单机验证，多机部署会把文件 Store、本地 claim 和宿主机执行换成 PostgreSQL、可靠队列和容器 Sandbox。

## 本章代码阅读任务

阅读顺序：从 HTTP 输入开始，跟到执行产物和审批终点。

1. 先读 `backend/app/gateway/routers/code_change.py` 的 `TaskRunRequest` 和 `run_project_task`。确认请求有 `requirement`、`patch_text`、`patch_mode`、`agent_model_name`，并调用 `create_task(..., enqueue=True)` 后返回。
2. 再读 `backend/packages/harness/deerflow/code_change/worker.py::execute_task`。标出外部/Agent 分支、Workspace、apply、test、report；重点看外部空 Patch 的 `PATCH_REQUIRED` 和 Agent 失败的 `AGENT_GENERATION_FAILED`。
3. 接着读 `backend/packages/harness/deerflow/code_change/pr_handoff.py` 的 `PRHandoff`、`write_pr_handoff`、`render_script`。确认产物是 JSON/脚本路径，不是 GitHub 返回的 PR number 或 URL。
4. 最后读 `backend/packages/harness/deerflow/code_change/review.py::review_task`。确认它只允许 `HANDOFF_READY`，并把决定写入 `human_review.json`。

看到什么程度：能列出一次成功任务交付的材料，并指出每类材料由哪个函数产生；还能说明 Agent 模式只改变候选来源，不跳过后续验证。

暂不要求：不读完整 FastAPI 认证、LangGraph 内部调度和 shell 脚本模板。第一遍只掌握控制面职责和边界。

验收动作：用一分钟回答项目解决什么问题；回答中至少出现 Task、候选 Patch、固定测试、人工审批和一个当前限制。

## 本章自测

1. 这个项目主要解决“生成代码”还是“治理代码变更”？
2. 为什么称它为控制面？
3. 一次成功任务真正交付什么？
4. 为什么上游 DeerFlow 仍值得复用？
5. 当前项目最重要的范围边界是什么？

## 参考答案

1. 主要解决治理。它把候选 Patch、确定性验证、状态证据和人工审批分开，防止模型的一句自然语言直接变成仓库副作用。
2. 控制面保存任务归属、状态、领取权、测试模板和审计证据。耗时的 Agent、Patch 与测试由 Worker 执行，API 负责接收、查询和审批。
3. 交付可应用的 unified diff、固定测试结果、变更与耗时统计、状态时间线、Markdown 报告、审计 JSON 和 PR handoff 材料。它不自动合并代码。
4. 上游已经处理通用 Agent factory、Tool 调用、模型配置、Thread/Run 和工作台。个人二开把工作集中到代码变更领域对象、执行边界和失败恢复。
5. JSON/JSONL Store 仍是单机；`local-copy` 仍是宿主机执行；handoff 不是真实 PR；fake model 与外部 Patch 评测不能代表在线模型高成功率。
