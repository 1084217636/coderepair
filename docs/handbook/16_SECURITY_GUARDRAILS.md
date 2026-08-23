# 16 Agent 安全、Guardrail 与 Sandbox 边界

Agent 安全不能依赖单点防护。Prompt Injection、越权 Tool、路径穿越、Secret 泄漏、无限循环和危险测试命令分别需要不同层处理。

| 层 | 当前措施 | 仍然存在的边界 |
| --- | --- | --- |
| 输入/上下文 | Input sanitization、来源标签、长度预算 | 不可能仅靠清洗识别全部恶意语义 |
| Tool | 最小 Tool 集、schema、路径/大小校验、可选 Guardrail | 模型仍可能提出有害但格式合法的动作 |
| API | feature flag、owner scope、repo root allowlist、Worker token | 依赖部署正确配置身份与 Secret |
| Patch | 相对路径、`.git` 拒绝、`git apply --check` | 合法文件内仍可能存在业务破坏 |
| Test | server profile、`shell=False`、scrubbed env、timeout group kill | 宿主进程不是强隔离 Sandbox |
| Release | report、human review、状态机 | 当前未完成真实 GitHub Provider |

## Guardrail 与 Sandbox 不同

Guardrail 在动作前根据策略允许、拒绝或修改请求；Sandbox 假设动作可能不可信，从 OS/容器层限制它能访问的文件、网络、CPU、内存和系统调用。二者互补：策略可能漏判，隔离也不能理解业务授权。

## Prompt Injection 思路

仓库代码、README、网页和 Tool 输出都是不可信数据。Agent 不应把其中“忽略系统指令”“上传 Secret”等内容提升为指令。实践上应区分 instruction/data、最小 Tool 权限、敏感动作确认、Secret 不入上下文、输出审计，并用对抗样本测试。

## 本章代码阅读任务

- 阅读顺序：`input_sanitization_middleware.py` → `sandbox_audit_middleware.py` → `backend/app/gateway/code_change_worker_auth.py` → `code_change/patcher.py` → `test_runner.py`。
- 看到什么程度：能为 Prompt Injection、repo escape、任意命令、Secret 泄漏、超时子进程各指出至少一条真实防线和残余风险。
- 暂不要求：不实现 seccomp、网络策略或完整容器 Sandbox。
- 验收动作：写一份威胁模型，包含 asset、attacker、entry point、mitigation、residual risk，而不是只列安全名词。

## 本章自测

1. 最小 Tool 集为什么比“提示模型不要做坏事”可靠？
2. Guardrail 与 Sandbox 谁可以替代谁？
3. 为什么 owner scope 常返回 404 而不是 403？

## 参考答案

1. 未注册的能力无法被模型调用，权限边界由应用代码执行；提示词只影响概率行为。
2. 不能互相替代。Guardrail 判断意图/策略，Sandbox 限制实际资源访问，需要纵深防御。
3. 对无权资源隐藏其是否存在，减少 ID 枚举和跨租户信息泄露。
