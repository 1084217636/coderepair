# DeerFlow 二开模块卡片

## 1. CodeChangeStore

位置：

```text
backend/packages/harness/deerflow/code_change/store.py
```

职责：

```text
管理 project 和 task 的本地 JSON 存储。
```

关键函数：

```text
create_project
list_projects
get_project
new_task_dir
save_task
append_timeline
```

数据位置：

```text
DEER_FLOW_HOME/code-change
或当前目录 .deer-flow/code-change
```

## 2. State Machine

位置：

```text
backend/packages/harness/deerflow/code_change/state_machine.py
```

职责：

```text
约束任务状态不能乱跳，形成可审计任务流。
```

当前状态：

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

## 3. Repo Scanner

位置：

```text
backend/packages/harness/deerflow/code_change/repo_scanner.py
```

职责：

```text
扫描目标仓库，识别 Go / Python / JS / TS / Java / Markdown / YAML / JSON 文件。
```

排除：

```text
.git
.venv
node_modules
dist
build
__pycache__
.deer-flow
```

## 4. Context Retriever

位置：

```text
backend/packages/harness/deerflow/code_change/context_retriever.py
```

职责：

```text
根据需求关键词，对路径、摘要、内容做轻量打分，召回 Top-K 相关文件。
```

当前是轻量关键词召回，不是完整向量 RAG。这样更适合第一阶段闭环。

## 5. Test Runner

位置：

```text
backend/packages/harness/deerflow/code_change/test_runner.py
```

职责：

```text
在目标仓库目录执行 test_command，把 stdout/stderr 保存到 test.log。
```

当前执行方式：

```text
subprocess.run(shell=True, cwd=repo_path)
```

V2/V3 再接 DeerFlow sandbox。

## 6. Report Writer

位置：

```text
backend/packages/harness/deerflow/code_change/report_writer.py
```

职责：

```text
生成 task_report.md 和 audit.json。
```

报告内容：

```text
任务 ID
项目 ID
需求
状态
召回上下文
Patch 结果
测试结果
PR 草稿路径
错误信息
```

## 7. CLI

位置：

```text
backend/packages/harness/deerflow/code_change/cli.py
```

职责：

```text
提供无需前端和 API 的最小演示入口。
```

命令：

```text
project create
project list
project status
task run
```

面试价值：

```text
这证明二开不是只改 README，而是已经有可运行的 project-based workflow。
```

## 8. Patcher

位置：

```text
backend/packages/harness/deerflow/code_change/patcher.py
```

职责：

```text
应用统一 diff，生成 patch.diff、patch_check.log、patch_apply.log，并统计修改文件、增删行。
```

关键函数：

```text
apply_patch_file
apply_patch_text
extract_changed_files
validate_patch_paths
write_pr_body
```

安全边界：

```text
拒绝绝对路径
拒绝包含 .. 的路径
先执行 git apply --check
check 通过后才执行 git apply
```

产物：

```text
patch.diff
patch_check.log
patch_apply.log
pr_body.md
audit.json
```

面试价值：

```text
这让项目从“只跑测试和写报告”升级成“代码变更、测试验证、PR 草稿”的研发效能闭环。
```
