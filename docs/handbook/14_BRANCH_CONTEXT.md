# 14 BranchContextBuilder：预算、裁剪与提示注入

Branch Context 按固定来源组合：

```text
Anchor（硬保留）
+ Root Summary（可截断）
+ 最近 Branch History（从尾部保留）
+ Code Context（按预算加入）
+ Current Question（硬保留）
```

当前实现用 `token_budget * 4` 近似字符预算。Anchor 或当前问题无法放入预算时直接报错，不能静默摘要；summary、history 与 code context 可以裁剪，并通过 `truncated` 明示。

## 为什么要 hard preserve

Anchor 是用户显式选中的讨论对象，Current Question 是当前意图。若它们被摘要或挤出窗口，分支功能就失去语义保证。Root Summary 和历史只是辅助来源，可以在预算不足时降级。

`to_prompt()` 使用 XML 风格边界，并声明应用提供内容是 context 而非 instructions。这能帮助模型区分来源，但不是完整 Prompt Injection 防线；代码与历史仍应视为不可信数据，Tool 层继续执行权限校验。

`read_code_context` 只读仓库相对路径和最多 120 行。当前是 deterministic bounded read，不是完整 RAG；`estimated_tokens=len(chars)//4` 也不是 provider 精确计费。

## 本章代码阅读任务

- 阅读顺序：`anchored_branch/context.py` 的 `read_code_context` → `BranchContextBuilder.build` → `BranchContext.to_prompt` → Router 的 `stream_branch_run` → `anchored_branch/middleware.py`。
- 看到什么程度：能手算固定预算下的保留顺序，并解释 prompt 进入模型前经过哪里。
- 暂不要求：不实现模型 tokenizer、语义压缩或 reranker。
- 验收动作：构造超长 history/code，验证 Anchor 与 Question 原样保留、旧 history 被裁剪且 `truncated=True`。

## 本章自测

1. 为什么“完整历史”不一定比 bounded context 好？
2. XML 标签能否彻底阻止 Prompt Injection？
3. 如何严谨评估这套 Context 策略？

## 参考答案

1. 它增加成本、延迟和无关信息，可能触发 lost-in-the-middle，让旧指令干扰当前问题。
2. 不能。标签只增强来源提示，真正安全还依赖输入处理、Tool 权限、输出验证和对抗测试。
3. 固定任务、模型、参数和工具，对照 Full History，测 token/延迟、Anchor/Question 保留、关键约束命中和人工正确性评分。
