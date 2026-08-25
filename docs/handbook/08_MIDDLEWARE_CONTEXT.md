# 08 Middleware 与 Context Engineering

Prompt Engineering 关注“怎么写提示”；Context Engineering 关注“这一轮模型究竟看到哪些指令、历史、工具、文件、记忆和运行状态”。Agent 工程中，后者往往更决定稳定性与成本。

Middleware 在模型或 Tool 调用前后统一处理横切逻辑，例如：

- 输入净化与 system message 合并。
- 动态日期、Memory、Skill 和 Branch Context 注入。
- Tool 输出裁剪、token 预算与用量统计。
- Tool 权限、审计、错误转换和循环检测。
- 摘要、dangling Tool call 修复与安全结束原因。

顺序很重要：输入应先净化；权限检查必须发生在 Tool 副作用之前；Tool 输出要在重新进入模型前裁剪；摘要不能丢掉 durable goal、delegation 或当前 Anchor。

## 上下文来源与优先级

```text
static system prompt
+ current user message
+ bounded recent history / summary
+ durable memory and active skill
+ retrieved code/tool results
+ request-scoped branch context
```

更多上下文不一定更好。常见问题包括 lost-in-the-middle、重复指令、旧结论污染、Tool 输出淹没当前问题和提示注入。应使用来源标记、预算、硬保留字段、裁剪与评测控制。

## 本章代码阅读任务

### 一次只学一个 Middleware

先问 Agent 怎样组装 Middleware，然后对每个 Middleware 单独使用下面问题：

> 我现在只学习【当前 Middleware 类】。请先说明它在模型调用或 Tool 调用的前后哪个时点执行，再按方法逐段解释接收的 request/state、读取的字段、触发条件、产生的修改和交给下一层的对象。给出执行前与执行后的消息或上下文示例，并说明它和前后 Middleware 的顺序依赖、失败或误裁剪风险。最后写出对应测试思路、看到什么程度就停和 3 道带答案的自测题。

每次回答只展开一个 Middleware，不把所有上下文工程概念揉在一起。

- 阅读顺序：`backend/packages/harness/deerflow/agents/lead_agent/agent.py` 的 Middleware 组装 → `backend/packages/harness/deerflow/agents/middlewares/input_sanitization_middleware.py` → `backend/packages/harness/deerflow/agents/middlewares/tool_output_budget_middleware.py` → `backend/packages/harness/deerflow/agents/middlewares/summarization_middleware.py` → `backend/packages/harness/deerflow/anchored_branch/middleware.py`。
- 看到什么程度：能解释至少五个 Middleware 的触发点、输入、输出和顺序依赖。
- 暂不要求：不背所有 Middleware 类名。
- 验收动作：给“超长 Tool 输出导致当前问题消失”设计一条 Middleware 处理链和回归测试。

## 本章自测

1. Prompt Engineering 与 Context Engineering 的区别是什么？
2. 为什么不能把 Branch Context 永久写成 HumanMessage？
3. Middleware 顺序错误可能造成什么安全问题？

## 参考答案

1. 前者优化指令表达，后者管理模型本轮看到的全部信息来源、预算、生命周期和权限。
2. 它是应用构造的本次运行上下文，不是用户原话；永久写入会污染历史并在后续重复放大。
3. 例如先执行 Tool 后鉴权就已经产生副作用；先摘要后保存 durable 信息可能永久丢失约束。
