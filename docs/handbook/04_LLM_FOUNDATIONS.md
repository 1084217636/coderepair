# 04 LLM API、消息、Token 与结构化输出

Agent 的底层仍是语言模型调用。面试时至少要能解释输入如何组成、输出为什么不稳定、上下文为什么有成本，以及结构化输出怎样降低解析歧义。

## 一次模型调用

输入通常由 System、Human、AI、Tool 四类消息组成。模型根据已有消息预测下一段 token；temperature 等采样参数影响随机性，但不能提供权限保证。上下文窗口同时容纳提示词、历史消息、Tool 结果和模型输出预算。

关键概念：

- Token 不是字符；不同模型和语言的切分不同。
- Context window 是单次请求可见范围，不等于长期记忆。
- System prompt 提供行为约束，但不是安全隔离。
- Tool call 是模型生成的结构化调用意图，应用仍要校验参数并决定是否执行。
- Structured output / schema 能减少自由文本解析，但仍需处理缺字段、类型错误、拒答和截断。
- 幻觉来自模型按概率生成看似合理内容；Grounding、Tool、引用与验证只能降低风险，不能保证为零。

## 成本与延迟

输入越长通常 token 成本和首 token 延迟越高。Agent 还会多轮调用模型和 Tool，因此总成本约等于各轮输入/输出 token 与工具执行的累积，而不是一次聊天价格。Prompt cache、摘要、检索和 Tool 输出裁剪都是上下文工程手段。

## 与本项目的关系

CodeRepair 不相信模型文本中的“已经修改、已经测试”，而只接受 typed `code_change_submit_patch`。Anchored Context 控制送入模型的历史范围；TokenUsage/TokenBudget Middleware 则处理通用 Agent 的预算与统计。

## 本章代码阅读任务

- 阅读顺序：`backend/packages/harness/deerflow/models/` → `agents/lead_agent/prompt.py` → `agents/middlewares/token_usage_middleware.py` 与 `token_budget_middleware.py`。
- 看到什么程度：能指出模型配置、system prompt、消息列表和 token 预算在不同层的职责。
- 暂不要求：不学习 Transformer 数学推导、训练或 GPU 推理优化。
- 验收动作：拿一个 Tool 调用例子，写出模型看到的消息顺序以及下一轮为什么能读到 Tool 结果。

## 本章自测

1. Context window 与长期 Memory 有什么区别？
2. temperature 设为 0 是否保证绝对确定？
3. 为什么 typed Tool 仍需要服务端校验？

## 参考答案

1. Context window 是本次请求的有限输入；长期 Memory 持久保存筛选后的信息，并在未来请求中重新注入。
2. 不保证。服务端实现、模型版本、并行计算和工具环境仍可能带来差异。
3. 模型可能传入越权路径、超大内容或不合法类型；schema 改善格式，不替代授权和业务规则。
