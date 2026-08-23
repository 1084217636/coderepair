# 07 Tool Calling、Schema 与最小权限

Tool 是 Agent 与确定性世界之间的接口。好的 Tool 不是“给模型一个万能 shell”，而是围绕业务动作设计清晰 schema、权限、错误语义和可观察结果。

## Tool 设计检查表

1. 名称和 description 是否让模型知道何时调用？
2. 输入是否有类型、长度、枚举和路径范围？
3. Tool 是否只拥有完成动作所需的最小权限？
4. 返回值是否简洁、结构化，并避免把超长输出重新塞回上下文？
5. 调用是否幂等；若非幂等，是否有确认与去重键？
6. 异常是让 Run 失败，还是转换为模型可恢复的 ToolMessage？
7. 是否记录 tool name、参数摘要、耗时、结果状态与 token 影响？

## CodeRepair 的三个 Tool

- `code_change_search(query)`：从已扫描文件中召回相关上下文。
- `code_change_read_file(path, start_line, end_line)`：只读索引内的仓库相对路径并限制行数。
- `code_change_submit_patch(patch_text, rationale)`：只接受一次 typed unified diff，验证大小和路径，不执行 Patch。

这里最重要的是能力分离：模型可以“提议”，Worker 才能“应用与测试”。如果从最终自然语言中用正则抓 diff，就绕过了 Tool schema、单次提交和明确失败语义。

## 本章代码阅读任务

- 阅读顺序：`backend/packages/harness/deerflow/code_change/agent_patch.py` 的 `build_code_change_tools` → `agents/middlewares/tool_error_handling_middleware.py` → `tool_output_budget_middleware.py`。
- 看到什么程度：能为三个 Tool 写出输入约束、权限、输出和负向用例。
- 暂不要求：不学习所有 MCP 协议细节。
- 验收动作：设计一个“创建 PR”Tool schema，并说明为什么它必须比 search Tool 多确认和幂等字段。

## 本章自测

1. Tool schema 为什么不是安全边界的全部？
2. 为什么限制 Tool 输出长度？
3. 搜索、读取和 Patch 提交为什么不合成一个万能 Tool？

## 参考答案

1. schema 主要约束格式，应用还要做身份、资源范围、业务状态和内容校验。
2. 超长结果会挤占上下文、增加成本，并使模型忽略关键部分；应裁剪、分页或返回引用。
3. 分离后权限更小、失败更清晰、调用可审计，也能对每一步独立测试。
