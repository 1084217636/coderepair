# 11 受限 Patch Agent 的完整链路

Patch Agent 的职责只有“理解需求并提出一个候选 unified diff”。它不能应用 Patch、运行测试、提交 Git 或创建 PR。

```text
requirement + pinned workspace
→ code_change_search(query)
→ code_change_read_file(path, start_line, end_line)
→ code_change_submit_patch(patch_text, rationale)
→ AgentPatchResult
→ deterministic Worker
```

`generate_patch_with_agent` 通过 DeerFlow Agent factory 建图，但只注册三个请求级 Tool。提交 Tool 验证大小、路径与 `.git` 元数据，只接受一次提交。Agent 如果在自然语言里贴出 diff 而没有调用 typed Tool，任务失败关闭。

## 为什么是混合架构

理解需求、选择文件和设计修改属于概率性工作，适合模型；路径授权、Patch 语法、文件修改、命令执行和状态迁移属于确定性工作，应交给普通代码。这比“让通用 Agent 拿 shell 自己完成一切”更容易审计、测试和控制权限。

`agent_thread_id` 与 `agent_run_id` 是 Task 关联标识。当前 Agent 图没有 Gateway 持久化 Thread/Run，也没有 Checkpointer，因此异常后由 Task 重试，而不是从 Agent 中间节点恢复。

## 本章代码阅读任务

- 阅读顺序：`agent_patch.py` 的 `PatchCapture`、`build_code_change_tools`、`create_code_change_agent`、`generate_patch_with_agent` → `worker.py` 的 `_generate_agent_patch` 与 `execute_task`。
- 看到什么程度：能从 `patch_mode=agent` 追到 typed submit，再指出与 external 模式的汇合点。
- 暂不要求：不追具体模型 provider SDK。
- 验收动作：运行 `test_real_deerflow_agent_graph_submits_candidate_patch` 和“未调用 submit Tool”失败测试，解释 ToolMessage 序列。

## 本章自测

1. 为什么 prompt 禁止写文件仍不够？
2. Agent 模式与 external 模式在哪里汇合？
3. 如何给 Patch Agent 增加可观测性？

## 参考答案

1. Prompt 只是软约束；真正权限来自只注册 search/read/submit Tool，并由 Worker 独占应用和测试能力。
2. 两者都进入 `VALIDATING_PATCH`，之后共用 Workspace、Patcher、Test、Report 与 Review。
3. 记录模型名、task/thread/run 关联、每次 Tool 名称与耗时、检索文件、读取范围、提交次数、token 和失败分类，同时避免记录 Secret 或完整敏感源码。
