# 19 简历口径与面试问答

## 项目名称

**CodeRepair：基于 DeerFlow 2.0 的受控 Agent 代码变更平台**

不要只写“DeerFlow 二次开发”，否则面试官不知道你改了什么；也不要写“全自动 AI 程序员”，当前系统有人工门禁和明确边界。

## 三条简历描述

下面口径要根据最终代码和 CI 数字更新：

- 基于 DeerFlow 2.0 扩展 owner 隔离的 Project/Task 控制面，将代码变更拆为 Agent 候选生成与确定性 Worker 验证；使用任务级 Agent 关联标识串联检索、typed Patch Tool、Workspace 测试、报告和人工审批。
- 设计任务状态机及 claim_id、lease、heartbeat、fencing 机制，处理 Worker 宕机、重复领取和旧执行者覆盖；HTTP 侧使用服务端测试模板、仓库根与 Patch 路径校验、内部 Worker 身份，收紧宿主机执行面。
- 建立 fake-model Agent 集成测试与固定任务评测，分别验证真实 Tool 调用链和 Patch/Test/安全拦截；新增 Next.js Code Change 控制台查看任务、报告并 approve/request changes。

如果容器 Sandbox 仍未接入，把“Workspace 测试”写清楚，不要改成“容器沙箱执行”。

## 三分钟介绍

> 我第二个项目是在 DeerFlow 2.0 上做代码变更控制面。原版 DeerFlow 是通用 Super Agent Harness，已有 Agent、Tool、Skill、Middleware、Thread/Run 和 SandboxProvider。我没有把这些上游能力都算成自己的，而是在它旁边新增 Project、Task、状态机和 Worker。
>
> 一次任务由登录用户登记受控仓库并提交需求。Agent 通过 DeerFlow factory 创建，但只拿到搜索、按行读代码和 typed submit_patch 三个 Tool，不能直接写仓库或执行 bash。候选 unified diff 进入确定性 Worker，Worker 用带 claim_id 的 lease/heartbeat 领取，在固定 source commit 的独立 Workspace 做路径校验、git apply 和服务端固定测试模板。通过后生成 report 与 PR handoff，状态只到 HANDOFF_READY，再由人批准或要求修改。
>
> 我重点解决的是 AI 行为治理而不是只接模型 API：没有 Patch 不会跑原仓库测试冒充成功，旧 Worker 会被 fencing 拒绝，HTTP 用户不能传任意 test command，不同 owner 的目录隔离。当前文件 Store 和 local-copy 适合单机验证；公司多机版会换成 PostgreSQL、事务 Outbox、可靠队列和真正的容器 Sandbox。项目有 fake model 的真实 Agent 图测试，外部 Patch 的 20 用例是确定性回归，不把它夸大成模型能力评测。

当前 `agent_thread_id/agent_run_id` 是 Task 自己生成并传入 Agent config/metadata 的关联标识。Patch Agent 没配置 checkpointer，也没有调用 Gateway Thread/Run API，所以简历不写“已完成持久化 Agent 会话与 Run 事件追踪”。

## 高频追问

### 为什么选择 DeerFlow？

因为它已经提供通用 Agent Harness 和扩展点，我把精力用于代码变更的状态、执行安全和人工门禁。相比从零写 Agent，更贴近公司基于开源底座做领域平台的工作。

### 你到底二开了什么？

回答具体目录、类和链路：`deerflow.code_change`、Gateway Router、Patch Agent 三个 Tool、Project/Task、Store、Worker、Patch/Test/Report/Review、控制台和测试。再明确上游部分。

### 为什么不直接给 Agent bash？

生成候选 Patch不需要执行权限。最小 Tool 集减少密钥读取、联网、删除文件和命令注入风险。执行交给确定性 Worker和 Sandbox。

### `shell=False` 为什么不安全？

它只防 shell 元字符解释。允许 `python -c` 仍是任意代码执行，测试项目本身也能读取继承环境。因此 API 使用服务端 profile、最小 env，生产要放容器。

### claim、lease、heartbeat、fencing 有什么区别？

claim 竞争执行权；lease 让崩溃持有者到期；heartbeat 给活跃任务续租；fencing 在写结果和 release 时拒绝旧 claim。

### 为什么测试通过还要人工审批？

测试覆盖有限，模型可能误解需求。HANDOFF_READY 表示证据齐全可审，不代表业务正确或 PR 已创建。

### 如何扩展到多服务器？

Project/Task 元数据放 PostgreSQL，Task+Outbox 同事务，队列唤醒 Worker，DB 条件更新生成 fencing token，artifact 放对象存储，Sandbox 使用短生命周期容器。Gateway 无状态，Worker 按队列深度扩容。

### 为什么不用向量数据库？

当前小型仓库先用可解释词法检索完成链路。向量库不是目的；当 Recall@5 和规模证明需要时，再做 symbol/chunk、BM25+Embedding 和 rerank。

### 创建真实 PR 了吗？

当前只生成 handoff/草稿材料，没有 GitHub number/URL，所以不声称 PR_CREATED。真实接入还要 GitHub App 权限和外部成功后本地宕机的幂等处理。

### 项目最大的不足？

当前 local-copy 不是强沙箱，文件 Store 与 owner-scoped JSONL 不是多机多租户调度；在线 Agent 任务集和人工接受率数据也不足。这些边界比“再加一个模型 Provider”更值得继续完善。

## 不要说的句子

- “我实现了 DeerFlow 的全部 Agent 架构。”
- “支持生产级多租户沙箱。”
- “20 个用例证明模型修复成功率很高。”
- “已经自动创建并合并 PR。”
- “K8s 部署以后天然高可用。”

这些说法都容易被一两个代码追问击穿。

## 本章代码阅读任务

阅读顺序：按三条简历描述逐条找证据，不要只读一份 README 后背句子。

1. 第一条简历证据：读 `models.py::Project/Task/PatchMode`、`agent_patch.py::create_code_change_agent/generate_patch_with_agent`、`worker.py::execute_task`。确认 Agent 候选怎样进入 Task，再跟到 report 和 review。
2. 第二条简历证据：读 `store.py::claim_next_task/renew_task_claim/save_task/release_task_claim`、`test_profiles.py::load_test_profiles`、`agent_patch.py::_safe_repo_file`、`routers/code_change.py::require_internal_worker`。每个安全词都要能指到实际判断条件。
3. 第三条简历证据：读 `tests/code_change/test_agent_patch.py`、`test_worker.py` 中 Agent 模式与 heartbeat 用例、`evaluation.py::fixed_cases/run_evaluation`，以及 `.github/workflows/code-change-platform.yml` 两个 job。记住当前评测只测外部 Patch 回归。
4. 前端证据：读 `frontend/src/app/workspace/code-change/code-change-console.tsx` 的四个 handler 与按钮禁用条件；再读 `frontend/src/core/code-change/api.ts` 对应请求函数。只确认功能存在，不把项目包装成前端主项目。

看到什么程度：简历上每一个名词都能在 20 秒内报出至少一个文件、一个函数或字段和一个测试证据。说不出代码位置的句子先从简历删除。

暂不要求：不背上游 DeerFlow 每个 Middleware，也不编造线上 QPS、真实人工接受率、K8s 生产数据或模型成功率。数字只使用 CI 与评测真实输出。

验收动作：录制三分钟介绍，再让同学从三条简历描述中任抽五个名词追问。回答必须包含当前实现、设计理由和未完成边界。

## 本章自测

1. 用一句话说明项目，不使用“强大”“智能化”等形容词。
2. 你个人二开了什么，上游已有什​​么？
3. 为什么 Patch Agent 不直接拿 bash？
4. 如何证明 Agent 不只是 README 中的概念？
5. 如何证明 Worker 不是简单同步脚本？
6. 当前项目最大的三个边界是什么？
7. 面试官问多机部署时，怎样避免把目标架构说成已完成？
8. 为什么这个项目适合 AI Platform/App Infra 岗位？

## 参考答案

1. 我基于 DeerFlow 2.0 做了一个受控代码变更平台，Agent 通过只读检索 Tool 提交候选 diff，Worker 在固定基线 Workspace 校验和测试，最后由人审批。
2. 上游已有 Agent factory、Tool/Middleware、Thread/Run、Memory、SandboxProvider 和通用工作台；个人二开增加 Project/Task、状态机、受控 Patch Agent、Queue/lease/fencing、Patch/Test/Report/Review API 与控制台。
3. 生成候选不需要执行权限。不给 bash 能减少读密钥、联网、删文件和任意命令风险；写入与测试由有固定步骤的 Worker 承担。
4. `agent_patch.py` 真实调用 `create_deerflow_agent`，fake model 测试经过 ToolCall 和 submit；Worker Agent 模式测试还验证候选继续 apply、test 并到 `HANDOFF_READY`。
5. Task 先入队；Worker 竞争 claim，后台 heartbeat 续 lease，保存和 release 使用 claim_id fencing；失败可按 attempt 重试。这些都有 Store/Worker 测试。
6. `local-copy` 不是强沙箱；JSON/JSONL Store 不能多机共享；固定外部 Patch 评测和 fake model 测试不能代表在线模型真实成功率或人工接受率。
7. 先说当前单机文件版的真实证据，再说目标会使用 PostgreSQL、Outbox、可靠队列、对象存储和容器 Sandbox，最后明确这些目标组件尚无生产部署与压测证据。
8. 它包含 Agent Tool 治理、异步任务状态、可靠领取、执行安全、人机审批、评测与平台化演进，贴近 AI 应用基础设施。它不覆盖 CUDA、分布式训练或推理引擎等底层 AI Infra。
