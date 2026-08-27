# 07 Anchored Branch Context：面试背诵稿

## 一句话定位

我没有发明对话分支。ChatGPT、Claude Code 等产品已有类似能力。我的二次开发重点是：针对长回答中的局部文本建立细粒度 Anchor，并研究独立 Branch 在“背景够用”和“不要携带无关主线”之间怎样分配上下文。

## 30 秒项目回答

用户读一段复杂回答时，常常只想追问其中一句或一个代码片段。直接在主对话继续问会让局部讨论污染后续主任务；新建空白对话又会丢背景。我的实现保存 Main message ID、选中文本 offset、Anchor 原文和可选代码引用，创建独立 Child Thread。每次 Branch Run 使用 `Main Task Summary + Anchor + Relevant Main Context + Branch History` 构造 Prompt，并受 Token Budget 限制。Branch 的消息、搜索和工具调用只进入 Child Checkpoint；默认关闭不会写 Main Thread。

## 用户操作到后端的完整过程

1. 左侧 Main Thread 正常显示 DeerFlow 对话。
2. 每条助手消息 DOM 带 `data-branch-message-id`。用户选中文字后，前端读取 Selection、所属消息 ID 和渲染文本偏移，在选区旁显示 Ask in Branch。
3. `POST /api/anchored-branches` 提交 Main Thread ID 和 Anchor。Gateway 先检查 Thread owner，再检查 message ID 确实存在、消息角色是 assistant、Anchor 原文确实出现在该回答中。渲染 offset 与 Markdown 原文不一致时，后端用原文重新定位。
4. Gateway 创建 `branch-thread-*`、空 Checkpoint 和 Branch Record。Record 保存 parent/child 关系、Anchor、创建时的主任务摘要、相关主线上下文快照、上下文策略和预算。
5. 用户在右栏提问时，请求进入 `/{branch_id}/runs/stream`。Gateway 只读取 Child Checkpoint 作为 Branch History，再由 `BranchContextBuilder` 生成隐藏 Context。
6. 现有 `start_run`、Agent、Tool、Sandbox、StreamBridge 和 SSE 在 Child Thread 上运行。结果写 Child Checkpoint，Main Checkpoint 不变。
7. 用户可以切换同一 Main 回答上的多个 Branch。关闭调用 `/close`，只更新 Branch Record 和 Child metadata。

## 为什么一定要 Child Thread

如果只在前端保存一个对话数组，刷新后会丢失，工具调用和 Checkpoint 也无法复用。如果把 Branch 消息追加到 Main Thread，虽然省事，但已经破坏了上下文隔离。

Child Thread 直接复用 DeerFlow 已有的消息历史、Run、Checkpoint 和 SSE 生命周期。Branch Store 不再保存一份 `branch_messages`，所以没有双写一致性问题。我的自定义数据只描述“哪个 Main 消息的哪段文字，关联哪个 Child Thread”。

这里的 Branch 不是 Git Branch，也不是 Sub-Agent。Git Branch 隔离代码版本；Sub-Agent 是 Lead Agent 内部委派；Anchored Branch 是用户可见、可继续多轮交互的独立对话。

## BranchContextBuilder 到底放什么

生产默认策略是 Anchored Context：

```text
Main Task Summary
+ Anchor
+ Relevant Main Context
+ Branch History
+ optional Code Context
+ Current Question
```

Main Task Summary 说明整个主任务在做什么。Anchor 是用户明确选中的原文，不能被摘要替换。Relevant Main Context 是创建分支前与当前任务有关的少量主线消息。Branch History 保证右栏可以多轮追问。Current Question 是本轮用户输入。

当前实现用字符数除以四近似 Token。它不是计费级 tokenizer，但预算规则可复现。Anchor 和 Current Question 是硬保留项；两者连 Prompt 外壳都放不下时直接报错。其余内容超预算时依次删减，并返回 `truncated=true`。Prompt 用标签标明每段来源，Middleware 将它作为不在 UI 显示的 SystemMessage 注入。

## 三种实验策略

Full History 会复制完整主历史。优点是背景最完整；缺点是 Token 高、无关内容多，主对话越长越严重。

Anchor Only 只给 Anchor、Branch History 和当前问题。优点是便宜、隔离最强；缺点是 Anchor 中的代词、前置约束和仓库背景可能无法解释。

Anchored Context 加入主任务摘要和筛选后的相关内容。它不是理论上永远最好，而是需要通过固定任务实验验证的折中。

实验固定同一模型、温度、工具、问题和预算，比较：回答正确率、背景信息遗漏率、无关上下文比例、Prompt Token，以及长 Branch 结束后 Main Thread 是否仍能继续原任务。默认脚本能确定计算 Context 指标；没有真实模型输出时 `answer_correct` 必须为 `null`，不能把关键词命中冒充模型准确率。

## 为什么删除 Decision Capsule 和 Context Ledger

它们解决的是长期记忆审核、冲突和版本治理，会引入 Accept/Edit/Reject、Stale、Conflict、Supersede 等额外状态。当前用户场景只是临时深入回答局部，强迫用户把每个 Branch 整理成 Decision 会增加操作负担，也让项目失去清晰边界。

现在默认 Close 不影响 Main。唯一合理的可选增强是“带总结返回主线”：模型先生成简短总结，用户看见并点击确认后，才把它作为普通消息写进 Main。当前版本没有实现这个可选增强，不能说已经完成。

## 上游能力与个人实现边界

上游 DeerFlow 提供 Thread、Run、Checkpoint、Agent、Tool、SandboxProvider、StreamBridge 和 SSE。我实现的是 Anchor 领域模型、Main/Child 关系、锚点校验、Context Builder、隔离 API、双栏 UI、多 Branch 标记和三策略 Benchmark。Code Change 只用于展示 Branch 内也能调用现有搜索和代码工具，不是 Anchored Branch 的创新点。

## 当前局限

- Branch 索引是 owner 目录下的本机 JSON，不是多机数据库。
- 相关主线上下文目前使用创建时的有限快照，还不是 Embedding/Rerank 检索。
- Token 用字符近似，不是模型 tokenizer。
- Anchor 在原回答被重新生成后不会自动漂移；当前依靠 message ID、offset 和原文校验。
- 轻量 Anchor 标记由右栏同步到消息 DOM，生产级实现更适合提升为共享 React 状态。
- 可选“总结返回主线”尚未实现。

## 面试追问与回答

### Branch 内调用搜索工具为什么不会污染 Main？

因为 `start_run` 接收的是 `record.child_thread_id`，Checkpointer 的 configurable thread_id 也是 Child ID。模型消息、ToolMessage 和运行状态都落入 Child Checkpoint。Context Builder 对 Main 只读创建时快照；close 路由也没有 Main Thread update 调用。

### 为什么不每轮重新读取最新 Main History？

创建时快照让 Branch 的输入边界稳定，避免主线后来变化导致同一个 Branch 的背景悄悄改变。代价是它看不到创建后的新主线信息；如果未来需要同步，应设计显式 Refresh Context，而不是默认串线。

### 为什么 Relevant Main Context 不是向量数据库？

当前数据规模只是一个 Thread 内的少量消息，先用确定性窗口能够降低系统复杂度，也便于解释和测试。只有当对话很长、窗口召回明显不足，并且离线评测证明语义检索提升质量时，Embedding/Rerank 才值得引入。

### 多个 Branch 会互相看到历史吗？

不会。每个 Branch 有独立 child_thread_id。Branch Record 的 list 接口只是让 UI 展示索引，不会把另一个 Child Checkpoint 传进当前 Builder。

### 关闭 Branch 后数据是否删除？

没有物理删除。状态变为 CLOSED，不能再启动新 Run，历史仍可查看。这既避免误删，也让刷新后能解释之前讨论过什么；但它不是长期 Decision Memory。

## 问题 1：为什么做细粒度 Anchored Branch，而不是普通新对话

### 面试官问

这个功能解决什么问题，和现有产品的 Branch 有什么区别？

### 30 秒回答

我不宣称首创 Branch。我的问题是长回答中的局部追问：普通主线追问会污染后续任务，空白新对话又缺背景。我用 message ID、offset 和原文建立细粒度 Anchor，再创建独立 Child Thread，重点研究上下文隔离和背景保留的平衡。

### 详细回答

Anchor 明确指出“针对哪条助手回答的哪段文字”。Child Thread 让局部讨论拥有独立消息、Checkpoint、Run 和工具调用。一个回答能有多个 Branch，用户关闭右栏后仍停留在左侧原回答。默认没有审核、Decision 或回写动作，符合临时深入一个局部问题的操作成本。

### 结合当前 CodeRepair 源码

`message-list-item.tsx` 暴露消息 ID，`anchored-branch-panel.tsx` 捕获 Selection；`anchored_branch.py::_validated_anchor` 校验来源；`_create_child_thread` 和 `AnchoredBranchStore.create` 建立关系。

### 技术选型与替代

只用前端数组最简单，但刷新即丢；复制 Main Thread 最省后端代码，但破坏隔离。复用 DeerFlow Child Thread 能避免重写消息、Checkpoint 和 SSE。

### 边界与追问

当前 Anchor 不会在回答重新生成后自动漂移，Store 也是单机 JSON。这是可演示的上下文工程原型，不是多人协作文档锚点系统。

## 问题 2：怎样证明 Main Thread 与 Branch 真正隔离

### 面试官问

你怎么证明 Branch 中的多轮讨论和工具调用不会写进主线？

### 30 秒回答

Branch Run 的历史读取、Checkpointer thread_id 和 `start_run` 目标全部是 child_thread_id。Main 只在创建时被只读并形成快照。Close 只更新 Child metadata。单测直接断言运行目标是 Child、关闭没有 Main update。

### 详细回答

创建阶段读取 Main 是为了校验 Anchor 和获取有限背景，不会追加消息。运行阶段 `_checkpoint_values` 只读 Child，Branch History 也来自 Child；Agent 和 ToolMessage 随该 Run 写 Child Checkpoint。Store 中的 parent ID 只是关联，不会让 Checkpointer 自动合并。关闭阶段若错误调用 Main update，隔离测试会失败。

### 结合当前 CodeRepair 源码

看 `routers/anchored_branch.py::stream_branch_run`、`close_branch`，再看 `tests/code_change/test_anchored_branch.py::test_branch_run_targets_child_checkpoint_and_child_run` 和 `test_close_branch_updates_child_only`。

### 技术选型与替代

可以在同一 Thread 给消息加 branch_id 过滤，但所有查询、摘要和工具状态都必须记得过滤，漏一次就串线。物理使用不同 Thread ID 的隔离边界更清楚。

### 边界与追问

Branch Store 与 Thread Store 仍是两类持久化，创建过程不是跨库事务；若 Child 创建后索引保存失败，需要补偿清理。当前重点验证运行时不串线，不宣称解决分布式事务。

## 问题 3：Branch Context Builder 为什么比 Full History 或 Anchor Only 合理

### 面试官问

你如何构造 Prompt，又怎样评价策略好坏？

### 30 秒回答

默认组合主任务摘要、Anchor、相关主线上下文、Branch History 和当前问题，并受 Token Budget 控制。实验用相同模型和任务比较 Full History、Anchor Only、Anchored Context 的正确率、背景遗漏、无关比例、Token 和长分支后的主任务恢复能力。

### 详细回答

Full History 背景多但噪声和成本高；Anchor Only 隔离强但容易缺前置约束；Anchored Context 是可验证的折中。Anchor 和当前问题硬保留，可选内容超预算时删除并标记 truncated。Branch History 三组都保留，否则无法公平测试多轮 Branch。没有真实模型输出时只报告 Context 指标，回答正确率保持 null。

### 结合当前 CodeRepair 源码

`anchored_branch/context.py::BranchContextBuilder.build` 实现三策略和预算；`middleware.py` 注入隐藏 Context；`benchmark.py::run_benchmark` 输出同一 case 下的三组指标。

### 技术选型与替代

当前使用确定性有限快照，便于解释。只有评测证明窗口召回不足时才引入 Embedding/Rerank；只有字符估算误差影响预算时才接模型 tokenizer。

### 边界与追问

默认 Benchmark 不是在线模型评测。回答正确率需要保存真实输出和人工或规则金标准；长分支后恢复能力也需要单独任务集，不能从 Prompt Token 推断。
