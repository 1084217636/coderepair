# 04 受限 Patch Agent 与代码检索

## 问题 1：external 和 agent 两种 Patch 模式有什么区别

### 面试官问

为什么系统同时保留外部 Patch 和 Agent Patch，两条链分别怎么走？

### 30 秒回答

external 模式接收已经准备好的 unified diff，状态经过 PATCH_RECEIVED 和 VALIDATING_PATCH；agent 模式不给外部 Patch，Worker 在固定 commit 的 Workspace 中启动受限 Agent，状态进入 GENERATING_PATCH，Agent 通过 search、read 和 typed submit 生成候选 diff。两条路径从 VALIDATING_PATCH 开始汇合，共用路径校验、应用、测试、报告和人工审核。external 适合确定性回归和人工提供补丁，agent 才代表真实模型生成。

### 详细回答

保留两种模式主要有两个原因。

第一，确定性测试和模型评测必须分开。external 模式输入 Patch 固定，失败可以归因到 Workspace、Patch 校验、测试或状态机。Agent 模式还包含模型、Prompt、检索和 Tool Calling，不稳定因素更多。把两者混在一起，系统故障和模型失败很难区分。

第二，真实团队中候选 Patch 不一定来自模型，也可能来自开发者、其他扫描器或外部 Agent。后半段验证链应该复用，不必绑定某一个生成器。

状态名称也要真实。external 模式不能进入 GENERATING_PATCH，因为系统没有生成任何 Patch。Agent 模式生成成功后直接进入 VALIDATING_PATCH。生成失败设置 `AGENT_GENERATION_FAILED`。

无论哪种来源，候选 Patch 都不可信。来源不同不应改变执行安全规则。

### 结合当前 CodeRepair 源码

- `models.py::PatchMode` 定义 `external` 和 `agent`。
- `worker.py::create_task` 拒绝 Agent 模式携带外部 Patch，也拒绝 external 模式携带 model name。
- `worker.py::execute_task` 在 RETRIEVING_CONTEXT 后按模式分支。
- external 没有 Patch 时以 `PATCH_REQUIRED` 失败，之后必须通过 resubmit 提交。
- agent 调 `_generate_agent_patch`，保存 rationale、changed files、final message 和关联 ID。
- 两者都在 `TaskStatus.VALIDATING_PATCH` 后调用 `apply_patch_text`。

### 技术选型与替代

也可以只保留 Agent 模式，但这样很难做快速、无网络、可重复的执行面回归。也可以把生成器抽象成多个 Provider，支持模型、规则引擎和外部 API。当前 `PatchGenerator = Callable[[Task, str], AgentPatchResult]` 已经为测试替身保留了接口。

### 边界与追问

固定 20 case 全部走 external 模式。它能证明执行面处理预期 Patch 的能力，不能证明 Agent 自动生成 Patch 的成功率。

## 问题 2：当前代码检索怎么实现，效果有什么限制

### 面试官问

Agent 怎样从仓库里找到相关文件？用了向量数据库吗？

### 30 秒回答

当前没有向量数据库。系统先扫描代码文件，再把 requirement 切成英文标识符和中文二、三字片段，对文件路径、摘要和内容分别计分，路径命中权重 3，摘要 2，内容 1，排序后返回前几个 snippet。这个方案本地可运行、结果可解释，但语义召回有限，适合作为 MVP。后续可以加入 BM25、Symbol 索引和 Embedding，做混合检索。

### 详细回答

检索的输入是仓库路径、需求文本和扫描得到的 CodeFile 列表。当前扫描按路径排序，过滤依赖、构建产物和不支持的后缀，最多收集 500 个文件。

`tokenize` 使用正则提取英文标识符，并从连续中文中生成二元和三元片段。对每个文件，检索器计算三类命中：term 出现在 path 得 3 分，出现在 summary 得 2 分，出现在完整文本得 1 分。如果一个 Go 或 Python 文件完全没有命中，仍给 1 分作为弱兜底。最后按分数降序、路径升序排序。

返回的 `RetrievedContext` 包括 path、score、reason 和前 800 字符 snippet。reason 会明确写出 path、summary、content 各自得分，方便调试。

这个算法的问题也很明显。它按 term 是否出现计分，不考虑出现次数和文档长度；英文同义词和跨语言语义无法匹配；读取每个文件全文会带来 O(文件总量) 的 I/O；snippet 固定取文件开头，命中位置可能在后面；超过 500 个受支持文件的仓库会按路径顺序截断。项目里必须如实说这些限制。

### 结合当前 CodeRepair 源码

- `repo_scanner.py::scan_repo` 生成 CodeFile 列表并过滤不需要的目录和文件。
- `context_retriever.py::tokenize` 生成检索 term。
- `retrieve_context` 计算三部分分数并返回 Top K。
- Patch Agent 的 `code_change_search` 默认 `limit=8`。
- Worker 在执行生成前也会保存一次 `task.contexts`，用于报告和审计。

### 技术选型与替代

小仓库可以使用 `ripgrep` 或 BM25，速度快且可解释。代码检索还适合建立 symbol、import、调用关系索引。Embedding 能处理语义相似，但要考虑向量模型、切块、增量更新、权限过滤和费用。

我倾向于混合检索：路径和 Symbol 使用词法检索保证精确命中，代码块 Embedding 提供语义召回，再用 reranker 排序。离线评测应使用标注过的相关文件集合，计算 Recall@K，而不是凭感觉说效果好。

### 边界与追问

当前代码没有 Recall@5 数据，也没有向量库。不能在简历上写 RAG 检索准确率。如果面试官问 RAG，可以说当前是可解释词法检索，理解 RAG 演进方案，但没有把未实现方案写成现状。

## 问题 3：为什么 Agent 不能直接写文件和跑 shell

### 面试官问

不给写文件和 shell，Agent 能力不是很弱吗？为什么这样设计？

### 30 秒回答

这是有意收紧权限。模型负责理解和提出候选，Worker 负责执行。Agent 只有搜索、限量读取和提交 Patch 三个 Tool，不能直接修改文件、执行任意命令或接触 Git 元数据。这样可以记录完整提案，把路径校验、应用和测试放到普通程序中复现。代价是自主性较弱，但个人项目更容易证明安全边界和故障归因。

### 详细回答

通用 Coding Agent 常拿到 shell，可以运行 `rg`、编辑文件、执行测试和 Git 命令。这种模式效率高，但权限面也大：Prompt Injection 可能诱导读取 Secret，模型可能执行网络下载、修改 `.git`、删除目录，测试命令还可能启动子进程长期运行。

CodeRepair 把能力拆成最小集合。

搜索 Tool 只返回索引内结果。读文件 Tool 要求仓库相对路径，拒绝绝对路径和 `..`，并限制行数和字符数。提交 Tool 只收 unified diff 与 rationale，只允许一次，并在提交时提取和检查变更路径。

Agent 完成后没有任何文件被修改。Worker 把 Patch 写入任务 Artifact，再在 Workspace 中执行 `git apply --check` 和测试。即使模型最终消息说已经测试通过，也不会改变 Task 的测试状态。

### 结合当前 CodeRepair 源码

- `agent_patch.py::SYSTEM_PROMPT` 明确禁止声称已应用、测试、提交或合并。
- `_safe_repo_file` 防止读取逃逸仓库。
- `build_code_change_tools` 只返回三个 Tool。
- `code_change_submit_patch` 检查 256 KB 上限、重复提交、路径和 `.git`。
- `create_code_change_agent(... middleware=[])` 不加载完整通用 Agent 中间件。
- 真正修改 Workspace 的代码在 `patcher.py`，不在 Agent Tool 中。

### 技术选型与替代

如果公司内部有成熟容器 Sandbox、网络隔离、Secret 注入策略和审计，可以逐步开放受限 shell。例如只允许 `rg`、`go test` 和指定编辑工具，命令仍由 Policy 解析，不交给 shell 字符串执行。

另一种方案是让 Agent 输出 AST edit 或结构化文件操作。它比 unified diff 更容易校验某些语言结构，但跨语言通用性差。unified diff 能直接审阅，也能用 Git 工具链验证。

### 边界与追问

最小 Tool 集降低风险，但不等于绝对安全。被读取的源码本身可能含恶意 Prompt；模型仍可能生成危险业务代码；Workspace 的测试进程仍需要更强的 OS 隔离。

## 问题 4：模型幻觉在这个项目里怎么处理

### 面试官问

模型生成了不存在的文件、错误 Patch 或者没有调用 Tool，系统怎么办？

### 30 秒回答

系统把模型输出当候选，不尝试相信或掩盖错误。读取不存在文件时 Tool 返回失败；没有调用 typed submit 时 Agent 阶段硬失败；Patch 路径越界会被拒绝；上下文不匹配会在 `git apply --check` 失败；语义错误会在测试阶段失败。Task 保存明确 error code、日志和状态，允许在规则范围内重试或由人工提交修订 Patch。

### 详细回答

不同错误要在最靠近源头的位置被识别。

文件幻觉发生在读取阶段。`_safe_repo_file` 检查路径必须存在且属于已扫描代码集合，失败不会返回伪造内容。

输出协议错误发生在 Agent 完成阶段。系统不解析 assistant 最终文本，只检查 `PatchCapture`。没有调用 `code_change_submit_patch` 就抛出异常，Worker 设置 `AGENT_GENERATION_FAILED`。

结构错误发生在 Patch 校验阶段。`extract_changed_files` 必须提取到路径，`validate_patch_paths` 拒绝绝对路径、父目录和 `.git`。diff 上下文与固定 commit 不匹配时，`git apply --check` 返回非零，状态变成 FAILED，错误码是 `PATCH_APPLY_FAILED`。

语义错误通常由测试发现。测试返回非零时，错误码是 `TEST_FAILED`。即使所有测试通过，任务也只到 HANDOFF_READY，因为测试覆盖可能不完整，还需要人工检查 diff。

### 结合当前 CodeRepair 源码

- `agent_patch.py::generate_patch_with_agent` 检查 typed submission。
- `patcher.py::validate_patch_paths` 和 `run_git_apply(check=True)` 处理结构安全。
- `worker.py::execute_task` 为生成、Patch、测试和未提供 Patch 设置不同 error code。
- `worker.py::retry_task` 只允许 FAILED 且未耗尽 attempt 的任务重试。
- `worker.py::resubmit_patch` 处理 PATCH_REQUIRED 或 CHANGES_REQUESTED，并清理旧执行结果。

### 技术选型与替代

可以在失败后自动把日志反馈给 Agent 再生成一次 Patch，但需要严格限制次数、Token 和可见日志，防止循环放大成本。当前代码没有实现在线自动修复回路，选择把失败事实保存清楚，再由 retry 或人工 resubmit 驱动。

### 边界与追问

不能说测试通过就消除了幻觉。测试只能覆盖被测试的行为。人工审核、静态分析、更多测试和生产发布策略仍然需要存在。
