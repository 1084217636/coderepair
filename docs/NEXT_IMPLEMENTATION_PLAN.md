# Agent Code Change Platform 下一步修改计划

## 1. 项目新定位

项目二不做“复刻 DeerFlow”，而是做：

```text
基于 DeerFlow 的项目级 AI 研发任务助手二次开发
```

主线闭环：

```text
创建项目空间
  ↓
绑定代码仓库 / 测试命令
  ↓
输入需求
  ↓
Agent 读取项目上下文
  ↓
生成计划
  ↓
检索相关文件
  ↓
运行测试
  ↓
输出任务报告
  ↓
可选回推 IM 群聊
```

这个项目重点训练：

```text
接手已有开源 Agent 项目
理解核心模块
做小功能增量
形成可验证闭环
```

## 2. 版本路线

### V0：跑通 DeerFlow + 建代码地图

目标：

```text
先跑通项目，再理解 DeerFlow 关键模块，不急着改 Agent 主链路。
```

当前状态：

```text
已完成 DEERFLOW_CODE_MAP / DEERFLOW_MODULE_CARDS / DEERFLOW_TEST_EVIDENCE / DEERFLOW_INTERVIEW_QA。
```

要做：

```text
1. 阅读 README / Install / backend docs。
2. 跑 make doctor 或最小测试命令。
3. 梳理 backend/app/gateway/routers。
4. 梳理 backend/packages/harness/deerflow 下的 agents、memory、sandbox、skills、tools、persistence。
5. 写模块卡片。
```

新增或修改：

```text
docs/DEERFLOW_CODE_MAP.md
docs/DEERFLOW_MODULE_CARDS.md
docs/DEERFLOW_TEST_EVIDENCE.md
docs/DEERFLOW_INTERVIEW_QA.md
```

V0 不做：

```text
不改 frontend
不改 LangGraph 主 agent
不改 subagents
不改 memory middleware
不改 sandbox provider
不改 auth / user / channel 体系
```

### V1：项目空间 + 任务报告闭环

目标：

```text
先实现项目级上下文和任务报告，不急着让模型自动改代码。
```

当前状态：

```text
已完成 backend/packages/harness/deerflow/code_change 独立包。
已完成 project create/list/status 和 task run CLI。
已完成 repo scan、context retrieve、test runner、task_report、audit、timeline。
当前环境缺少 uv/pytest，已用 compileall + CLI 闭环验证通过。
```

第一轮独立包落点：

```text
backend/packages/harness/deerflow/code_change/
```

原因：

```text
1. DeerFlow 原项目很大，独立包减少侵入。
2. 便于单元测试和命令行演示。
3. 后续再接 FastAPI router、tools 或 DeerFlow memory。
```

CLI 命令：

```bash
python -m deerflow.code_change.cli project create demo \
  --repo-path /tmp/demo-repo \
  --test-command "go test ./..."

python -m deerflow.code_change.cli project list
python -m deerflow.code_change.cli project status demo
python -m deerflow.code_change.cli task run demo "修复 health handler 的单测失败"
```

V1 文件级新增：

```text
backend/packages/harness/deerflow/code_change/__init__.py
backend/packages/harness/deerflow/code_change/models.py
backend/packages/harness/deerflow/code_change/store.py
backend/packages/harness/deerflow/code_change/state_machine.py
backend/packages/harness/deerflow/code_change/repo_scanner.py
backend/packages/harness/deerflow/code_change/context_retriever.py
backend/packages/harness/deerflow/code_change/test_runner.py
backend/packages/harness/deerflow/code_change/report_writer.py
backend/packages/harness/deerflow/code_change/cli.py
backend/tests/code_change/test_state_machine.py
backend/tests/code_change/test_store.py
backend/tests/code_change/test_repo_scanner.py
backend/tests/code_change/test_task_runner.py
```

V1 产物：

```text
.deer-flow/code-change/
├── projects.json
└── projects/
    └── demo/
        ├── project.json
        ├── timeline.jsonl
        └── tasks/
            └── task_20260703_xxx/
                ├── task.json
                ├── task_report.md
                ├── test.log
                └── audit.json
```

V1 验收：

```bash
cd agent-code-change-platform/backend
uv run pytest tests/code_change
```

如果本地没有 `uv`，使用：

```bash
python -m deerflow.code_change.cli project create demo --repo-path tests/fixtures/go_demo_repo --test-command "go test ./..."
python -m deerflow.code_change.cli task run demo "修复 health check 测试"
python -m deerflow.code_change.cli project status demo
```

### V2：代码变更任务流

目标：

```text
在 V1 项目空间和报告闭环基础上，增加 patch / test / PR 草稿能力。
```

当前 V2 已落地：

```text
backend/packages/harness/deerflow/code_change/patcher.py
backend/tests/code_change/test_patcher.py
task run --patch-file <unified-diff>
patch.diff
patch_check.log
patch_apply.log
pr_body.md
```

任务状态机：

```text
CREATED
PLANNING
RETRIEVING_CONTEXT
PATCH_RECEIVED
VALIDATING_PATCH
APPLYING_PATCH
RUNNING_TESTS
REVIEWING
HANDOFF_READY
FAILED
ROLLED_BACK
```

V2 产物增加：

```text
patch.diff
patch_check.log
patch_apply.log
pr_body.md
```

`pr_body.md` 包含：

```text
需求摘要
修改文件
核心改动
测试结果
风险点
回滚建议
```

V2 不做：

```text
不直接创建真实 GitHub PR
不把 patcher 接入真实大模型
不接 FastAPI router
不改 DeerFlow 主 agent 链路
```

V3 已落地：

```text
1. 接 FastAPI router，暴露 project/task/timeline/report/pr-body 接口。
2. API 支持 patch_text 触发 patch/test/pr draft 闭环。
3. 增加 router 级测试。
```

V3 当前边界：

```text
1. API 同步执行任务，长测试会占用请求线程。
2. 仍使用 JSON 文件存储，不适合高并发写入。
3. timeline 仍是全量读取，后续需要分页。
```

V4 已落地：

```text
1. 引入 QUEUED 状态。
2. 新增 task_queue.jsonl 单机队列。
3. 新增 worker.py，支持 run_next_task。
4. CLI 支持 task enqueue / worker run-once。
5. API 默认创建 QUEUED 任务，新增 /api/code-change/worker/run-once。
```

V4 当前边界：

```text
1. JSONL 队列只适合单机 MVP。
2. 暂无任务租约、重试次数、死信队列。
3. patch/test 仍未进入 Docker 或 DeerFlow sandbox。
```

V5 已落地：

```text
1. Task 增加 attempt_count / max_attempts / last_error / queued_at / started_at / finished_at。
2. State machine 允许 FAILED -> QUEUED，用于显式 retry。
3. Worker 新增 retry_task，失败任务可重新入队。
4. CLI 新增 task retry 和 worker metrics。
5. API 新增 /api/code-change/metrics 和 /projects/{project_id}/tasks/{task_id}/retry。
6. Store 新增 list_tasks / task_metrics，输出 status_counts、queue_depth、failed_count、retryable_failed_count。
```

V5 当前边界：

```text
1. retry 仍是手动触发，没有自动退避调度。
2. task_queue.jsonl 仍是单机队列，没有 lease 和 heartbeat。
3. patch/test 仍未进入 Docker 或 DeerFlow sandbox。
```

下一步 V6：

```text
1. 把 patch/test 执行放到 DeerFlow sandbox 或 Docker workspace。
2. 对测试命令增加超时、日志截断和资源限制。
3. 失败后保留 repo diff、test.log、last_error，供二次修复 Agent 使用。
```

V6 已落地：

```text
1. 新增 workspace.py，创建 artifacts/workspace 本地隔离工作区。
2. Worker 在原仓库做 scan/context retrieve，但在 workspace 中 apply patch 和 run tests。
3. Task 新增 source_repo_path / workspace_path / sandbox_kind。
4. task_report.md 和 audit.json 输出 workspace 证据。
5. 测试验证原仓库不被 patch 污染，workspace 中变更和测试通过。
```

V6 当前边界：

```text
1. local-copy 不是容器级 sandbox，不能限制资源和网络。
2. 大仓库复制成本较高。
3. test_command 仍需白名单和参数化改造。
```

下一步 V7：

```text
1. 接 Docker/DeerFlow sandbox，限制 CPU、内存、网络和文件系统。
2. 增加 workspace manifest 和日志截断。
3. 对通过测试的 patch 生成 GitHub draft PR。
```

V7 已落地：

```text
1. 新增 sandbox_policy.py，定义 allowed_executables、timeout_seconds、max_log_bytes、network_disabled。
2. test_runner 改为 shlex.split + shell=False，拒绝 shell operator 和非白名单命令。
3. 每个任务输出 sandbox_policy.json。
4. workspace.py 输出 workspace_manifest.json，记录文件数、大小、忽略目录和复制耗时。
5. TestResult 新增 timed_out / log_truncated / policy_path。
6. 测试覆盖 shell operator 被阻断、python 命令正常执行、manifest 生成。
```

V7 当前边界：

```text
1. 仍不是容器级安全隔离。
2. 没有限制 CPU/内存/网络。
3. 命令白名单较保守，复杂测试命令需要后续模板化支持。
```

下一步 V8：

```text
1. 接 Docker/DeerFlow sandbox。
2. 接 GitHub draft PR。
3. 将任务完成摘要回推项目一 IM 群聊。
```

V8 已落地：

```text
1. 新增 pr_handoff.py。
2. HANDOFF_READY 时生成 pr_handoff.json。
3. HANDOFF_READY 时生成 create_draft_pr.sh。
4. Task 新增 pr_handoff_path / pr_create_script_path。
5. Router/CLI 返回 task 时能看到 PR handoff 产物路径。
6. 测试覆盖 gh pr create --draft 命令生成。
```

V8 当前边界：

```text
1. 不自动 push，不自动创建真实 PR。
2. 需要人工审核 pr_handoff.json 和 create_draft_pr.sh 后再执行。
3. 真正的 GitHub API 自动化可以作为扩展，但不建议继续堆到秋招主线里。
```

V9 已落地：最终收口

```text
1. 固定 demo case。
2. 整理最终简历 bullet。
3. 整理高频面试问答。
4. 明确“不做”的生产化边界：分布式队列、容器级 sandbox、真实自动 PR、权限系统。
```

### V9：最终学习和面试收口

目标：

```text
把项目二收成可学习、可演示、可写简历、可被面试官追问的最终版本。
```

已落地产物：

```text
docs/FINAL_PROJECT_LEARNING_PACKAGE.md
docs/FINAL_RESUME_AND_INTERVIEW_PACK.md
docs/FINAL_DEMO_CASES.md
docs/VERSION_TASK_TRACKER.csv
```

原先“回推 IM 群聊”不再作为项目二必做功能。它可以作为两个项目之间的扩展叙事，但不进入秋招主线，避免项目二继续发散。

## 3. 每次 AI 帮你改完必须补的内容

每做完一个功能，都要补：

```text
1. 改了哪些文件？
2. 新增了哪些类 / dataclass / 函数？
3. 谁调用谁？
4. 数据保存在哪里？
5. 产物保存在哪里？
6. 怎么测试？
7. 成功日志是什么？
8. 失败情况怎么处理？
9. 面试官可能怎么追问？
```

写入：

```text
docs/DEERFLOW_MODULE_CARDS.md
docs/DEERFLOW_TEST_EVIDENCE.md
docs/DEERFLOW_INTERVIEW_QA.md
```

## 4. 下一步立刻执行

当前项目二已经完成 V0、V1、V2、V3、V4、V5、V6、V7、V8、V9。下一步进入学习和演示阶段：

```text
1. 不再继续堆大功能。
2. 按 FINAL_DEMO_CASES.md 跑成功 demo 和失败 retry demo。
3. 按 FINAL_RESUME_AND_INTERVIEW_PACK.md 准备简历 bullet 和面试回答。
4. 把项目讲成研发效能平台，而不是 AI 写代码玩具。
```
