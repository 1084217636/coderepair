# CodeRepair 文档入口

系统学习走 [CodeRepair AI 工程与 Agent 开发学习手册](handbook/README.md)，请从 00 章按编号读到 21 章。通勤和面试背诵使用 [CodeRepair 手机背诵手册](mobile_ai_interview/README.md)，其中已经写好可直接口述的 30 秒回答、详细回答、源码证据、技术选型和能力边界。`docs/coderepair/` 是开发阶段记录，不是另一套学习顺序。

`handbook/00_START_HERE.md` 到 `handbook/21_AI_ASSISTED_AGENT_DEVELOPMENT.md` 是当前唯一系统源码教材。手机手册只负责背诵和面试复述，不能替代第一次源码学习。系统手册最后一章专门记录 AI 辅助开发的真实故障、项目与公司工作的差异和面试口径。每章包含：

- 本章目标和第一次出现的概念。
- 当前方案解决的问题与选择理由。
- 精确到文件、类、函数或字段的代码阅读任务。
- 这次需要读到什么程度，以及暂时不用掌握什么。
- 章末自测题和同文件参考答案。

## 其他文档怎样看

`docs/` 根目录下其余 Markdown 多数是早期版本计划、阶段记录或旧面试稿。它们保留开发过程，但部分状态名和实现边界已经过期，不再作为学习入口。当前事实按以下顺序判断：

```text
当前代码和测试
→ docs/handbook
→ 根 README
→ 旧阶段文档
```

上游 DeerFlow 的通用安装和功能说明仍在根 README 的上游章节中。学习个人二开时要把上游能力与 `deerflow.code_change` 新增内容分开。
