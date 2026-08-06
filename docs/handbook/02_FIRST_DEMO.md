# 02 跑通第一个演示

这一章的目的不是让你一次配置全部 DeerFlow，而是让你看到输入、状态和产物之间的关系。每条命令先看懂再执行。

## 1. 环境里分别有什么

仓库根目录主要有两部分：

```text
backend/    Python 3.12、FastAPI、DeerFlow Agent 与 Code Change Worker
frontend/   Next.js 16、React 19 的聊天工作台和 Code Change 控制台
```

后端使用 `uv` 管理 Python 依赖，前端使用 Node.js 22 和 pnpm 10。第一次只验证后端，不必同时学 React。

## 2. 安装与自检

在仓库根目录执行：

```bash
make check
make setup
```

`make check` 只检查本机依赖。`make setup` 会生成本地配置，模型 API key 应放在 `.env`，不能提交到 Git。

若只跑 Code Change 的确定性测试，不需要真实模型 key：

```bash
cd backend
PYTHONPATH=. uv run pytest tests/code_change -q
```

为什么先跑测试？因为它能在启动服务以前确认状态机、Patch 校验、Workspace 和 Store 的基本契约没有破坏。服务能启动不等于功能正确。

## 3. 准备一个允许访问的演示仓库

Code Change 不应该扫描机器上的任意目录。先配置允许根目录：

```bash
export CODE_CHANGE_ALLOWED_REPO_ROOTS=/absolute/path/to/demo-root
export DEER_FLOW_CODE_CHANGE_ENABLED=true
```

然后在这个根目录下准备一个小 Git 仓库。HTTP API 只能选择固定测试模板。当前后端默认 profile 是：

```text
python-pytest  → python3 -m pytest -q
go-test        → go test ./...
frontend-check → pnpm check
```

管理员可以通过 `DEER_FLOW_CODE_CHANGE_TEST_PROFILES` 配置更多 profile。模板名和实际 argv 由服务端控制；`load_test_profiles()` 的返回值才是实际可用清单。这样浏览器不能把任意 Python 或 shell 命令塞进 Gateway。

## 4. 启动服务和页面

标准开发模式：

```bash
make dev
```

默认工作台地址通常是 `http://localhost:2026`。登录后打开：

```text
/workspace/code-change
```

页面完成四件事：登记仓库、选择项目、提交需求与可选 Patch、查看状态和报告。提交只创建 `QUEUED` Task；内部 Worker 还要消费它。内部 Worker token 不会下发到浏览器。

## 5. 第一次建议使用外部 Patch

先使用一份你自己能读懂的 unified diff。原因是：这样可以把“Agent 是否生成正确”这一变量拿掉，先验证后半段确定性链路。

```text
创建项目
→ 需求 + 外部 Patch
→ git apply --check
→ Workspace 应用
→ 固定测试模板
→ HANDOFF_READY
→ 人工审批
```

如果不提供 Patch，系统应明确返回 `PATCH_REQUIRED`，或者在启用 Agent 模式时进入
`GENERATING_PATCH`。它不能在没有代码变更时跑一下原仓库测试，然后假装任务完成。

## 6. 再验证 Agent 模式

Agent Task 会由 Worker 调用 `create_deerflow_agent`，只挂载三个请求级 Tool：

- `code_change_search`
- `code_change_read_file`
- `code_change_submit_patch`

Agent 必须调用提交 Tool。系统不会从普通回答或 Markdown 代码块里猜 Patch，因为那会绕过类型和路径校验。候选写入 Task 后，仍然走统一的 Workspace、apply、test、report 和 review。

## 7. 你应该查看哪些产物

每个任务目录里重点看：

```text
task.json             当前字段和状态
requested_patch.diff  外部或 Agent 提交的候选 Patch
patch_check.log       git apply --check 结果
patch_apply.log       实际应用结果
test.log              测试输出
sandbox_policy.json   本次执行策略
task_report.md        给人的汇总
audit.json            结构化审计材料
human_review.json     审批决定
```

不要只看页面上的绿色状态。面试官问“你怎样证明测试真的执行了”时，退出码、命令模板、日志路径和报告生成代码才是证据。

## 常见启动问题

- `uv: command not found`：先安装 uv，不要改成全局 pip 乱装依赖。
- 找不到 Node/pnpm：只影响前端；后端测试仍可独立完成。
- `repo_path is outside allowed roots`：把仓库放进配置根目录，不要为了演示删安全校验。
- Code Change API 404/503：检查 `DEER_FLOW_CODE_CHANGE_ENABLED=true`，并确认测试 profile 配置能被解析。
- Worker 401/403：内部领取接口需要服务端 token，浏览器不应调用它。

## 本章代码阅读任务

阅读顺序：先核对配置，再沿一条完整 Router 测试看状态与 artifact。

1. 先读 `backend/packages/harness/deerflow/code_change/test_profiles.py` 的 `DEFAULT_TEST_PROFILES`、`load_test_profiles`、`_parse_profiles`。说出默认 profile 名、环境变量名和配置错误分支。
2. 再读 `backend/app/gateway/routers/code_change.py` 的 `ProjectCreateRequest`、`TaskRunRequest`、`create_project`、`run_project_task`、`run_worker_once`。记录请求输入和返回状态，确认普通浏览器不能通过 `require_internal_worker`。
3. 打开 `backend/tests/code_change/test_code_change_router.py`，先读 `test_code_change_router_runs_patch_task`，再读 Agent 模式入队测试。按 project、task、worker、report、approve 的顺序写下每个断言证明什么。
4. 打开一次测试生成的任务目录。按 `task.json`、`workspace_manifest.json`、`patch_check.log`、`patch_apply.log`、`test.log`、`task_report.md`、`human_review.json` 的顺序查看。`task.json` 至少找到 status、source_commit、steps、patch_result、test_result 和 Agent 字段。

看到什么程度：能独立跑确定性测试，并把 HTTP 操作、状态和 artifact 对成表；知道 Agent 模式需要模型配置，而 fake model 测试不需要 API key。

暂不要求：第一次不必启动全部 DeerFlow 外部通道、配置真实在线模型或学习 React。日志只读到能确认命令、退出码和失败原因。

验收动作：完成一条外部 Patch 成功任务和一条空 Patch 失败任务；再运行 Agent fake-model 测试，分别说明三次执行证明什么。

## 本章自测

1. 为什么第一次演示建议先传外部 Patch？
2. 前端提交以后为什么可能先看到 `QUEUED`？
3. 怎样证明测试真的执行过？
4. 外部模式空 Patch 的正确结果是什么？
5. fake model Agent 测试证明了什么？

## 参考答案

1. 这样先拿掉模型质量这个变量，只验证 Project、Task、队列、Workspace、Patch、测试、报告和审批是否真实工作。
2. 提交路由只入队。还需要内部 Worker 调用 `run_next_task` 消费；浏览器没有内部 token，也不应直接领取任务。
3. 检查 `task.test_result` 的 command、exit_code、duration、timed_out 和 log_path，再打开 `test.log` 与 `sandbox_policy.json`。页面绿色徽标本身不是充分证据。
4. Task 进入 `FAILED`，`error_code` 为 `PATCH_REQUIRED`，且不会生成 `test.log`。系统不能测试未修改仓库后返回成功。
5. 它证明真实 DeerFlow Agent 图能绑定受控 Tool，并要求模型通过 `code_change_submit_patch` 交付候选。Worker Agent 测试进一步证明候选进入 apply/test；它们仍不证明在线模型修复成功率。
