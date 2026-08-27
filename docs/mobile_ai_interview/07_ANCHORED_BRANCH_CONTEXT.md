# 07 Anchored Branch Context

## 问题 1：为什么要做 Anchored Branch

### 面试官问

这个功能解决什么问题，为什么不直接新建一个普通对话？

### 30 秒回答

长对话里经常只想深入某一段回答。直接在主 Thread 继续问，会让局部问题和主任务互相干扰；新建普通对话又会丢掉选中段落和必要背景。Anchored Branch 让用户选择一段 Anchor，系统创建带 `parent_thread_id` 的 Child Thread，并给每次分支 Run 注入 Anchor、主线摘要、局部历史、代码上下文和当前问题。讨论完成后只回流结构化 Decision，不复制整段聊天。

### 详细回答

普通分支对话有两个极端。

第一种是复制主对话全部历史。上下文很完整，但 Token 成本高，局部问题容易被无关内容淹没，而且主对话越长越难控制。

第二种是只新建空白对话。成本低，但用户还要重新解释原问题、代码位置和约束。

Anchored Branch 取中间方案。用户从主回答中选择一段文本，这段 Anchor 是分支的核心事实。系统同时保存主 Thread id、Child Thread id、可选消息位置、文件、Symbol 和代码上下文。Child Thread 仍然使用 DeerFlow 原有的 Run、Checkpoint 和 SSE，因此分支有自己的消息历史，但没有再实现一套消息数据库。

分支结束时，用户将结论整理成 `BranchDecision`，包括 summary、actions、constraints 和 rationale。点击 Apply 只把这个决策写回主 Thread metadata。下一次主 Thread Run 读取它并注入 Agent Context。这样回流的是经过人确认的结论，不是几十轮原始对话。

### 结合当前 CodeRepair 源码

- `anchored_branch/models.py::AnchorSelection` 保存选中文本和可选代码位置。
- `frontend/src/components/workspace/anchored-branch-panel.tsx` 提供分支创建、问答、Decision 和 Apply 交互。
- `frontend/src/core/anchored-branch/api.ts` 调用分支 REST 和 SSE 接口。
- `app/gateway/routers/anchored_branch.py::_create_child_thread` 创建 `branch-thread-*` 和空 Checkpoint。
- Child Thread metadata 包含 `branch_type=anchored`、`parent_thread_id` 和 ACTIVE 状态。
- `AnchoredBranchStore` 只保存分支索引、Anchor 和 Decision，消息仍在 DeerFlow Thread/Checkpoint。
- `stream_branch_run` 使用已有 `start_run`、StreamBridge 和 `sse_consumer`。

### 技术选型与替代

可以只用前端临时状态，把 Anchor 拼进下一条 Prompt。实现更快，但刷新后分支丢失，也没有独立 Thread、Checkpoint 和审计记录。

也可以复制全量主 Thread。实现简单但成本高，且分支与主线的边界不清。Child Thread 加引用和有预算 Context 更适合长期对话。

### 边界与追问

上游 DeerFlow 的 Thread、Run、Checkpoint、SSE 和 Lead Agent 是复用能力。个人新增的是 Anchor 领域、Child Thread 关系、Context Builder、Decision 和 Apply 流程。

## 问题 2：Branch Context 怎样控制 Token，又不丢掉核心信息

### 面试官问

上下文超出窗口怎么办？你按什么优先级截断？

### 30 秒回答

`BranchContextBuilder` 把 Anchor 和当前问题设为硬保留项，它们合计超预算就直接报错，不会偷偷摘要。剩余预算先给有限的主线摘要，再从最近的分支历史向前保留，最后加入代码上下文。当前默认预算 6000 Token，用字符数除以四做估算，并返回 `truncated` 标记。这个规则简单但可解释，保证分支不会失去用户明确选择的锚点。

### 详细回答

Context Builder 的输入包括：Anchor、root summary、branch history、code context 和 current question。

第一步清洗文本，去掉多余空白并限制单项长度。当前问题不能为空。Anchor 不能大于整个预算估算值，Anchor 与当前问题加起来也不能超过预算。这里选择报错，是因为静默截断 Anchor 会改变用户选择的含义。

第二步处理主线摘要。摘要最多 4000 字符，也会根据剩余预算缩短。如果缩短，`truncated=True`。

第三步选分支历史。系统从最近消息向前遍历，但最多使用可用空间的一半，保证代码上下文仍有空间。被保留的历史最后恢复成时间顺序。

第四步按输入顺序加入代码上下文，空间不足就停止。最后将所有内容合并，用总字符数除以四估算 Token。

`to_prompt` 用 XML 风格标签区分不同来源，并明确告诉模型这些内容是 Context，不是指令。这能降低结构混淆，但不能彻底阻止源码里的 Prompt Injection。

### 结合当前 CodeRepair 源码

- `anchored_branch/context.py::BranchContextBuilder` 实现预算算法。
- `_clean` 压缩空白并限制字符串长度。
- `_entry` 把字符串或字典规范成文本。
- `BranchContext.to_prompt` 生成 `<anchor>`、`<root_summary>`、`<branch_history>`、`<code_context>` 和 `<current_question>`。
- `AnchoredBranchContextMiddleware.before_model` 将 Prompt 作为隐藏 SystemMessage 注入。

### 技术选型与替代

更精确的实现会用当前模型 tokenizer，并按消息角色、代码块和 Symbol 做分段预算。还可以对旧分支历史做增量摘要，或者使用检索只选与当前问题相关的代码。

当前固定优先级的优点是稳定、容易测试；缺点是最近历史不一定最相关，代码上下文也没有语义重排。

### 边界与追问

6000 是 Branch Context 的应用预算，不等于模型完整上下文窗口。完整请求还包括 system prompt、Tool 描述和其他 Middleware 消息。

`estimated_tokens` 是近似值，不能当成实际计费数据。

## 问题 3：Decision、Apply 和 HITL 怎样工作

### 面试官问

分支讨论结束后，Apply 会不会直接修改主对话或代码？

### 30 秒回答

不会。分支先保存结构化 `BranchDecision`，用户显式 Apply 后，系统把 Decision 写到主 Thread metadata，并把分支标为 APPLIED。下一次主 Thread Run 会从 metadata 取出 Decision，放进 runtime context，再由 Middleware 注入 SystemMessage。Decision 只是人确认的约束，不是代码修改命令；主 Agent 若要改代码，仍需走原来的 Tool、Sandbox 和测试链。

### 详细回答

Decision 分两步处理。

第一步 create decision。请求必须包含 summary，可以附加 actions、constraints 和 rationale。一个分支已经有不同 Decision 时不能静默覆盖。这样用户有机会先检查结构化结论。

第二步 apply。没有 Decision 时返回 409。Apply 更新主 Thread metadata 中的 `anchored_branch_decision` 和 branch id，更新 Child Thread 状态，并在 AnchoredBranchStore 中把 Decision 标记 applied，记录时间。

主线下一次执行时，Gateway 的 `start_run` 读取 Thread metadata，把 Decision 加到 `config.context.branch_decision`。Lead Agent 构造阶段发现 branch decision 后，装配 `AnchoredBranchContextMiddleware`。Middleware 生成隐藏 SystemMessage，告诉 Agent 这是人工审阅的约束，并明确禁止在没有 Tool 证据时声称代码已修改。

这个设计把"讨论结论"和"执行动作"分开。用户批准的是一份 Decision，不是授权系统跳过工具直接修改代码。

### 结合当前 CodeRepair 源码

- `anchored_branch/models.py::BranchDecision` 定义结构化字段和 applied 状态。
- `anchored_branch.py::create_branch_decision` 创建 Decision。
- `apply_branch_decision` 更新主、子 Thread metadata 和分支 Store。
- `app/gateway/services.py::start_run` 将 metadata Decision 注入 run context。
- `agents/lead_agent/agent.py` 按 context 决定是否加入 Anchored Middleware。
- `anchored_branch/middleware.py` 创建隐藏 SystemMessage。

### 技术选型与替代

可以把整段分支 Transcript 追加到主对话，但噪声大且可能包含中间错误。结构化 Decision 更适合审阅、检索和审计。

如果未来多人协作，还应给 Apply 增加权限、版本号和乐观锁，防止两个用户对同一分支提交冲突决策。

### 边界与追问

Apply 不会 cherry-pick Git 分支，也不会合并数据库中的消息树。这里的 Branch 是对话上下文分支，不是 Git branch。

当前 AnchoredBranchStore 仍是本机 owner 目录中的 JSON 文件，不是多机共享数据库。
