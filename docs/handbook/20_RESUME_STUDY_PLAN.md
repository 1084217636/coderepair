# 20 AI 工程岗简历、面试题与六周计划

## 推荐项目定位

> CodeOps Agent 是基于 DeerFlow 2.0 二次开发的代码智能协作平台。主体是 Coding Agent 执行链和代码仓上下文增强，Anchored Branch 是解决长回答局部追问与 Main Context 膨胀的自研功能。

简历中的专业短版：

```text
基于 DeerFlow 二次开发 Client-Server Coding Agent。系统先从登记仓库构建受预算的相关代码上下文，再由受限 Agent 生成候选 Patch，并在独立 Workspace 中校验和测试；同时提供 Anchored Branch，让局部代码追问在 Child Thread 中运行而不污染 Main Thread。
```

简历正文建议使用三条：

- 打通 Requirement → Retrieval → Agent/Tool → Patch → Workspace → Test → Diff/Report 链路。12 个真实模型任务最终通过 10 个，通过率 83.33%。
- 实现 lexical + symbol + optional semantic 的轻量 Hybrid Code Retrieval 和 Token Budget Context Builder。12 个任务目标文件 Recall@5 为 100%，本次评测使用 lexical + symbol fallback。
- 实现 Anchored Branch Context。12 个同模型案例中，Anchored Context 正确率为 100%，平均 Prompt Token 比 Full History 少 10.32%；关闭 Branch 后 Main Thread 不变。

不能写：自研 DeerFlow/LangGraph、生产级分布式 Worker、自动创建合并 PR、在线模型高修复率、真实人工接受率或强容器 Sandbox。

## 六周学习计划

1. 第一周（00～04）：跑 Demo，补 Python async/FastAPI、LLM 消息、token、tool calling 基础。
2. 第二周（05～09）：追通 DeerFlow 请求，画 Agent Loop，读 State/Middleware/Memory/Skill/Sub-Agent。
3. 第三周（10～12）：读检索、Patch Agent、Workspace/Patch/Test，自己补一个负向测试。
4. 第四周（13～16）：操作 Branch、Context Isolation、三策略实验与安全边界，完成一次 threat model。
5. 第五周（17～19）：运行两组真实评测，分析两个失败任务，练两次故障排查，闭卷画三条调用链。
6. 第六周（20）：准备 1/3/10 分钟项目介绍，按岗位做两轮模拟面试和错题复盘。

每天至少输出一种证据：源码笔记、调用链图、测试、Benchmark 结果、故障 runbook 或口述录音。只阅读不输出很难应付追问。

六周计划完成后继续学习第 21 章，把依赖缺失、远端 CI、Agent 边界和项目与真实工作的差距整理成至少三篇故障复盘。学习档案不仅记录“会什么”，还要保留“问题怎样出现、证据怎样排除错误假设、修复后还剩什么风险”。

## AI 工程面试题纲

- LLM 的 context window、token、temperature、structured output 是什么？
- Agent 与 workflow 的区别？LangGraph State/Checkpoint 解决什么？
- Tool schema 如何设计？为什么 Tool call 不等于授权？
- Memory、Skill、RAG、Sub-Agent 与 Middleware 分别是什么？
- 如何处理 Prompt Injection、Tool 越权和无限循环？
- 如何评估检索、Agent trajectory、Patch 与最终回答？
- 为什么把概率性生成与确定性执行分开？
- 哪些来自 DeerFlow，哪些是你真正新增？

## 岗位匹配

这套项目适合 AI 应用工程、Agent 工程、LLM 平台应用层和 Python AI 后端。它不证明你具备预训练、CUDA、分布式训练、推理引擎或模型算法研究能力。投递 JD 若强调这些底层方向，需要另补数学、Transformer、PyTorch 与推理系统项目。

## 本章代码阅读任务

### 每次只审计一个简历动词

从简历中选择“设计、实现、接入、验证、优化”等一个具体动词：

> 我现在只审计这句简历表述：【粘贴一句】。请根据当前仓库真实代码，把它拆成需求、我的改动、上游复用、调用链、测试证据和当前边界。对每个涉及文件按关键函数分段解释，并指出面试官继续追问时我必须能写出的结构或伪代码。证据不足时直接降级措辞。最后给 60 秒回答、递进追问、评分标准和带答案的自测题。

一句通过后再审计下一句，不要用技术栈列表替代代码所有权。

- 阅读顺序：回看 `README_zh.md`，再按 `19_END_TO_END_CODE_MAP.md` 随机抽查源码；最后浏览 `backend/tests/code_change/` 选择能支撑每条简历描述的测试。
- 看到什么程度：每个简历动词都能对应实现、测试与边界；每个 AI 概念都能用本仓库举例。
- 暂不要求：不背没有亲自运行或阅读过的上游全部实现。
- 验收动作：录制三分钟项目介绍并接受二十分钟追问；无法在 30 秒内定位证据的“已实现”表述必须删除或降级。

## 本章自测

1. 学完这套手册后应达到什么 Agent 开发水平？
2. AI 工程岗与算法岗还差什么？
3. 怎样判断自己可以把项目写进简历？

## 参考答案

1. 能接入模型、设计受限 Tool、理解 Agent state/runtime、管理上下文、实现 HITL、安全边界、评测和调试，并能读懂 DeerFlow 对应源码；不是从零训练模型。
2. 算法岗通常还要求 Transformer/优化理论、数据与训练、PyTorch、论文复现；推理岗还可能要求 CUDA、量化、并行和服务优化。
3. 能独立运行、修改、测试、画链路，完成至少三篇真实故障复盘，并经两轮模拟面试仍不混淆上游/自研、当前/未来、测试/真实效果。
