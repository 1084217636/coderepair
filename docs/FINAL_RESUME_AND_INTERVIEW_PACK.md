# 项目二简历与面试口径

## 项目名称与定位

项目名称：CodeOps Agent，基于 DeerFlow 的代码智能协作平台。

技术栈：Python、DeerFlow 2.0、LangGraph、LLM Agent、轻量 Hybrid Code Retrieval、Tool Calling、FastAPI、Local-copy Workspace、Git Diff、Next.js。

项目不是一个普通聊天框，也不是只研究对话分支。它面向真实代码仓任务，主体链路如下：

```text
Requirement
→ Repository Retrieval
→ Agent / Tool Calling
→ Candidate Patch
→ Isolated Workspace
→ Test
→ Diff / Report
```

Anchored Branch 是个人二开中最有辨识度的功能。它解决长回答中局部追问污染主线程的问题，但不是项目的全部。

## 简历可直接使用的版本

```text
CodeOps Agent｜基于 DeerFlow 的代码智能协作平台
技术栈：Python、DeerFlow 2.0、LangGraph、LLM Agent、Code Retrieval、Tool Calling、FastAPI、Workspace、Git Diff

• 基于 DeerFlow 2.0 二次开发 Coding Agent，打通 Requirement → Retrieval → Agent/Tool → Patch → Workspace → Test → Diff/Report 链路；Agent 只拥有 search、bounded read 和 typed patch submit 权限，确定性 Worker 负责 Patch 校验、应用和测试。12 个真实模型小型代码任务中，最终测试通过 10 个，通过率 83.33%。

• 实现轻量 Hybrid Code Retrieval，将路径/代码词法命中、Python/Go/TypeScript/Java 符号命中和可配置 Embedding 语义分数组合，并返回可解释的召回原因；Context Builder 按 Token Budget 选择 Top-K 代码块。12 个任务的目标文件 Recall@5 为 100%，本次无 Embedding 配置的评测走 lexical + symbol fallback。

• 设计 Anchored Branch 局部探索机制，从主回答或代码片段创建独立 Child Thread，按 Main Task Summary + Anchor + Relevant Context/Retrieved Code + Branch History 构造上下文，分支消息和工具调用不写入 Main Thread。12 个同模型案例中，Anchored Context 正确率为 100%，平均 Prompt Token 为 234.67；相较 Full History 保持相同正确率，Prompt Token 降低 10.32%。
```

这些数字来自 2026-08-28 的单次固定任务集运行。它们适合说明本次实验，不代表线上长期成功率。模型、Prompt、任务集或运行次数变化后必须重新测量。

## 30 秒介绍

```text
这是我基于 DeerFlow 2.0 二次开发的 CodeOps Agent。用户提交自然语言代码需求后，系统先从登记仓库检索相关代码，再由受限 Agent 通过搜索、读文件和 typed submit Tool 生成候选 Patch。Worker 在固定 Git commit 的独立 Workspace 中校验 Patch、运行测试并输出 Diff 和报告。我还实现了 Anchored Branch，让用户从长回答或代码片段建立独立分支，局部追问不会写入主线程。DeerFlow 的 Agent Runtime、Thread、Run、Tool、Sandbox 和 SSE 是上游能力，我的工作集中在代码变更链路、Hybrid Retrieval 和 Anchored Branch。
```

## 2 分钟介绍

```text
我做的是一个基于 DeerFlow 的代码智能协作平台，主体仍然是 Coding Agent，而不是单独做一个分支聊天功能。

一次任务从自然语言需求和已登记代码仓开始。仓库扫描器先过滤二进制、构建产物和超限文件，再把源码切成代码块。检索层组合三类信号：路径和代码文本的词法命中、函数/类型/方法等 Symbol 命中，以及可选的 Embedding 语义相似度。它对分数做融合，返回 Top-K 代码块和召回理由；Context Builder 再按 Token Budget 组织 Agent 的初始上下文，不复制整个仓库。

Agent 复用 DeerFlow 的 create_deerflow_agent，但没有直接使用全权限通用 Agent。我只开放 search、bounded read 和 typed patch submit 三个 Tool。模型只能提出 unified diff，不能直接改登记仓库或执行任意 shell。服务端在固定 source commit 上准备独立 Workspace，执行路径检查、git apply --check、Patch 应用和白名单测试，最后生成 Diff、日志和报告。第一次 Diff 格式无效时，系统会把真实校验错误反馈给模型，只允许修正一次，避免无限重试。

Anchored Branch 解决另一个问题：长回答里往往有多个局部问题，全部在线性主线程追问会让上下文越来越长。用户可以选中一句话、一段解释或代码片段创建 Child Thread。Branch Prompt 由主任务摘要、Anchor、相关主线内容或检索代码、Branch History 和当前问题组成。Branch 关闭后 Main Thread 不变，同一条回答也能创建多个 Branch。

我用两套真实模型评测收口。Coding Agent 的 12 个小型代码任务通过 10 个；Anchored Context 的 12 个案例中，Full History 和 Anchored Context 都是 100% 正确，Anchored Context 的平均 Prompt Token 少 10.32%。这只是固定任务集的单次结果，所以我会同时说明样本量和当前限制。
```

## 面试追问

### 为什么选 DeerFlow，而不是自己写 ReAct 循环？

最小 ReAct 循环不难，完整系统还需要 Thread、Run、Checkpoint、Tool 调度、流式事件和前端交互。DeerFlow 已经提供这些运行时能力。我选择在现有框架内找扩展点，能把时间放在代码仓上下文、Patch 安全边界和分支隔离上，也更接近接手公司开源底座做二次开发的工作。

### Code Retrieval 为什么叫 lightweight hybrid？

它不是只有关键词，也没有引入向量数据库和复杂 Reranker。词法信号负责精确路径、标识符和代码文本；Symbol 信号补充函数、类、类型和方法；Embedding 配置存在时提供语义相似度。三类分数融合后仍保留 reason，方便解释某段代码为什么被召回。Embedding 不可用时，系统明确回退到 lexical + symbol，主链路仍能运行。

### 为什么不把整个仓库交给模型？

大仓通常超出上下文窗口，即使放得下也会增加 Token、延迟和无关噪声。项目采用 coarse-to-fine 方式：先检索候选代码块，再让 Agent 通过 bounded read 获取准确上下文。Context Builder 负责预算控制，Anchor 和当前问题等必要内容优先保留。

### Agent 为什么不能直接写文件？

模型生成具有概率性，文件修改和命令执行有副作用。当前 Agent 只负责候选 Patch，Worker 负责确定性校验和测试。这样可以明确区分"模型认为可行"和"程序实际验证通过"，也能留下失败阶段、测试日志和 Diff。

### 83.33% 是怎样测出来的？

评测包含 12 个自动验收的小型 Python 仓库任务，覆盖 bug fix、边界条件、参数检查、小功能和源代码加测试修改。每条任务都实际经过 Retrieval、Agent、Tool、Patch、Workspace 和 unittest。10 条最终测试通过，分母是 12。剩余两条在一次修正后仍生成 corrupt unified diff，因此计为失败。

### Recall@5 为 100% 能说明什么？

它只说明 12 个任务标注的目标文件都进入检索 Top 5，不能说明排序永远正确，也不能单独证明 Patch 正确。本次环境没有配置 Embedding，因此这个结果对应 lexical + symbol fallback。要比较 Semantic Retrieval 的收益，需要固定任务集，分别运行开关 Embedding 的消融实验。

### Anchored Branch 与普通新对话有什么区别？

普通新对话没有精确指出来自主回答的哪一段。Anchored Branch 保存 source message ID、文本 offset、Anchor 原文和可选代码引用，并创建独立 Child Thread。它既保留局部定位，又让 Branch History、搜索和工具调用不进入 Main Thread。

### 三种 Context 策略的结果怎样解释？

同一个模型、温度和 12 个案例下，Full History 为 100% / 261.67 tokens，Anchor Only 为 83.33% / 211.42 tokens，Anchored Context 为 100% / 234.67 tokens。Anchor Only 最省 Token，但会遗漏前置约束；Full History 信息完整但包含更多无关历史；Anchored Context 在这组案例中保留正确率，并比 Full History 少 10.32% Prompt Token。样本较小，不能宣称它对所有任务都最好。

## 上游能力、个人二开与边界

| 分类 | 内容 |
| --- | --- |
| DeerFlow 上游 | Agent Factory、Thread、Run、Checkpoint、Tool 抽象、Sandbox 接口、Middleware、SSE |
| 个人二开 | Code Change 控制面、受限 Patch Agent、Hybrid Code Retrieval、Token Budget Context Builder、Workspace/Test 链路、Anchored Branch 领域模型与双栏交互、两组真实评测 |
| 当前边界 | 文件型 Store/Queue、单机 POSIX claim/lease、local-copy Workspace、没有真实 GitHub PR、没有生产级容器隔离、Embedding 需要显式配置 |

不能写"自研 DeerFlow"、"生产级分布式 Worker"、"自动创建并合并 PR"、"容器级安全 Sandbox"或"线上成功率 83.33%"。
