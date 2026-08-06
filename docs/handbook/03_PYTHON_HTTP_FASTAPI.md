# 03 Python、HTTP 与 FastAPI 基础

## 先分清四个东西

### Python 模块

一个 `.py` 文件就是模块。`from deerflow.code_change.store import CodeChangeStore`
表示从模块导入类。包目录中的 `__init__.py` 决定哪些对象作为公共入口导出。

### 进程

Gateway 和 Worker 在公司部署中是不同进程。它们可以在不同机器上运行，不能依赖共享内存。当前 HTTP 路由创建 Task 后入队，内部 `/worker/run-once` 仍在 Gateway 进程中同步执行一次 Worker 函数；CLI 才有直接同步执行入口。这些都是本地演示方式，不是最终部署形态。

### HTTP

浏览器通过 HTTP 请求 Gateway。一个请求至少包含方法、路径、Header 和 Body：

```http
POST /api/code-change/projects/demo/tasks
Content-Type: application/json
Cookie: access_token=...
X-CSRF-Token: ...

{"requirement":"修复空用户名错误","patch_text":"..."}
```

`POST` 表示创建或触发状态变化，`GET` 表示读取。状态码的含义也要会：

- `200/201`：请求成功。
- `400`：输入格式或参数不合法。
- `401`：没有登录。
- `403`：已登录但没有权限，或 CSRF/内部 token 不正确。
- `404`：资源不存在，或功能关闭时隐藏路由。
- `409`：资源状态冲突，例如不是 `HANDOFF_READY` 却尝试 approve。

### JSON

JSON 是 HTTP API 常用的数据格式。Pydantic 会把 JSON 转成 Python 对象并检查字段。它只负责结构校验，不会自动保证业务安全。例如字段是字符串，不代表这个字符串可以安全地当命令执行。

## FastAPI Router 怎样工作

入口位于：

```text
backend/app/gateway/routers/code_change.py
```

典型结构：

```python
@router.post("/projects")
def create_project(request: ProjectCreateRequest, store=Depends(...)):
    ...
```

执行顺序可以理解为：

```text
HTTP 请求
→ 认证/CSRF Middleware
→ 路由匹配
→ Pydantic 解析 Body
→ Depends 创建当前用户的 Store
→ 业务函数
→ dict 序列化为 JSON
```

`Depends(get_code_change_store)` 很重要。它从 DeerFlow 的用户上下文拿到
`user_id`，再创建 owner-scoped Store。若在 Router 里直接用一个全局 Store，不同用户就可能读到同一个目录。

## 同步函数和异步函数

FastAPI 同时支持 `def` 和 `async def`。当前 Code Change 涉及文件、Git 和 subprocess，这些大多是阻塞操作。不能仅把函数改成 `async def` 就变成非阻塞；阻塞调用仍会卡事件循环。

正确的公司部署是：Gateway 快速写入任务并返回，独立 Worker 做耗时工作。这样一次测试跑两分钟不会占住 Web 请求线程，也不会拖慢其他用户的 API。

## 为什么需要认证和 CSRF

Cookie 会被浏览器自动携带。攻击者可能诱导已登录用户访问恶意页面，由恶意页面发起修改请求。因此前端的 fetch wrapper 会在状态变更请求中附带
`X-CSRF-Token`，Gateway 比较 Header 与 CSRF Cookie。

认证解决“你是谁”，CSRF 解决“这个浏览器请求是否来自可信页面”。两者不能互相替代。

## 为什么 Worker 还要单独的内部身份

普通登录用户可以创建自己的任务，但不能伪装成 Worker 领取和执行任务。`/worker/run-once`
需要内部 token，且 token 必须由服务端环境注入，不能放进 Next.js 客户端代码。否则任何浏览器用户都能消耗计算资源、竞争 claim，甚至触发测试执行。

## 面试追问

**问：既然已经有 JWT，为什么还要内部 token？**

答：JWT 表示终端用户身份，内部 token 表示服务到服务身份，两者权限域不同。用户能创建和查看自己的任务，不代表有 Worker 执行权限。生产环境会进一步使用 mTLS、工作负载身份或网关内网策略。

**问：为什么不在 POST 请求里直接等测试完成？**

答：测试耗时不稳定，HTTP 超时会导致客户端不知道任务是否已执行，Gateway 也容易被长请求占满。异步任务能返回 task_id，后续查询状态，并通过 lease 恢复 Worker 故障。

## 本章代码阅读任务

阅读顺序：先看请求 Schema，再看 owner 依赖、业务路由和 Worker 专用身份。

1. 打开 `backend/app/gateway/routers/code_change.py`，先看 `router = APIRouter(...)`，再看 `ProjectCreateRequest`、`TaskRunRequest`、`TaskResubmitRequest`、`TaskReviewRequest`。列出每个类允许的字段，确认项目创建不接受 `test_command`。
2. 接着看 `get_code_change_store`。只跟到可信 owner 的解析和 `CodeChangeStore(owner_id=owner_id)`，确认 owner 不来自 Body。
3. 再看 `create_project`、`run_project_task`、`get_project_task`、`review_project_task`。每个函数记录依赖、领域函数，以及 KeyError/ValueError 映射的 HTTP 状态码。
4. 最后看 `require_internal_worker` 和 `run_worker_once`，再跳到 `backend/app/gateway/code_change_worker_auth.py` 的 Worker token 判断函数。确认专用 token 与普通用户身份是两条权限域。

看到什么程度：给出 `POST /api/code-change/projects/demo/tasks`，能说出 Router 如何解析 patch_mode、怎样得到 owner、创建什么对象、为何先返回 `QUEUED`。

暂不要求：不追完整 JWT 签发、CSRF Middleware 和 FastAPI 线程池实现；只掌握 Code Change Router 的输入、依赖与错误映射。

验收动作：自己写四个 HTTP 请求样例，分别触发 200、400、403、409，并指出对应代码分支。

## 本章自测

1. Pydantic 校验为什么不能替代业务安全校验？
2. 认证、CSRF 和内部 Worker token 各解决什么？
3. `Depends(get_code_change_store)` 为什么与多租户有关？
4. 把阻塞文件操作改成 `async def` 为什么没有用？
5. HTTP 409 在本项目中表示什么？

## 参考答案

1. Pydantic 只能确认字段类型、长度和格式。字符串合法不代表它能安全地当命令或路径；profile、allowed root 和 owner 授权仍要由业务代码检查。
2. 认证确认终端用户是谁；CSRF 防止第三方网页借用户 Cookie 发起状态变更；Worker token 表示可信服务身份，防止普通用户领取和执行任务。
3. 它按可信用户创建 owner-scoped Store。Project 和 Task 的目录与查询都绑定 owner，避免所有请求共用不带用户范围的全局 Store。
4. Git、文件复制和 subprocess 仍是阻塞调用，放进 `async def` 仍会阻塞事件循环。正确做法是快速入队，让独立 Worker 执行。
5. 它表示资源当前状态不允许动作，例如未到 `HANDOFF_READY` 就审批，或不符合条件的 Task 提交修订 Patch。
