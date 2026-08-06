# 10 真实 Patch Agent 链路

## 这一版和“外部 Patch 工作流”有什么不同

外部模式由 API 或 CLI 直接传入 unified diff。它适合确定性回归。Agent 模式由 Worker 根据 `patch_mode="agent"` 调用受限 Patch Agent，再进入同一套 Patch/Test 主链。

真实 Agent 版本增加：

```text
requirement
→ create_deerflow_agent
→ code_change_search
→ code_change_read_file
→ code_change_submit_patch
→ requested_patch.diff
→ 原有确定性 Worker
```

重点不是“调用过一次模型”，而是模型输出必须通过一个有 Schema 的 Tool 进入原来的控制面。

## 为什么只给三个 Tool

### code_change_search

输入查询，返回候选文件路径、分数、原因和有界 snippet。它帮助模型决定先看哪里。

### code_change_read_file

输入仓库相对路径和行范围。服务端 resolve 后确认路径仍在 repo root 中，并限制最多读取行数和字符数。

### code_change_submit_patch

输入 `patch_text` 和 `rationale`。Tool 检查非空、最大字节数、changed files 和路径逃逸，然后把候选保存在请求级 capture 中。

它只“接收候选”，不应用 Patch。Tool 返回 accepted 只说明结构边界通过，不代表测试通过。

## 为什么不能解析模型最后一段 Markdown

如果系统在模型普通回复中寻找 ```diff 代码块，会遇到：

- 模型输出了多个代码块，不知道哪个是真正结果。
- 前后解释被误当 Patch。
- 路径和大小校验容易散落在解析逻辑中。
- 模型没按协议提交，系统却替它猜测成功。

当前实现要求 Agent 必须调用 `code_change_submit_patch`。没有调用就是硬失败。这样工具调用轨迹、参数 Schema 和错误都可观察。

## create_deerflow_agent 在哪里真正使用

代码位于：

```text
backend/packages/harness/deerflow/code_change/agent_patch.py
```

`create_code_change_agent` 调用上游 `create_deerflow_agent`，传入模型、三个 Tool、专用 system prompt 和最小 Middleware。`generate_patch_with_agent` 使用 `thread_id`、`run_id` 和
`task_id` 写入运行 metadata，便于跟踪一次生成属于哪个业务 Task。

这里的 thread/run 是 Task 创建的关联 ID。当前图没有 checkpointer，也没有通过 Gateway 创建持久化 Thread/Run，所以报告能关联一次调用，却不能查询完整上游 Run 事件历史。面试时应说“任务级 Agent 关联 metadata”，不能说“已接入持久化 Thread/Run 控制面”。

`worker.py` 的 `execute_task` 在 Agent 模式进入 `GENERATING_PATCH`，调用 Patch Generator，将 `AgentPatchResult` 写回 Task，再进入 `VALIDATING_PATCH`。这里的证据不只来自 README：fake model 测试运行真实 LangGraph Agent 图，Worker 测试还验证候选继续经过 apply 和 test。

## 为什么 Agent 没有直接使用通用 Sandbox Tool

生成阶段只需读和提交候选，不需要执行命令。挂载通用 bash、write_file 会把权限扩大到没有业务理由的范围。

Sandbox 更应该包住后面的 Patch 应用与测试。当前 Worker 的 local-copy 是可查看的隔离原型；容器化 Provider 是下一层执行隔离。不要把“Agent 没有 bash”误说成“已经拥有完整容器安全”。

## Agent 失败怎样进入状态机

典型失败：

- 模型 API 超时或限流。
- 搜索没有召回目标文件。
- read_file 尝试越界。
- submit_patch 路径非法或 Patch 过大。
- 模型只回复文字，没有调用 submit Tool。

这些都不能进入 `PATCH_RECEIVED`。Task 应记录 `GENERATING_PATCH → FAILED`，保留错误、thread/run 和 attempt。可重试错误使用受限次数重试；越权和结构错误应直接要求人工修改需求或 Patch。

## 怎样测试而不花模型费用

测试使用能输出固定 tool_calls 的 fake chat model：

```text
第 1 轮：调用 code_change_search
ToolResult 返回候选
第 2 轮：调用 code_change_submit_patch
ToolResult 返回 accepted
第 3 轮：模型结束
```

这样真实经过 `create_deerflow_agent` 和 ToolNode，但不需要 API key，CI 结果可重复。在线模型评测另行执行，不能让普通 CI 依赖不稳定外部模型。

## 一次失败反馈修复

更完整的 V11 流程允许第一次测试失败后，把“有界、脱敏的测试摘要 + 当前 Patch”返回给 Agent，一次性生成修订候选。为什么只允许一次？防止 Agent 在错误循环里无限消耗 token 和测试资源。

当前只有 Task retry 与 request changes，尚未完成模型自动读取失败日志再生成一次候选。不能把普通 Worker retry 包装成 Agent 自我修复。

## 面试回答

> 我没有让模型直接操作仓库。DeerFlow Agent 只拿到搜索、按行读取和 typed submit_patch 三个 Tool，候选 diff 先做路径和大小校验，再交给原有 Worker。Agent 没调用提交 Tool就失败，不会从自然语言里猜 Patch。CI 用 fake tool-calling model 真实跑 Agent 图，线上模型能力则由独立固定任务集评测。

## 本章代码阅读任务

阅读顺序：先看 Agent Tool 与结果结构，再跟 Worker 和 Router，最后用两层测试核对。

1. 打开 `backend/packages/harness/deerflow/code_change/agent_patch.py`，先读 `PatchCapture` 和 `AgentPatchResult` 字段，再按 `_safe_repo_file`、`build_code_change_tools`、`create_code_change_agent`、`generate_patch_with_agent` 的顺序读。每个函数记录输入、返回值和一个拒绝分支。
2. 打开 `backend/packages/harness/deerflow/code_change/worker.py`，定位 `PatchGenerator` 类型、`execute_task` 的 `PatchMode.AGENT` 分支和 `_generate_agent_patch`。跟清 `agent_thread_id`、`agent_run_id`、`agent_rationale`、`agent_changed_files` 从哪里产生并写回 Task。
3. 打开 `backend/app/gateway/routers/code_change.py`，只读 `TaskRunRequest` 和 `run_project_task`。确认 `patch_mode` 只能是 `external` 或 `agent`，Agent 模式怎样携带可选 `agent_model_name`，以及请求最终仍先创建 `QUEUED` Task。
4. 打开 `backend/tests/code_change/test_agent_patch.py`，逐个看 Tool 越界、重复 submit、真实 Agent 图 submit、未 submit 失败四个测试。再在 `test_worker.py` 中定位 Agent 模式测试，确认 fake Patch Generator 的结果继续经过 Workspace、apply、test 和 `HANDOFF_READY`。

看到什么程度：闭卷讲清“HTTP 选择 agent 模式”到 `requested_patch.diff` 的每个函数，并能解释 Agent Tool 返回 accepted 为什么不等于任务成功。暂不要求会接真实模型 API key。

验收动作：画出 Agent 模式时序图，标出三次 Tool 调用、Task Agent 字段、`VALIDATING_PATCH` 汇合点和四个失败出口。

## 本章自测

1. 为什么只给 Patch Agent 三个 Tool？
2. 为什么必须调用 `code_change_submit_patch`，不能解析最终 Markdown？
3. Agent 模式怎样接回确定性 Worker？
4. `middleware=[]` 在这里表示什么？
5. fake model 集成测试能证明和不能证明什么？
6. Agent 只回复文字但没调用 submit 时，Task 应怎样结束？

## 参考答案

1. 生成候选只需要搜索、按行读代码和提交 diff。不给 bash、write_file 和 git push 能缩小读取密钥、联网、删文件和直接改仓库的权限面。
2. typed Tool 有固定参数 Schema、单次提交限制和统一路径/大小校验。解析 Markdown 会猜测多个代码块的含义，并可能绕过提交协议。
3. `execute_task` 在 `PatchMode.AGENT` 分支调用 Patch Generator，将 `AgentPatchResult.patch_text` 原子写成 `requested_patch.diff`，保存 Agent 元数据，然后进入 `VALIDATING_PATCH`，与外部模式共享 apply、test、report 和 review。
4. 它表示 Patch Agent 显式接管 Middleware 列表且使用空列表，不按默认 `RuntimeFeatures` 自动挂载 Sandbox、Memory 或其他通用能力。这与后面的 Worker 执行隔离是两件事。
5. 它证明真实 Agent 图、Tool binding、ToolNode、candidate capture 和 no-submit hard failure可重复运行。它不证明在线模型在真实仓库上的修复成功率、成本或人工接受率。
6. Patch Generator 抛出协议错误，Task 记录 `AGENT_GENERATION_FAILED`，从 `GENERATING_PATCH` 进入 `FAILED`，不得继续测试未修改 Workspace。
