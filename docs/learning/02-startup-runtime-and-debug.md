# 启动、运行与调试路线

文档对应提交：`7c9059b1`
生成或最后校验时间：2026-08-04
适用分支：`agent-code-change-platform`

## 阅读项

### HTTP 控制面

- 文件：`backend/app/gateway/routers/code_change.py`
- 符号：`router`、各 `@router` endpoint、`get_code_change_store`
- 阶段：第 1 遍，服务启动后先看请求如何变成 Project/Task。
- 问题：开关、鉴权、参数校验、入队和返回的 task_id 分别在哪里？

### Worker 主链

- 文件：`backend/packages/harness/deerflow/code_change/worker.py`
- 符号：`create_task`、`run_next_task`、`run_task_now`
- 阶段：第 1/3 遍。
- 问题：claim、状态迁移、workspace、Agent、Patch、测试、报告和 retry 的先后顺序是什么？Worker 崩溃后哪些状态可恢复？

### 状态与产物

- 文件：`models.py`、`state_machine.py`、`store.py`、`report_writer.py`、`pr_handoff.py`
- 符号：`TaskStatus`、`transition`、`CodeChangeStore`、报告写入函数
- 阶段：第 2/3 遍。
- 问题：哪些数据在 JSON/JSONL，哪些在 workspace？谁创建、谁读取、生命周期多长？

## 实际验证

先按仓库 README 完成配置和启动，再运行 `backend/tests/code_change` 相关测试。至少验证一次非法 Patch、测试命令超时或任务 retry，并检查 task timeline、audit 和 report；日志和产物不得包含 API key、Token 或原始敏感文件内容。
