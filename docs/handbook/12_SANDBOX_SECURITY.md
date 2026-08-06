# 12 Sandbox 与安全边界

## 先纠正一个误区

`shell=False` 不是沙箱。它只表示 Python 不把命令字符串交给 `/bin/sh` 解析。下面的命令即使
`shell=False` 也能执行任意 Python：

```text
python3 -c "import os; ..."
```

同样，复制一个目录也不是完整沙箱。local-copy 保护了真实源码不被直接修改，但测试进程仍可能读取宿主机文件、环境变量或网络。

## 当前安全边界分层

### API 层

- 功能默认关闭，需要 `CODE_CHANGE_ENABLED`。
- 项目和任务按当前登录 `owner_id` 隔离。
- repo_path 必须在 `CODE_CHANGE_ALLOWED_REPO_ROOTS` 下。
- 测试只选服务端 profile。
- Worker endpoint 需要内部 token。
- 状态变更请求经过 CSRF。

### Agent 层

- 只有 search、read_file、submit_patch Tool。
- read_file 限制路径、行数和字符数。
- Patch 限制字节数和路径。
- 没有 bash、write_file 和自动 Git push。

### Worker 层

- 在独立 Workspace 应用 Patch。
- 使用固定 argv 与超时。
- 最小化环境变量。
- 写日志和策略文件。
- claim/fencing 防止旧 Worker 覆盖结果。

这些措施能降低风险，但宿主机 subprocess 仍不是不可信代码的最终隔离方案。

## 真正容器 Sandbox 还要做什么

```text
Worker
→ SandboxProvider.acquire(task/thread)
→ 创建短生命周期容器
→ 只读挂载源码基线
→ 可写临时 Workspace
→ 无 Gateway Secret
→ 默认禁网
→ CPU/内存/PID/磁盘限制
→ 非 root 用户
→ seccomp/AppArmor 等系统调用限制
→ 超时销毁
```

执行结果通过明确通道返回，容器销毁后不能继续访问平台。

## 为什么“禁网”很重要

项目测试或恶意 Patch 可能把源码、凭据发送出去，也可能下载额外程序。默认禁网能降低数据外泄和供应链风险。

但某些测试需要下载依赖。公司方案可使用只读依赖缓存、内部代理或域名白名单，而不是开放全网。安全和可用性是明确取舍，不是简单开关。

## owner 隔离不是操作系统隔离

当前 owner 目录能阻止 API 通过正常 Store 读取别人的对象，但同一进程里的代码仍共享操作系统权限。若路径校验或测试执行被绕过，目录命名本身不能阻止访问。

生产环境还需要数据库行级授权、每任务容器、独立工作负载身份和审计。不要把业务层 owner scope 说成强租户沙箱。

## Secret 怎样处理

- `.env` 不提交 Git。
- 浏览器 bundle 不能包含内部 token。
- Gateway 与 Worker 使用不同 Secret 范围。
- 测试容器不继承模型 key、数据库密码和 JWT secret。
- 日志写出前做敏感字段与环境值脱敏。
- CI 使用 GitHub Secrets，但 PR from fork 不应获得高权限 Secret。

## 典型攻击与防护

| 攻击 | 防护 |
| --- | --- |
| repo_path 指向 `/etc` | allowed roots + resolve 校验 |
| Patch 修改 `../../secret` | changed path 校验 |
| read_file 读取仓库外文件 | relative path + resolve + root check |
| 用户提交 `python -c` | 服务端固定 test profile |
| 浏览器领取 Worker 任务 | internal token / workload identity |
| 测试读取 Gateway key | 最小 env + 独立容器 Secret |
| 死循环/进程炸弹 | timeout、PID/CPU/内存限制 |
| 旧 Worker 覆盖新结果 | claim_id/fencing |

## 面试最诚实的回答

> 当前二开已把命令入口改成服务端模板，限制 repo root、Tool 与 Patch 路径，并最小化子进程环境；local-copy 主要解决真实仓库污染，不等于强沙箱。上游 DeerFlow 有 SandboxProvider，我的下一层执行设计是把 Patch/Test 放进短生命周期非 root 容器，默认禁网并限制资源。在真实接完以前，我不会把宿主机 subprocess 说成生产级沙箱。

## 本章代码阅读任务

阅读顺序：按 API、路径、命令、环境、上游 SandboxProvider 五层逐步收紧权限。

1. 打开 `backend/app/gateway/routers/code_change.py`，读 `require_code_change_enabled`、`get_code_change_store`、`get_code_change_test_profiles` 和 `require_internal_worker`。对照四项风险写出它们分别阻止什么。暂不追完整登录页面。
2. 打开 `backend/packages/harness/deerflow/code_change/models.py` 的 `ensure_repo_path`，再读 `agent_patch.py` 的 `_safe_repo_file` 和 `code_change_submit_patch`。比较登记仓库、读文件和 Patch changed path 三层校验，不能只记一个“防目录穿越”。
3. 打开 `backend/packages/harness/deerflow/code_change/sandbox_policy.py`，按 `SandboxPolicy`、`default_policy`、`build_command`、`executable_allowed` 的顺序读。重点记录当前默认 `sandbox_kind="local-copy"`、`network_disabled=False`、超时和日志上限。
4. 打开 `backend/packages/harness/deerflow/code_change/test_runner.py` 的 `build_test_environment`。列出保留的环境变量和重新指向任务目录的 HOME/TMP。确认它减少 Secret 暴露但不改变进程的操作系统用户。
5. 最后读上游 `backend/packages/harness/deerflow/sandbox/sandbox_provider.py` 的 `SandboxProvider.acquire/get/release`。只理解接口和生命周期，暂不阅读 E2B、AIO 或 K8s 具体 Provider。用全文搜索确认当前 Code Change Worker 的 Patch/Test 是否调用这个 Provider。

看到什么程度：随机给出 repo escape、Patch escape、任意命令、浏览器调用 Worker、测试读 Secret、死循环、旧 Worker 写结果七种攻击时，能指出当前防护代码和剩余风险。

暂不要求：不部署容器或编写 seccomp/AppArmor 规则，也不读所有 Sandbox Provider；先分清当前保护与目标隔离。

验收动作：为七种攻击各写“入口、当前防护、剩余风险”三列，任何一项不能只写“有沙箱”。

## 本章自测

1. 为什么 `shell=False` 不是沙箱？
2. owner 目录为什么不是操作系统级多租户隔离？
3. 当前 `local-copy` 真正保护了什么？
4. 固定 profile、executable allowlist 和容器 Sandbox 的强度有什么差别？
5. 为什么容器默认禁网？需要下载依赖时怎么办？
6. 当前 `sandbox_policy.json` 中 `network_disabled=False` 应怎样解释？

## 参考答案

1. 它只阻止 shell 解析 `&&`、重定向等语法。允许的解释器仍可执行代码，项目测试本身也能读取文件、环境或网络。
2. owner scope 约束正常 API 和 Store 路径，但同一宿主机进程仍共享 OS 权限。若测试或路径校验被绕过，目录名不能阻止访问其他可读资源。
3. 它把 Patch 和测试放在固定 commit 导出的任务目录中，避免直接修改登记仓库并减少 Task 之间污染。它没有隔离宿主机文件、用户、网络和内核资源。
4. 固定 profile 控制普通用户能选什么命令；allowlist 再限制可执行文件；容器 Sandbox 才能提供独立文件系统、用户、Secret 范围、网络与资源限制。三者解决不同层面，不能互相冒充。
5. 恶意 Patch 或测试可能把源码和凭据发出，也可能下载未审依赖。需要依赖时可使用内部代理、只读缓存或域名白名单，而不是默认开放全网。
6. 这表示当前策略文件只是如实记录本地执行没有禁网。它不能被表述为网络隔离已完成；目标架构才会在短生命周期容器中实施网络策略。
