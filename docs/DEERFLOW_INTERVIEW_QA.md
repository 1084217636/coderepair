# DeerFlow 二开面试问答

## 1. 你是不是复刻 DeerFlow？

不是。DeerFlow 本身已经是开源 SuperAgent harness，有 sub-agents、memory、sandbox、skills/tools 等能力。我做的是基于它的二次开发：

```text
补项目级研发任务助手能力，让 Agent 围绕一个代码仓库持续管理项目上下文、任务、测试结果和报告。
```

## 2. 为什么第一版没有直接让 Agent 自动改代码？

因为企业研发流程里，“能不能改代码”不是第一步，第一步是任务闭环和可验证性：

```text
创建项目空间
绑定仓库和测试命令
输入需求
召回相关上下文
运行测试
生成任务报告
保存 timeline / audit
```

这个闭环稳定后，再接 patch、sandbox 和 PR。

## 3. 你这次二开改了 DeerFlow 哪里？

新增独立包：

```text
backend/packages/harness/deerflow/code_change/
```

它不侵入 DeerFlow 原主链路，先提供 CLI 闭环。后续再接：

```text
backend/app/gateway/routers/code_change.py
DeerFlow sandbox
DeerFlow memory
DeerFlow tools
```

## 4. 为什么用 JSON 文件存储，不直接用数据库？

第一版目标是最小闭环和可演示。JSON 文件有几个好处：

```text
无数据库依赖
容易看产物
适合面试演示
后续迁移到 DeerFlow persistence 成本低
```

## 5. 当前状态机有什么意义？

状态机把一次研发任务拆成可审计步骤：

```text
CREATED
PLANNING
RETRIEVING_CONTEXT
GENERATING_PATCH
APPLYING_PATCH
RUNNING_TESTS
REVIEWING
PR_CREATED / FAILED
```

这样面试时可以讲清楚：Agent 不是黑盒输出，而是每一步都有状态、产物和失败记录。

## 6. 当前 RAG 是不是太简单？

是轻量版。第一版只做关键词召回，目标是跑通闭环：

```text
路径匹配
摘要匹配
文件内容匹配
Top-K 上下文
```

后续可以升级成：

```text
函数级 chunk
符号索引
调用关系
embedding
最近修改历史
```

## 7. 怎么证明它真的跑了？

当前已验证：

```text
project create
task run
project status
patch.diff
pr_body.md
task_report.md
test.log
audit.json
timeline.jsonl
```

这证明它已经是一个项目级任务闭环，不只是文档计划。

## 8. 下一步怎么靠近最终简历项目？

当前 V2 已完成：

```text
1. 增加 patcher.py，支持 unified diff。
2. 增加 patch 路径安全校验，防止写出仓库。
3. 增加 patch.diff / patch_check.log / patch_apply.log。
4. 增加 pr_body.md。
5. task run 支持 --patch-file，完成 patch -> test -> PR draft 闭环。
```

下一步做 V3：

```text
1. 增加 FastAPI router。
2. 把 test_runner 接入 DeerFlow sandbox。
3. 把项目历史接 DeerFlow memory。
```

最终简历叙事：

```text
基于 DeerFlow 二次开发项目级 AI 研发任务助手，支持项目空间、代码上下文召回、测试执行、任务报告、审计留痕，并逐步扩展到 Patch、PR 草稿和 IM 回推。
```

## 9. 你怎么保证 Agent 不乱改文件？

V2 先从 patch 安全边界做起：

```text
1. patch 必须是 unified diff。
2. 解析 diff 里的 changed files。
3. 拒绝绝对路径和包含 .. 的路径。
4. 先 git apply --check，通过后才真正 apply。
5. 所有 patch、日志、审计结果都保存到 task artifact 目录。
```

当前还没有宣称“完全安全”，因为真实生产还需要 Docker sandbox、权限隔离、资源限制和人工审核。这个口径比说“AI 自动改代码很安全”更工程化。

## 10. 和 Cursor / Copilot 的区别是什么？

Cursor / Copilot 更偏个人 IDE 辅助。我这个项目关注企业研发流程里的任务闭环：

```text
项目空间
仓库上下文
任务状态机
Patch 应用
测试验证
PR 草稿
审计记录
```

重点不是模型会不会写代码，而是把代码变更纳入可追踪、可测试、可审核的流程。
