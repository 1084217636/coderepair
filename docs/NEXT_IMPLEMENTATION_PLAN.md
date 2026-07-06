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
GENERATING_PATCH
APPLYING_PATCH
RUNNING_TESTS
REVIEWING
PR_CREATED
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

下一步 V4：

```text
1. 把 patch 执行放到 DeerFlow sandbox 或 Docker workspace。
2. 增加失败任务二次修复入口。
3. 引入任务队列，把 API 和 Worker 解耦。
```

### V5：回推 IM 群聊

目标：

```text
把项目二的任务报告回推到项目一 IM 群聊，形成两个项目之间的叙事连接。
```

先只做可选 webhook：

```text
任务完成 -> 调用 IM Bot webhook -> 群里发送任务摘要、测试结果、风险点
```

V5 不作为第一阶段必做。

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

当前项目二已经完成 V0、V1、V2、V3。下一步建议进入 V4：

```text
1. 接 sandbox/worker。
2. 增加失败任务二次修复。
3. 为任务状态和耗时补指标。
```
