# DeerFlow 二开项目学习入口

这套资料已经覆盖项目定位、DeerFlow 原结构、二开动机、代码地图、任务状态机、Worker、Patch/Test、沙箱、RAG、PR handoff、测试证据、简历表达和面试题。

## 建议顺序

1. `FINAL_PROJECT_LEARNING_PACKAGE.md`：先背完整项目闭环。
2. `COMPANY_DEPLOYMENT_AND_INTERVIEW.md`：建立公司多服务器部署口径，并分清已实现与演进设计。
3. `DEERFLOW_CODE_MAP.md`：理解 DeerFlow 原结构和二开位置。
4. `CODE_CHANGE_SUMMARY_BY_FILE.md`：掌握自己新增的文件与职责。
5. `DEERFLOW_MODULE_CARDS.md`：按模块复习。
6. `FINAL_DEMO_CASES.md`、`DEERFLOW_TEST_EVIDENCE.md`：掌握证据。
7. `FINAL_RESUME_AND_INTERVIEW_PACK.md`、`DEERFLOW_INTERVIEW_QA.md`：背简历和追问。
8. `PERFORMANCE_AND_EVOLUTION.md`：学习生产化演进。

## 统一口径

面试时先讲公司目标架构：多 API Gateway、多 Worker、共享 PostgreSQL/任务队列、对象存储、短生命周期容器沙箱。随后必须主动说明当前仓库真实版本使用 JSON/JSONL 持久化、原子 claim/lease 和本地隔离 workspace，目标架构中的 PostgreSQL、Redis Stream、Docker/K8s Sandbox 尚未全部实现。

“公司场景作为默认思考方式”不等于把未来设计冒充当前代码。面试回答固定分三层：当前实现、为什么这样设计、生产环境怎样演进。
