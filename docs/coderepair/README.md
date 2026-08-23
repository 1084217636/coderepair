# CodeRepair 开发阶段记录

> 文档对应提交：`594d2b63076430f4f1cb492e4c3c85c30b5423ea`
> 生成或最后校验时间：2026-08-14
> 适用分支：`agent-code-change-platform`

本目录保留功能开发时的六阶段记录，不再作为学习顺序。唯一教材是 [`../handbook/README.md`](../handbook/README.md)。DeerFlow 的 Thread、Run、Agent、Tool、Sandbox、Checkpoint 和 SSE 属于上游能力；本项目的自定义范围是 Code Change 控制面与 Anchored Branch Context。

## 历史阶段记录

1. [Phase 1：真实请求链路](PHASE_01_REQUEST_FLOW.md)
2. [Phase 2：最小 Coding Agent Demo](PHASE_02_CODING_AGENT.md)
3. [Phase 3：Anchored Branch](PHASE_03_ANCHORED_BRANCH.md)
4. [Phase 4：BranchContextBuilder](PHASE_04_BRANCH_CONTEXT.md)
5. [Phase 5：BranchDecision 合并](PHASE_05_DECISION_MERGE.md)
6. [Phase 6：Benchmark、README 与面试](PHASE_06_BENCHMARK_INTERVIEW.md)

每个阶段都必须回答：用了什么上游能力、改了什么、为什么这样设计、请求如何走、重要文件/符号是什么、还需要学习什么、面试怎么追问。
