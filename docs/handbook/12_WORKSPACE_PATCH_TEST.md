# 12 Workspace、unified diff 与测试门禁

Worker 将 Task 记录的 Git commit 导出到 staging，完成后再替换 Workspace。候选 unified diff 先经路径检查与 `git apply --check`，再应用到 Workspace；登记仓库不会被直接修改。

## unified diff 最小结构

```diff
--- a/app.py
+++ b/app.py
@@ -1,1 +1,1 @@
-old
+new
```

Patcher 解析 changed files，拒绝绝对路径、`..`、Git 元数据和仓库外目标，记录增删行数；`git apply --check` 负责验证上下文能否匹配，真正 apply 才改变 Workspace。

## 测试执行

HTTP 只接收 `test_profile`，命令由服务端配置映射成参数数组。Runner 使用 `shell=False`、最小环境和 timeout；POSIX 下建立新进程组，超时会结束整个组，避免子进程残留。

## 必须主动说明

- `local-copy` 是工作区隔离，不是容器 Sandbox。
- `shell=False` 防止 shell operator 解释，不阻止允许程序访问宿主资源。
- 单个 profile 通过不等于功能绝对正确。
- 测试结果属于指定 source commit、Patch 与环境，缺一项就难以复现。

## 本章代码阅读任务

### Workspace、Patch、Profile、Runner 分四次问

一次只学习一个确定性边界：

> 我现在只学习【当前文件】。请先说明它接收 Agent 候选 Patch 之后负责哪一步，再按类和函数解释基线 commit、临时目录、staging、路径校验、patch check/apply、测试命令白名单、最小环境变量、timeout 和进程组清理。对每个拒绝条件给一个恶意或错误输入，并指出对应异常与测试。最后画出调用前后的文件系统状态，说明当前隔离仍缺什么，并给 3 道带答案的自测题。

不要用“沙箱安全”概括，必须说出当前真实限制。

- 阅读顺序：`backend/packages/harness/deerflow/code_change/workspace.py` → `backend/packages/harness/deerflow/code_change/patcher.py` → `backend/packages/harness/deerflow/code_change/test_profiles.py` → `backend/packages/harness/deerflow/code_change/test_runner.py` → `backend/tests/code_change/` 中对应测试。
- 看到什么程度：能讲固定 commit、staging 发布、两阶段 Patch、命令白名单、最小 env 和 timeout kill。
- 暂不要求：不实现容器编排或远程执行器。
- 验收动作：分别定位拒绝 path escape、`.git`、shell operator、Python 前缀伪装、Secret 继承和超时孙进程的测试。

## 本章自测

1. 为什么不能复制当前脏工作树？
2. `shell=False` 为什么仍不等于 Sandbox？
3. Workspace 刷新为什么先 staging 再替换？

## 参考答案

1. 它可能包含未记录修改且随时变化，无法证明任务针对哪个源码版本。
2. 被执行程序仍可直接访问宿主机文件、网络和系统调用，缺少容器或系统级隔离。
3. 若复制中途失败，直接覆盖会破坏上一份完整 Workspace；staging 成功后发布可保持旧副本可用。
