# 05 Agent、Tool、Skill、Middleware 与 Sub-Agent

这些词经常一起出现，但职责完全不同。先用“修复一个接口”来理解。

## Agent

Agent 是“模型 + 可调用工具 + 状态 + 运行规则”的组合。普通聊天模型只输出文字；Agent 可以根据上下文决定先搜索代码、再读文件、最后提交 Patch。

它不是一个永远正确的自动程序。模型决定下一步，因此输出存在不确定性。系统必须限制它能调用的 Tool，并对最终结果做确定性校验。

Code Change Agent 由 `create_code_change_agent` 创建，底层调用上游
`create_deerflow_agent`。它使用专门的 system prompt，并采用最小 Tool 集合。

## Tool

Tool 是带名称、参数 Schema 和返回值的可执行函数。例如：

```text
code_change_search(query)
code_change_read_file(path, start_line, end_line)
code_change_submit_patch(patch_text, rationale)
```

模型不会直接调用任意 Python 函数，只能从暴露给它的 Tool 中选择。Tool 是最直接的权限边界。

为什么不用一个万能 `bash` Tool？因为 bash 可以读密钥、联网、删文件和执行任意程序。代码变更的生成阶段只需读上下文和提交候选，没理由授予写入与执行权限。

## Skill

Skill 是一组可复用的领域说明、流程和允许工具约束。它可以告诉 Agent 如何做代码审查、如何准备 PR，但 Skill 本身不等于执行环境，也不天然提供安全隔离。

可以把 Skill 理解为“可装载的工作方法”，Tool 理解为“真正能产生动作的函数”。只写一份 Markdown 说“请安全修改代码”不能替代路径校验和沙箱。

当前 Code Change 的关键能力在 Python 控制面和请求级 Tool 中。若把它注册为通用 Lead Agent Skill，仍要保留这些后端校验，不能仅靠 prompt。

## Middleware

Middleware 包在模型或 Tool 调用前后，用来注入上下文、限制循环、处理错误、汇总长对话、挂载 Sandbox 等。它解决横切问题，类似 Web 服务里的认证、日志 Middleware。

上游 `create_deerflow_agent` 可以根据 `RuntimeFeatures` 自动组装 Middleware。Code Change Patch Agent 采用最小链路，不自动挂载通用 Sandbox/bash 工具，避免权限意外扩大。执行隔离由后面的 Worker 负责。

## Sub-Agent

Sub-Agent 是主 Agent 委派出去的另一个 Agent，适合并行研究多个独立问题。它不是普通函数，也不是 Worker。

- Sub-Agent 仍然使用模型，会消耗 token，结果也有不确定性。
- Worker 是确定性任务执行进程，按照状态机应用 Patch 和运行测试。
- 两者不能因为名字里都有“任务”就混为一谈。

当前 Code Change 的单 Patch 纵向链路不需要 Sub-Agent。为了展示技术栈而强行并行多个 Agent，会增加成本和调试难度，却不提高安全性。

## Thread、Run、Task 的区别

| 名称 | 所属 | 含义 |
| --- | --- | --- |
| Thread | DeerFlow/LangGraph | 一段可持续的 Agent 对话上下文 |
| Run | DeerFlow/LangGraph | Thread 内一次实际模型运行 |
| Task | Code Change | 一次需要排队、执行、测试和审批的代码变更业务对象 |

完整平台可以让 Task 关联 Agent Thread/Run，方便把 Tool 轨迹与后续测试报告串起来。Task 不能直接用 Run 替代，因为 Agent 结束后，Patch 测试、重试和人工审批仍会继续。

当前 Code Change 的字段名是 `agent_thread_id` 和 `agent_run_id`。它们由 Task 创建时生成，并作为 `graph.invoke` 的 configurable/metadata 关联标识。当前 Patch Agent 没有配置 checkpointer，也没有调用 Gateway Thread/Run API，因此这两个字段不是已经持久化的 DeerFlow Thread/Run 数据库记录。

## RAG 在这里是什么

RAG 的核心是先检索外部资料，再把相关内容交给模型。当前实现是文件级轻量检索：扫描允许后缀文件，按路径、摘要和内容词项打分，返回 Top-K。它没有向量数据库、Embedding 或 Rerank。

因此正确说法是“轻量代码上下文检索”，不是“完整企业级 RAG”。以后仓库更大时，才需要 symbol 索引、chunk、BM25/Embedding 混合召回与 rerank。

## 面试快速区分

> Agent 决定下一步；Tool 执行一个受控动作；Skill 提供领域工作方法；Middleware 在调用链前后处理横切能力；Sub-Agent 是另一个可委派的模型执行单元；Worker 则是确定性后台任务进程。我的 Code Change 链路故意只给 Patch Agent 三个 Tool，把写入和测试放在 Worker 中。

## 本章代码阅读任务

阅读顺序：从三个 Tool 开始，再看 Agent factory、测试与 Task 关联字段。

1. 打开 `backend/packages/harness/deerflow/code_change/agent_patch.py`，先看 `SYSTEM_PROMPT`，再看 `build_code_change_tools` 内三个 `@tool` 函数。对每个 Tool 记录参数、返回值和副作用。
2. 看 `create_code_change_agent` 调用 `create_deerflow_agent` 的实参，再回到 `backend/packages/harness/deerflow/agents/factory.py` 的 `middleware is not None` 分支，理解为何不按 RuntimeFeatures 自动装 Middleware。
3. 打开 `backend/tests/code_change/test_agent_patch.py`，按越界、单次 submit、真实 Agent 图、未 submit 失败四个测试阅读。每个测试写一句合同。
4. 打开 `models.py::Task`，找到 patch_mode、agent_thread_id、agent_run_id、agent_rationale、agent_changed_files，理解业务 Task 如何保存 Agent 关联。

看到什么程度：随机说 Agent、Tool、Skill、Middleware、Sub-Agent、Worker、Thread、Run、Task 中任意一个词，能用一句定义和项目例子回答。

暂不要求：不研究 LangChain `@tool` decorator、fake model 内部和上游 Thread 数据库 Schema，也不背全部 Middleware。

验收动作：把九个概念写成卡片，正面是名称，背面是定义、项目例子和一个容易混淆的对象，随机抽查。

## 本章自测

1. Agent 和普通模型调用的差别是什么？
2. Tool 为什么是权限边界？
3. Skill 能否替代服务端安全校验？
4. Sub-Agent 和 Worker 为什么不是一回事？
5. Thread、Run 和 Task 怎样关联？
6. 当前检索为什么只能叫轻量代码上下文检索？

## 参考答案

1. 普通模型调用主要返回文本；Agent 在有状态循环中决定是否调用 Tool，并把 Tool 结果继续交给模型。它仍有概率性，所以候选需要确定性校验。
2. 模型只能调用绑定的 Tool 和参数 Schema。Patch Agent 没有 bash、write_file 或 git push，因此生成阶段不能通过正常能力直接执行这些动作。
3. 不能。Skill 是工作说明，模型可能不遵守；路径 resolve、Patch 大小、owner 和命令 profile 必须由代码强制检查。
4. Sub-Agent 仍由模型推理，适合委派研究；Worker 按状态机执行固定步骤。前者有 token 与不确定输出，后者可重试、可审计并检查领取权。
5. Thread 是 Agent 对话上下文，Run 是其中一次模型运行，Task 是完整代码变更生命周期。当前 Task 保存自生成的 Agent 关联标识，但未建立 Gateway 持久化 Thread/Run 记录；Agent 结束后 Task 仍继续测试、审批和重试。
6. 它按文件路径、摘要和内容词项打分，没有向量数据库、Embedding、chunk 索引或 reranker。功能真实但范围有限。
