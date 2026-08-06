# 00 使用方式与学习目标

## 你现在不需要先会什么

第一次看项目时，不需要先掌握 LangGraph、向量数据库、Kubernetes 或大模型训练。你只需要知道：Python 文件可以定义类和函数；程序能从一个函数调用另一个函数；Git 能保存代码版本。

先记住一句话：

> CodeRepair 是一个“模型只提候选改法，确定性程序负责验证，人负责最终批准”的代码变更平台。

这里故意把职责拆成三段，因为大模型输出有概率性。如果让模型直接在真实仓库执行任意命令、提交并推送，错误和越权都会直接变成外部影响。候选、验证、批准分开后，每一段都能记录、测试和拒绝。

## 第一遍先学当前已经打通的主链路

第一遍只背下面九步：

```text
登录用户登记仓库和测试模板
→ 选择外部 Patch 或 Agent Patch 模式
→ 提交需求与外部 diff，或由受限 Agent 生成候选
→ 创建并入队 Task
→ Worker claim Task
→ 独立 Workspace 应用 Patch 并运行测试
→ 生成报告与 PR handoff
→ 人工 approve 或 request changes
```

Agent 模式内部是：

```text
requirement
→ create_code_change_agent
→ search/read_file/submit_patch Tool
→ AgentPatchResult
→ Worker 写入 requested_patch.diff
→ 进入统一的 VALIDATING_PATCH
```

Worker 主流程已经调用这段代码，Router、Agent 和 Worker 都有对应测试。这里仍有一条边界：fake model 能证明调用链，不代表在线模型对真实需求的修复成功率。

## 第二遍再学三个核心取舍

### 为什么 Agent 不直接写真实仓库

因为模型可能选错文件、构造越界路径、生成不可应用的 diff，甚至尝试读取凭据。系统只给 Agent 搜索、读文件和提交候选 Patch 三类 Tool。真正的写入由 Worker 在复制出来的 Workspace 中完成。

### 为什么测试命令不能由网页随便填写

`shell=False` 只是不经过 shell 解释字符串，并不代表命令安全。用户若能提交
`python3 -c "..."`，仍然可以运行任意 Python 代码。因此 HTTP API 只接受服务端定义的测试模板，例如 `go-test` 或 `python-pytest`。

### 为什么需要人工审批

测试通过只说明已配置的测试没有发现问题，不代表需求一定理解正确，也不代表没有未覆盖回归。`HANDOFF_READY` 只是“材料可以交给人审”，不是“已创建或已合并 PR”。

## 你最终要达到的程度

学完手册后，应当能闭卷完成下面几件事：

- 用三分钟介绍 DeerFlow 上游结构和自己的二开部分。
- 画出 API、Store、Queue、Worker、Workspace、Agent、Sandbox 的关系。
- 解释 claim、lease、heartbeat 和 fencing 分别防什么问题。
- 指出至少 12 个自己修改或新增的类、字段、函数。
- 解释无 Patch、Patch 越界、测试超时、Worker 宕机和审批驳回怎样处理。
- 清楚说出当前是本地文件控制面，哪些能力需要 PostgreSQL/消息队列/容器集群才能公司化。

## 不合格的学习方式

- 只背“用了 LangGraph、RAG、Sandbox、CI/CD”这类名词。
- 把上游 DeerFlow 的所有功能都写成自己实现。
- 看到测试通过就声称已经生产可用。
- 不看 `Task` 字段和状态迁移，只背一张架构图。
- 让 AI 继续加功能，但自己说不出失败路径。

## 本章代码阅读任务

阅读顺序：第一遍控制在 40 分钟，只沿主链看入口，不展开底层库。

1. 打开 `backend/packages/harness/deerflow/code_change/models.py`，先找 `TaskStatus` 和 `PatchMode`，再找 `Project` 与 `Task`。指出 `status`、`source_commit`、`claim_id`、`patch_result`、`test_result`、`agent_thread_id` 分别保存什么。
2. 打开 `backend/packages/harness/deerflow/code_change/worker.py`，按 `create_task`、`run_next_task`、`execute_task` 的顺序读。找到外部模式与 Agent 模式的分叉，以及 `prepare_workspace`、`apply_patch_text`、`run_tests`、`write_reports` 的调用。
3. 打开 `backend/packages/harness/deerflow/code_change/agent_patch.py`，只读 `build_code_change_tools` 和 `generate_patch_with_agent`。确认它返回 `AgentPatchResult`；再回到 `worker.py::_generate_agent_patch`，确认主链真实调用它。
4. 打开 `backend/packages/harness/deerflow/code_change/review.py`，找到 `review_task` 对 `HANDOFF_READY` 的检查，以及 approve 与 request_changes 两个分支。

看到什么程度：合上源码后，能画出 Router、Task、Queue、Worker、Agent、Workspace/Test、Review，并说出两种 Patch 模式在哪里汇合。

暂不要求：不记 `to_dict/from_dict` 每一行，不展开 LangGraph、Git、subprocess 和文件锁实现，也不背所有状态。

验收动作：让同学随机指图中一个箭头，你能说出左侧输入、调用函数、右侧状态或 artifact。

## 本章自测

1. 这个项目最短的一句话定位是什么？
2. 当前端到端支持哪两种 Patch 输入？
3. fake model Agent 测试能证明什么，不能证明什么？
4. 为什么成功状态不是自动合并？
5. `local-copy` 解决了什么，没解决什么？

## 参考答案

1. CodeRepair 是一个受控代码变更平台。Agent 只提交候选改法，确定性 Worker 负责校验和测试，人负责最终批准。
2. 外部模式由用户提交 unified diff；Agent 模式由受限 DeerFlow Agent 搜索、读代码并 typed submit 候选。两种模式都进入同一套 Patch/Test/Report/Review 链。
3. 它证明真实 Agent 图、Tool binding 和 typed submit 协议可重复运行；Worker 测试还能证明候选接入执行主链。它不证明在线模型对真实仓库的修复成功率、成本或人工接受率。
4. 测试只能证明指定测试没有发现错误，不能证明模型完整理解需求。当前成功终点是 `HANDOFF_READY`，审批后是 `APPROVED`；handoff 也不等于 GitHub 已创建 PR。
5. 它让 Patch 和测试发生在固定 commit 导出的 Workspace，避免直接改脏登记仓库。测试进程仍使用宿主机权限和网络，所以它不是容器 Sandbox。
