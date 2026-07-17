# 项目二最终学习包：基于 DeerFlow 二开的 AI 代码变更平台

## 1. 项目定位

项目名：

```text
基于 DeerFlow 二开的项目级 AI 代码变更与 PR 交付平台
```

一句话介绍：

```text
我基于字节开源 DeerFlow 的 Agent harness 做二次开发，补充项目空间、代码上下文召回、Patch 应用、沙箱测试、任务审计、失败重试和 PR handoff，让一次 AI 代码修改从需求到审核材料形成可追踪闭环。
```

这个项目不要讲成：

```text
我做了一个 AI 自动改代码工具。
```

应该讲成：

```text
我做的是企业研发流程里的代码变更任务平台，重点不是模型生成代码，而是把需求、上下文、变更、测试、审计、PR 审核串起来。
```

## 2. 为什么选择 DeerFlow 二开

选择 DeerFlow 的原因不是“蹭开源项目”，而是训练真实公司里常见的能力：

```text
1. 接手已有复杂项目，而不是永远从零写 demo。
2. 复用已有 Agent harness、memory、sandbox、tools、gateway 等基础能力。
3. 在不破坏原主链路的前提下，做一个清晰的增量业务功能。
4. 证明自己能读开源项目、找扩展点、做闭环、写测试和整理文档。
```

DeerFlow 已经提供了通用 SuperAgent 底座。我的二开重点是补“项目级研发任务流”：

```text
单次对话任务
  ↓
项目空间
  ↓
代码仓库上下文
  ↓
任务状态机
  ↓
Patch/Test/Report/PR
  ↓
审计与复盘
```

## 3. 重点解决的问题

普通 AI 编码工具的问题：

```text
1. 容易停留在一次聊天，不保存项目级上下文。
2. 生成代码后缺少强制测试和日志证据。
3. 直接改主仓库风险高，失败后难复盘。
4. 没有任务状态机，用户不知道执行到哪一步。
5. 没有审计记录，不适合企业研发流程。
6. PR 描述、风险点、回滚建议通常靠人工补。
```

本项目解决的核心问题：

```text
需求输入
  ↓
项目空间保存仓库、测试命令、历史任务
  ↓
扫描仓库并召回相关代码
  ↓
在隔离 workspace 应用 patch
  ↓
按 sandbox policy 执行测试
  ↓
保存日志、报告、审计、timeline
  ↓
失败可 retry
  ↓
成功生成 PR handoff 和 draft PR 脚本
```

## 4. 闭环链路

完整链路：

```text
project create
  ↓
task enqueue / task run
  ↓
QUEUED / CREATED
  ↓
PLANNING
  ↓
repo_scanner 扫描源码文件
  ↓
context_retriever 召回相关文件
  ↓
workspace 复制隔离工作区
  ↓
patcher 做 git apply --check / git apply
  ↓
test_runner 使用 shell=False + sandbox policy 执行测试
  ↓
report_writer 写 task_report.md / audit.json
  ↓
worker 写 task.json / timeline.jsonl / metrics
  ↓
pr_handoff 写 pr_handoff.json / create_draft_pr.sh
  ↓
人工审核后创建 GitHub draft PR
```

最终状态不是简单的 `SUCCESS`，而是更贴近研发流程的：

```text
HANDOFF_READY
```

它表示这次变更已经通过测试并生成可审核的 PR 交付材料。

## 5. 版本演化

| 版本 | 目标 | 解决的瓶颈 | 核心产物 |
| --- | --- | --- | --- |
| V0 | 跑通项目并画代码地图 | 不了解 DeerFlow，容易乱改 | `DEERFLOW_CODE_MAP.md`、模块卡片、问答 |
| V1 | 项目空间和任务报告 | 单次对话没有项目上下文 | `project.json`、`task_report.md`、`audit.json` |
| V2 | Patch/Test/PR 草稿 | 只有报告，没有真实代码变更 | `patch.diff`、`patch_check.log`、`pr_body.md` |
| V3 | FastAPI API | CLI 不像平台项目 | `/api/code-change/*`、TestClient 测试 |
| V4 | 队列和 Worker | HTTP 同步执行长任务 | `task_queue.jsonl`、`worker run-once` |
| V5 | Retry 和 metrics | 失败任务不可恢复，不好观测 | `attempt_count`、`last_error`、`/metrics` |
| V6 | Workspace 隔离 | Patch/Test 污染主仓库 | `artifacts/workspace`、`workspace_path` |
| V7 | Sandbox policy | 测试命令边界太弱 | `sandbox_policy.json`、`shell=False`、白名单 |
| V8 | PR handoff | 只生成 PR 文本，离真实交付还有一步 | `pr_handoff.json`、`create_draft_pr.sh` |
| V9 | 学习和面试收口 | 功能分散，不利于复盘和讲述 | 最终学习包、简历包、demo case |

这套演进在面试里要按“发现瓶颈、做小版本优化”的方式讲，而不是罗列功能。

## 6. 代码地图

核心二开包：

```text
backend/packages/harness/deerflow/code_change/
```

关键文件：

```text
models.py             Project / Task / TaskStatus / TestResult / PatchResult
store.py              JSON 文件存储，project/task/timeline/queue/metrics
state_machine.py      任务状态流转校验
repo_scanner.py       仓库文件扫描和摘要
context_retriever.py  轻量代码上下文召回
patcher.py            unified diff 校验、应用、PR body
workspace.py          local-copy workspace 隔离
sandbox_policy.py     命令白名单、超时、日志截断策略
test_runner.py        shell=False 执行测试命令
worker.py             创建任务、消费队列、执行闭环、retry
pr_handoff.py         生成 PR handoff 和 draft PR 脚本
report_writer.py      写 task_report.md 和 audit.json
cli.py                本地演示入口
```

API 接入：

```text
backend/app/gateway/routers/code_change.py
```

测试：

```text
backend/tests/code_change/
```

## 7. 需要掌握的基础知识

基础技术栈：

```text
Python dataclass / pathlib / subprocess / shlex
FastAPI / Pydantic / APIRouter / Depends / TestClient
pytest 单元测试和接口测试
Git unified diff / git apply --check / git apply
任务状态机
队列和 Worker
JSONL 事件日志
沙箱执行和命令白名单
RAG 基础：scan / retrieve / top-k / snippet
GitHub PR 流程：branch / commit / push / draft PR
```

秋招需要背的重点不是所有库 API，而是这些问题：

```text
1. 为什么任务要有状态机？
2. 为什么 API 不能同步执行长测试？
3. 为什么 AI 不能直接改主仓库？
4. 为什么测试命令不能随便 shell=True？
5. 代码 RAG 和文档 RAG 有什么区别？
6. Retry、metrics、audit 在企业系统里解决什么问题？
7. 为什么当前只生成 PR handoff，而不是自动 push？
```

## 8. 当前测试工具

项目当前使用这些验证手段：

```text
python3 -m compileall
pytest
FastAPI TestClient
CLI smoke test
git apply --check
git diff --check
```

其中：

```text
compileall       验证 Python 语法。
pytest           验证状态机、store、patch、worker、sandbox、router。
TestClient       验证 HTTP API 行为。
CLI smoke        验证用户视角的端到端链路。
git diff --check 验证提交前没有空白字符问题。
```

## 9. 当前边界和未来优化

当前项目已经适合作为秋招项目收尾，但不能夸大成完整生产系统。

当前边界：

```text
1. 存储仍是 JSON 文件，不是 PostgreSQL。
2. 队列仍是 JSONL，不支持多 worker 抢占和 lease。
3. sandbox policy 不是 Docker 级隔离。
4. RAG 是轻量关键词召回，不是完整符号索引和 embedding。
5. PR handoff 生成脚本，不自动调用 GitHub API。
```

生产化优化方向：

```text
1. JSON 文件迁移到 PostgreSQL。
2. task_queue.jsonl 迁移到 Redis Stream 或数据库队列。
3. 增加 lease / heartbeat / backoff / dead-letter queue。
4. 接 Docker 或 DeerFlow sandbox，限制 CPU、内存、网络和文件系统。
5. 代码索引升级为 symbol index + BM25 / embedding。
6. metrics 接 Prometheus / Grafana。
7. PR 创建接 GitHub App，并加权限审批。
```

## 10. 学习顺序

建议你按这个顺序学，不要从 DeerFlow 全量源码开始硬啃：

```text
第 1 天：读 docs/FINAL_PROJECT_LEARNING_PACKAGE.md，先理解项目故事。
第 2 天：读 models.py / state_machine.py，画出任务状态机。
第 3 天：读 store.py / worker.py，理解项目、任务、队列、retry。
第 4 天：读 patcher.py / workspace.py / test_runner.py，理解 patch/test/sandbox。
第 5 天：读 router 和 router 测试，理解平台 API。
第 6 天：跑 FINAL_DEMO_CASES.md 里的 demo，保存产物截图或日志。
第 7 天：背 FINAL_RESUME_AND_INTERVIEW_PACK.md，把项目讲成 1 分钟和 3 分钟版本。
```

## 11. 面试时的主线表达

推荐回答：

```text
这个项目不是复刻 DeerFlow，也不是让大模型裸写代码。我基于 DeerFlow 的 Agent harness 做了一个项目级代码变更任务流扩展。用户可以创建项目空间，绑定仓库和测试命令，提交需求后平台会召回相关代码、应用 patch、在隔离 workspace 里跑测试、记录审计日志和 timeline，成功后生成 PR handoff。我的重点是把 AI 代码修改纳入企业研发流程，做到可追踪、可测试、可审核、可回滚。
```

这一段是你最应该背熟的项目总括。
