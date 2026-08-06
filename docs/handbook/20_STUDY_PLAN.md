# 20 四周学习计划与验收表

这份计划假设 LinkGo 已先学完。每天先口述，再看代码；不要只读文档。

## 第 1 周：能讲清 DeerFlow 与二开边界

### 第 1～2 天

- 读 00～04。
- 手画 Frontend、Gateway、Agent Runtime、Code Change Worker。
- 口述“上游已有 / 我新增 / 当前未完成”。

### 第 3～4 天

- 读 05～06。
- 每个概念举一个项目内例子：Agent、Tool、Skill、Middleware、Sub-Agent、Worker。
- 打开 `backend/packages/harness/deerflow/agents/factory.py`，只读 `create_deerflow_agent` 的函数签名、`middleware is not None` 分支和最终 `create_agent(...)` 调用。能说出 model、tools、system_prompt、middleware、features、checkpointer 的作用即可，暂不读 `_assemble_from_features` 全部实现。

### 第 5～7 天

- 跑后端测试和第一次外部 Patch demo。
- 在一个实际 Task 目录按 `task.json`、`workspace_manifest.json`、`patch_check.log`、`patch_apply.log`、`test.log`、`task_report.md` 顺序查看。`task.json` 要找到 status、source_commit、steps、patch_result、test_result；日志读到能确认命令、退出码和错误即可。
- 能用一分钟解释为什么模型不直接写仓库。

周验收：不看文档画出两条链路，并指出至少 5 个上游能力和 5 个个人二开能力。

## 第 2 周：吃透状态和可靠执行

### 第 8～10 天

- 读 07～08。
- 手写 Task 主要字段和主状态迁移。
- 用 A/B Worker 时间线解释 lease 与 fencing。

### 第 11～12 天

- 依次读 `models.py::TaskStatus/Project/Task`、`state_machine.py::ALLOWED_TRANSITIONS/transition`、`store.py::claim_next_task/renew_task_claim/save_task/release_task_claim`。每个符号写输入、状态副作用和一个失败分支，暂不读序列化辅助函数。
- 为一条非法状态迁移补单元测试。
- 在 `store.py::_claim_path/_claim_task_file/_write_json` 找到 `.claim.json`、`O_CREAT | O_EXCL` 和 `os.replace`。同时读 `_task_claim_lock`，明确 `fcntl.flock` 只适用于当前 POSIX 本地文件原型。

### 第 13～14 天

- 模拟 Worker 执行中 lease 过期。
- 口述 Task 已写 DB 但队列未发时为什么需要 Outbox。

周验收：面试官随便问一个状态，你能说进入证据、允许后继和失败恢复。

## 第 3 周：Agent、Patch、安全与测试

### 第 15～17 天

- 读 09～10，再按 `agent_patch.py::PatchCapture/build_code_change_tools/create_code_change_agent/generate_patch_with_agent` 顺序读源码。三个 Tool 分别写出参数、返回值和权限；看到 typed submit 的 hard failure 即可。
- 运行 `PYTHONPATH=. uv run pytest tests/code_change/test_agent_patch.py -q`，再逐个核对越界读取、单次 typed submit、真实 Agent 图、未 submit 失败四个测试名称和断言。
- 自己写一个 escape path 测试。

### 第 18～19 天

- 读 11～12。
- 手工执行 `git apply --check` 和 `git apply`。
- 解释 `shell=False`、固定 profile、最小 env 和容器 Sandbox 的差别。

### 第 20～21 天

- 运行 `test_patcher.py::test_patcher_rejects_paths_outside_repo` 和 `test_test_runner.py::test_run_tests_timeout_kills_spawned_process_group`。分别查看异常或 `TestResult` 的 error、exit_code、timed_out、log_path，读到能解释为何失败即可。
- 口述为什么 source commit 必须固定。

周验收：闭卷讲 requirement 到 HANDOFF_READY，至少包含 15 个具体函数/字段名。

## 第 4 周：CI、公司部署和面试

### 第 22～24 天

- 读 13～16。
- 打开 `.github/workflows/code-change-platform.yml`，按 `code-change-tests`、`frontend-code-change` 两个 job 读。为每个 step 记录 working-directory 和命令，尤其是 ruff、pytest、handbook validator、20 例阈值、artifact、pnpm check/test。
- 打开一次 `evaluation.json`，找到 suite、metrics、cases。核对 task_count=20、task/test success=0.5、patch apply=0.65、unsafe block=1.0；暂不把这些数字解释为模型成功率。

### 第 25～26 天

- 读 17，随机抽 8 个故障回答。
- 画 PostgreSQL + Outbox + Queue + Worker + Object Storage + Sandbox 多机图。

### 第 27～28 天

- 读 18～19，录制三分钟项目介绍。
- 让另一个人连续追问 30 分钟。
- 把答不上来的重要问题补回手册和代码注释，而不是临时编答案。

## 最终验收清单

### 代码所有权

- [ ] 能说出至少 12 个主要类/函数的输入、输出和失败路径。
- [ ] 能独立新增一个状态机测试和一个 Tool 安全测试。
- [ ] 能读懂一次完整 task.json 和 report。
- [ ] 能解释上游 factory 的复用位置。

### 可靠性

- [ ] 能画 claim/lease/heartbeat/fencing 时间线。
- [ ] 能解释重复队列消息为什么不等于重复外部副作用。
- [ ] 能解释 PR 远端成功、本地保存前宕机的处理。
- [ ] 能说明文件 Store 为什么不能直接多 Pod。

### Agent 工程

- [ ] 分清 Agent、Tool、Skill、Middleware、Sub-Agent 和 Worker。
- [ ] 能解释 typed submit Patch 为何优于解析 Markdown。
- [ ] 能区分 fake-model 集成测试和在线模型评测。
- [ ] 能列出 Recall@5、apply、test、task success、token 和人工接受率。

### 安全

- [ ] 能解释 `shell=False` 的边界。
- [ ] 能说明 repo root、path resolve、profile、internal token、minimal env。
- [ ] 不把 local-copy 说成强沙箱。
- [ ] 不把 owner 目录说成操作系统级多租户隔离。

### 投递表达

- [ ] 三分钟介绍不看稿。
- [ ] 能明确列出上游与个人贡献。
- [ ] 不声称已自动创建 PR、生产 K8s 或真实人工接受率。
- [ ] 能回答为什么这个项目与 AI Platform/App Infra 岗位有关。

全部勾选后，项目资料才真正变成你的面试能力，而不只是仓库里的代码。

## 本章代码阅读任务

阅读顺序：本章不是再读一遍全部源码，而是用三条主线验收前四周结果。

1. 调用主线：从 `routers/code_change.py::run_project_task` 跟到 `worker.py::create_task/run_next_task/execute_task`，再跟到 Workspace、Patch、Test、Report、Review。外部和 Agent 两种模式各讲一次。
2. 可靠性主线：从 `store.py::claim_next_task` 跟到 `renew_task_claim/save_task/release_task_claim`，再读 `worker.py::_TaskClaimHeartbeat`。画 A/B Worker 时间线。
3. 证据主线：从 `evaluation.py::fixed_cases/run_evaluation` 跟到 `.github/workflows/code-change-platform.yml` 的阈值和 artifact 上传，再对照一个实际 `task_report.md`。

看到什么程度：三条主线都能闭卷讲 5 分钟，讲错时能回到具体函数或字段定位，而不是重新问 AI 整个项目是什么。

暂不要求：四周计划不要求记住所有第三方库源码，也不要求完成生产 K8s、真实 GitHub Provider 或在线模型大规模评测。先获得当前代码所有权。

验收动作：安排两次 30 分钟模拟面试。第一次允许在结束后查手册纠错；第二次全程闭卷。把第二次仍答错的关键问题补进对应章节，而不是只追加到本计划。

## 本章自测

1. 第一周结束时最低要能讲什么？
2. 第二周怎样证明自己理解 lease 与 fencing？
3. 第三周怎样证明自己理解 Agent 与安全边界？
4. 第四周怎样证明自己会看 CI，而不是只知道名称？
5. 哪四种过度表述会直接导致最终验收失败？
6. 什么时候可以把学习计划视为完成？

## 参考答案

1. 能画上游 DeerFlow 与个人 Code Change 两张图，指出至少 5 个上游能力和 5 个个人二开能力，并跑通外部 Patch demo、找到主要 artifact。
2. 不看文档画 A claim、heartbeat、暂停、lease 过期、B 接管、A save/release 被拒绝的时间线，并能定位 Store 的 claim_id 比较与对应测试。
3. 能讲三个 Tool、typed submit、Agent 模式如何接回 Worker；能写一个 repo escape 测试，并区分固定 profile、最小 env、local-copy 与容器 Sandbox。
4. 能打开 workflow 说出两个 job 的 Runner、版本、working directory、命令和 artifact；看到红灯先定位第一条真实错误，并在本地用相同命令复现。
5. 把上游 Agent 架构说成自研；把 local-copy 说成容器沙箱；把 handoff 说成已创建 PR；把固定外部 Patch 20 例说成在线模型或人工接受率。
6. 最终清单全部能用口述、画图、源码定位和测试证据证明，并连续两次模拟面试不再出现重要结构、调用链或能力边界错误时，才算完成。
