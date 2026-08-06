# 13 报告、审计、人工审批与 PR Handoff

## 为什么机器结果还要变成人能读的报告

Task JSON 适合程序读取，但评审人需要快速判断改了什么、测试是否可信、有哪些风险。报告把分散的 PatchResult、TestResult、状态步骤和路径汇总成 Markdown，同时保留结构化 audit JSON 供平台查询。

## 报告至少应包含什么

- task_id、project_id、owner 和 source commit。
- 原始 requirement。
- Agent thread/run 与候选理由。
- changed files、增删行数。
- `git apply --check` 和 apply 结果。
- 实际 test profile、退出码、耗时、超时和日志截断。
- Workspace/Sandbox 类型。
- 完整状态步骤和错误。
- 已知风险、回滚建议和人工检查项。

为什么记录 profile 而不是只写“测试通过”？因为不同 profile 覆盖范围不同，评审人必须知道到底跑了什么。

## HANDOFF_READY 的准确含义

进入这个状态说明：

1. 有真实候选 Patch。
2. Patch 在固定源码基线的独立 Workspace 可应用。
3. 服务端批准的测试模板退出码为 0。
4. 报告和 handoff 材料已写出。

它不说明业务一定正确，也不说明 GitHub 已创建 PR。

## 人工审批怎样授权

审批接口只能操作当前 owner 的 Task，并且 Task 必须是 `HANDOFF_READY`。决定包括：

- `approve`：记录 reviewer、时间和 note，进入 `APPROVED`。
- `request_changes`：记录原因，进入 `CHANGES_REQUESTED`，等待新 attempt。

审批文件是证据，不应由 Agent 自己写。模型可以解释 Patch，但不能扮演批准者。

更完整的公司流程会区分任务提交者和审批者，使用 RBAC 或代码所有者规则，防止自己提交、自己批准。

## PR handoff 和真实 PR 的区别

当前 `pr_handoff.py` 生成说明和可执行脚本，帮助人从已验证基线创建分支和 PR。它没有调用 GitHub API，也没有保存 PR number/URL。

因此简历应写“生成 PR handoff/草稿材料”，不能写“自动创建 Draft PR”。真实实现需要：

```text
APPROVED
→ GitHub App installation token
→ 从 source_commit 创建分支
→ 写入同一 Patch
→ push
→ Create Pull Request API
→ 收到 number + html_url
→ 幂等保存
→ PR_CREATED
```

## 为什么外部副作用要幂等

GitHub 请求成功后，Worker 可能在保存 URL 前崩溃。重试时如果再次创建，就会出现两个 PR。应使用稳定 branch 名或 idempotency key，先查询是否已有 task_id 对应 PR，再决定创建。

这与消息系统“发送成功但提交位点前宕机”是同一类问题：本地状态和外部系统之间没有原子事务，只能通过幂等、查询与补偿收敛。

## request changes 的闭环

评审驳回后，新 Patch 不能覆盖旧证据。系统至少要：

- 增加 attempt_count。
- 保留旧 Patch/test/report。
- 记录 review note。
- 接受修订 Patch或再次 Agent 生成。
- 重新走校验与测试。

当前实现会增加 `attempt_count` 并重新入队，但复用同一 Task 目录和同名 artifact，旧 Patch、Workspace、测试日志与报告可能被覆盖。面试时必须把它说成当前限制。完整方案按 attempt 建子目录，并在数据库保存每次 artifact URI。

## 面试回答

> 我的终态不是自动合并，而是 HANDOFF_READY。它要求 Patch 真正可应用、固定测试模板通过且报告生成；当前 owner 再 approve 或 request changes。现版本生成 PR handoff 脚本，没有调用 GitHub，所以不声称已创建 PR。真实接 GitHub 时还要处理 token 权限和“远端成功、本地保存前宕机”的幂等问题。

## 本章代码阅读任务

阅读顺序：先看报告字段，再看 handoff 命令，最后看审批和修订重入。

1. 打开 `backend/packages/harness/deerflow/code_change/report_writer.py`，按 `write_reports`、`render_task_report` 的顺序读。把报告中的 Task、Agent、Patch、Test、PR Handoff、Error 六部分分别对应到 `Task` 字段。暂不背 Markdown 拼接代码。
2. 打开 `backend/packages/harness/deerflow/code_change/pr_handoff.py`，先看 `PRHandoff`，再看 `write_pr_handoff`、`build_commands`、`render_script`。确认函数只写 `pr_handoff.json` 和 `create_draft_pr.sh`，并没有在 Python 中执行命令或接收 GitHub PR number/URL。
3. 打开 `backend/packages/harness/deerflow/code_change/review.py` 的 `review_task`。记录允许状态、decision 白名单、reviewer 校验、`human_review.json` 字段和两个目标状态。确认当前 reviewer 就是 owner，尚未实现提交者与审批者分离。
4. 打开 `backend/packages/harness/deerflow/code_change/worker.py` 的 `resubmit_patch`。跟清可接受状态、attempt 上限、哪些结果字段被清空、怎样重新 `QUEUED`。再确认 artifact 仍使用原 Task 目录。
5. 对照 `backend/tests/code_change/test_pr_handoff.py` 和 `test_worker.py` 中 request changes 用例。只看脚本未自动执行的证据和第二次 attempt 的断言。

看到什么程度：能拿一份 Task 报告逐项解释证据来源，并能指出 `HANDOFF_READY`、`APPROVED`、手动执行 handoff 脚本、未来 `PR_CREATED` 四者的区别。

暂不要求：不执行脚本向真实远端 push，也不实现 GitHub App、CODEOWNERS 或 attempt 表；先读懂材料与状态边界。

验收动作：拿一个成功 Task，对照 task.json、task_report.md、pr_handoff.json、human_review.json，逐项说出谁生成、何时生成、能证明什么。

## 本章自测

1. 为什么 Task JSON 之外还要 Markdown 报告？
2. `HANDOFF_READY` 准确证明了什么？
3. 当前 handoff 与真实 GitHub PR 有什么区别？
4. 为什么 PR 创建需要幂等？
5. 当前人工审批有哪些授权边界？
6. request changes 当前闭环还缺什么证据保留？

## 参考答案

1. JSON 适合程序读取，评审人需要快速看到需求、基线、changed files、测试命令与退出码、风险和时间线。Markdown 是人读汇总，audit JSON 仍保留结构化事实。
2. 它证明候选 Patch 存在、在固定基线 Workspace 可应用、服务端测试模板退出码为 0，并且 handoff 材料与报告已生成。它不证明业务完全正确，也不代表 PR 已创建。
3. 当前代码只生成包含命令的 JSON 与 shell 脚本，等待人审后手动运行。Python 流程没有调用 GitHub API，也没有保存 number 或 html_url，所以状态不进入 `PR_CREATED`。
4. GitHub 可能已创建 PR，但平台在保存 URL 前宕机。重试若直接再次创建会重复，因此要用稳定分支或 task marker 先查询，再补写已有 PR 信息。
5. API 只允许当前 owner 的 `HANDOFF_READY` Task，并记录 reviewer、时间和 note。当前没有把提交者与审批者分成不同 RBAC 角色，生产方案还需要 CODEOWNERS 或 reviewer 角色。
6. 当前 attempt_count 会增加，但修订仍复用同一 Task 目录，同名 Patch、日志、Workspace 和报告可能覆盖旧版本。完整方案应有 `task_attempts` 和分 attempt artifact。
