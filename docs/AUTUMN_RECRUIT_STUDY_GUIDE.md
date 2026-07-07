# Autumn Recruit Study Guide

这个项目按 AI 工程 / 研发效能平台项目准备。学习重点不是“大模型会写代码”，而是任务流、上下文、隔离执行、测试闭环和审计。

## 第一阶段：先理解平台闭环

优先学习：

```text
1. DeerFlow 项目结构：backend/app/gateway、backend/packages/harness/deerflow。
2. FastAPI：router、request/response schema、dependency override、TestClient。
3. 任务状态机：CREATED、QUEUED、PLANNING、RETRIEVING_CONTEXT、APPLYING_PATCH、RUNNING_TESTS、PR_CREATED、FAILED。
4. 文件型存储：project.json、task.json、timeline.jsonl、audit.json。
```

能讲清楚：

```text
用户提交需求后，任务如何创建？
为什么 API 不直接执行长任务？
Worker 如何消费任务？
任务失败后如何 retry？
```

## 第二阶段：学习代码变更工程能力

优先学习：

```text
1. Git diff / unified diff / git apply --check。
2. Patch 不能直接改主仓库，为什么要 workspace。
3. test_command 为什么需要超时、日志和资源控制。
4. PR body 需要包含变更说明、测试结果、风险和回滚建议。
```

面试重点：

```text
不要说“AI 自动修代码”。要说“我做的是代码变更任务流：需求、上下文、patch、测试、报告、retry、审计、PR”。
```

## 第三阶段：学习 RAG 和 Agent

优先学习：

```text
1. repo_scanner 如何识别文件语言和摘要。
2. context_retriever 为什么现在是关键词召回，后续如何升级 BM25 / embedding / symbol index。
3. planner / executor / reviewer 的职责划分。
4. sandbox 与 memory 在长任务 Agent 里的作用。
```

面试重点：

```text
代码 RAG 不是普通文档分块。它需要目录结构、函数符号、调用关系、最近修改和测试失败日志共同参与召回。
```

## 第四阶段：补公司级工程认知

优先学习：

```text
1. Redis Stream / PostgreSQL row lock 如何做队列。
2. lease / heartbeat / backoff / DLQ 是什么。
3. Docker sandbox 如何限制 CPU、内存、网络。
4. Prometheus/Grafana 如何看任务失败率、队列积压和测试耗时。
5. GitHub API 如何创建 branch、commit、draft PR。
6. shell=True 为什么危险，shell=False + command whitelist 能解决什么问题。
7. 为什么 V8 只生成 PR handoff，而不是让 Agent 自动 push。
```

推荐复习顺序：

```text
第 1 天：跑 pytest，读 state_machine.py / worker.py。
第 2 天：读 store.py，画 project/task/timeline/audit 文件关系。
第 3 天：读 patcher.py / workspace.py，理解为什么不能污染主仓库。
第 4 天：读 router 测试，学会讲 API -> queue -> worker -> report。
第 5 天：读 DEERFLOW_INTERVIEW_QA，自问自答 Cursor/Copilot 区别。
第 6-7 天：准备一个 demo：坏代码 -> patch -> worker -> tests -> PR draft。
```

## 项目二收尾后的学习资料顺序

现在项目二已经进入 V9 收尾版，学习时按下面顺序读：

```text
1. FINAL_PROJECT_LEARNING_PACKAGE.md
2. FINAL_DEMO_CASES.md
3. FINAL_RESUME_AND_INTERVIEW_PACK.md
4. VERSION_TASK_TRACKER.csv
5. DEERFLOW_CODE_MAP.md
6. PERFORMANCE_AND_EVOLUTION.md
7. DEERFLOW_INTERVIEW_QA.md
```

学习目标：

```text
1. 能画出 project -> task -> worker -> workspace -> test -> report -> PR handoff。
2. 能讲清楚 V1 到 V8 每一版解决了什么瓶颈。
3. 能解释为什么选择 DeerFlow 二开，而不是自己从零写 Agent。
4. 能跑通成功 demo 和失败 retry demo。
5. 能说清楚当前边界和生产化升级方案。
```

秋招复习重点：

```text
FastAPI、pytest、Git diff、任务状态机、队列 Worker、RAG、沙箱、GitHub PR 流程。
```
