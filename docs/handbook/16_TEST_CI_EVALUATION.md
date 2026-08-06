# 16 测试、GitHub Actions 与评测

## 三类验证不要混在一起

### 单元测试

验证一个函数或类的契约，例如：

- 状态迁移是否合法。
- Patch 路径是否拒绝 `..`。
- tokenizer 是否保留中文词项。
- claim_id 不匹配是否拒绝续租和保存。

### 集成测试

让多个真实模块一起工作，例如：

- fake model 经过真实 `create_deerflow_agent` 图调用 search 和 submit Tool。
- Task 创建、Workspace、git apply、测试和报告完整运行。
- FastAPI 路由带用户身份验证 owner 隔离。

### 评测

比较系统完成任务的质量和成本。它不只回答代码是否跑通，还回答“对一组固定任务，成功了多少”。

## 当前 20 用例能证明什么

确定性评测使用预先准备的外部 Patch，记录：

- patch apply rate
- test pass rate
- task success rate
- unsafe path blocking
- duration

它适合防止 Worker 和状态机回归，但不能证明模型生成能力，也不能直接得出检索 Recall@5、token 成本或人工接受率。

当前固定集由 10 个成功、4 个 Patch 上下文无效、3 个越界路径、3 个测试失败用例组成。CI 固定检查 task success 和 test pass 都为 0.5、patch apply 为 0.65、越界拦截为 1.0。这里的数字是回归合同，不是线上模型效果。

## Agent 评测应怎样补

准备 20 个具有不同文件和失败模式的小仓库任务，每个任务包含：

```text
requirement
expected relevant files
baseline commit
hidden tests
allowed change scope
```

记录：

| 指标 | 含义 |
| --- | --- |
| Recall@5 | 检索前五是否包含标注相关文件 |
| submit rate | Agent 是否调用 typed submit Tool |
| patch apply rate | 候选能否应用到固定 SHA |
| test pass rate | hidden/approved tests 是否通过 |
| task success rate | 整条链路是否到 HANDOFF_READY |
| tool calls | 搜索和读取次数，反映效率 |
| latency/token | 模型成本 |
| policy block rate | 越权候选是否被拦截 |
| human accept rate | 真实 reviewer 是否接受 |

人工接受率没有真实用户数据时应标记 N/A，不能用“测试通过率”代替。

## GitHub Actions 做什么

CI 工作流在 push 和 pull request 时创建干净 Ubuntu 环境，安装依赖并运行固定命令。它解决“我电脑上能过，但别人 clone 后不一定能过”的问题。

建议至少包含：

```text
ruff check
ruff format --check
pytest tests/code_change
fake-model Agent integration test
20-case deterministic evaluation
Gateway import smoke test
frontend pnpm check
frontend unit test
```

评测输出可作为 artifact 上传，便于比较提交前后指标。

## CI 不等于 CD

CI 是构建和测试。CD 是把通过的版本发布到环境、做 smoke test、监控并回滚。仓库只有 GitHub Actions 测试时，应写“CI”，不能写“完整 CI/CD”。

若以后加 K8s 发布，应记录：镜像 SHA、manifest 版本、rollout 状态、smoke test 和 rollback 证据。

## 为什么 fake model 测试重要

在线模型输出不稳定、需要费用，也可能因限流导致 CI 偶发失败。fake model 固定发出 ToolCall，能验证：

```text
Agent factory
→ Tool schema/binding
→ ToolNode 执行
→ capture candidate
→ no-submit hard failure
```

它证明 Agent 集成代码真实存在，但不证明在线模型足够聪明。两种结论要分开。

## 怎样看一次 GitHub CI 报错

1. 先看失败 job 和第一条实际错误，不从最后的 `exit code 1` 猜。
2. 在本地使用同样工作目录、Python/Node 版本和命令复现。
3. 判断是代码失败、格式失败、依赖锁变化还是环境缺失。
4. 修复后本地跑目标测试，再跑整套检查。
5. 提交并 push，新 run 绿色后记录 URL 与 commit SHA。

不要通过删测试或加无条件 `continue-on-error` 把红灯变绿。

## 本章代码阅读任务

阅读顺序：先看测试分层，再看评测数据怎样产生，最后看 GitHub Actions 怎样调用它们。

1. 打开 `backend/tests/code_change/test_agent_patch.py`，选 `test_real_deerflow_agent_graph_submits_candidate_patch`；再打开 `test_worker.py`，选一个 Agent 模式端到端测试。比较“Agent 图集成”和“Worker 纵向链路”分别断言什么。
2. 打开 `backend/packages/harness/deerflow/code_change/evaluation.py`，按 `EvaluationCase`、`fixed_cases`、`run_evaluation`、`_markdown` 的顺序读。手算四类用例数量，再核对 metrics 的分子和分母。暂不研究 argparse。
3. 打开 `backend/tests/code_change/test_evaluation.py`，读“必须正好 20 例”和“三例小样本指标”两个测试。确认评测脚本自身也有单元测试。
4. 打开 `.github/workflows/code-change-platform.yml`，先看触发分支和 permissions，再按 `code-change-tests` 与 `frontend-code-change` 两个 job 阅读。每个 step 记录 `working-directory`、命令和失败会阻止什么。重点找到 handbook validator、评测阈值、artifact 上传、`pnpm check` 和 `pnpm test`。

看到什么程度：给出一条红色 GitHub Actions 日志时，能先定位 job 和 step，再在相同目录用相同命令本地复现；还能解释每个绿色结果的证据上限。

暂不要求：第一遍不需要学习 GitHub Actions 所有 YAML 语法、Runner 镜像制作或生产 CD。只掌握当前 workflow 的触发、权限、两个 job 和固定命令。

验收动作：闭卷写出当前 CI 的后端与前端检查清单，并解释 evaluation artifact 中五个现有指标；不能把它们说成在线 Agent 成功率。

## 本章自测

1. 单元测试、集成测试和评测分别回答什么问题？
2. 当前 20 用例的四类数量和固定指标是什么？
3. fake model 测试为什么适合普通 CI？
4. 当前 20 用例为什么不能证明 Agent 修复成功率？
5. CI 与 CD 的区别是什么？
6. GitHub Actions 报错时应按什么顺序排查？

## 参考答案

1. 单元测试验证单个函数合同；集成测试验证多个真实模块能协作；评测在固定任务集上比较质量、成本或安全指标。三者不能互相替代。
2. 固定集有 10 个成功、4 个 invalid context、3 个 unsafe path、3 个 test failure。CI 期望 task success 0.5、test pass 0.5、patch apply 0.65、unsafe path block 1.0，并有 10 个 FAILED 与 10 个 HANDOFF_READY。
3. fake model 输出固定 ToolCall，不需要外部 API key、费用或网络，结果可重复。它仍会经过真实 Agent factory 和 ToolNode，所以能发现集成回归。
4. 这 20 例使用预制外部 Patch，主要测 Worker、Patch、测试和拦截。它没有让在线模型检索和生成，也没有记录 token、Recall@5 或真实 reviewer 决定。
5. CI 在干净环境中 lint、测试、构建和评测；CD 把版本发布到环境，还要 rollout、smoke test、监控和 rollback。当前 workflow 主要是 CI。
6. 先找失败 job 与第一条真实错误，再按同一 Python/Node 版本、working directory 和命令本地复现；判断代码、格式、锁文件或环境问题，修复目标测试后再跑整套检查并 push 新 run。
