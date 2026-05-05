# 7 天学习计划

目标：这周内把项目学到“能讲、能改、能面试”的程度。

每天按 `3-4 小时` 设计，顺序从“先会讲整体”到“能讲取舍和边界”。

## Day 1：整体流程

重点：

- 跑通单智能体主链
- 看懂 `app.py`
- 建立 10 个阶段的总地图

要读：

- [README.md](/home/xiaobin/myproject/CodeRepair/README.md)
- [SIMPLE_USAGE.md](/home/xiaobin/myproject/CodeRepair/SIMPLE_USAGE.md)
- [app.py](/home/xiaobin/myproject/CodeRepair/app.py)

要跑：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "请分析 Calculate 函数的问题并给出修复建议" \
  --no-validate
```

完成标准：

- 你能说出主链的 10 个阶段
- 你能解释 `01~10` artifacts 分别代表什么

## Day 2：检索与上下文增强

重点：

- 看懂 `PathFilter`
- 看懂 chunk、Hybrid RAG、工程文件支持
- 知道为什么平台不会把自己喂给模型

要读：

- [retrieval/filters.py](/home/xiaobin/myproject/CodeRepair/retrieval/filters.py)
- [retrieval/chunker.py](/home/xiaobin/myproject/CodeRepair/retrieval/chunker.py)
- [retrieval/retriever.py](/home/xiaobin/myproject/CodeRepair/retrieval/retriever.py)
- [docs/VECTOR_RAG.md](/home/xiaobin/myproject/CodeRepair/docs/VECTOR_RAG.md)

完成标准：

- 你能解释 PathFilter 的作用
- 你能解释为什么现在是 Hybrid RAG，不是纯向量检索

## Day 3：Go AST 与问题定位

重点：

- 看懂 Go 结构分析
- 看懂调用关系和依赖跨度
- 看懂 Go 预检规则

要读：

- [analyzers/go_ast.py](/home/xiaobin/myproject/CodeRepair/analyzers/go_ast.py)
- [validators/go_checker.py](/home/xiaobin/myproject/CodeRepair/validators/go_checker.py)

完成标准：

- 你能说出 AST 产出哪些结构信息
- 你能说出调用关系和依赖跨度为什么有用

## Day 4：多智能体与 LangGraph

重点：

- 看懂 LangGraph 在项目里到底用在哪
- 看懂 `planner / implementer / reviewer`
- 看懂 reviewer 回环

要读：

- [core/multi_agent.py](/home/xiaobin/myproject/CodeRepair/core/multi_agent.py)
- [docs/LANGGRAPH_LEARNING.md](/home/xiaobin/myproject/CodeRepair/docs/LANGGRAPH_LEARNING.md)
- [docs/MULTI_AGENT_BOUNDARY.md](/home/xiaobin/myproject/CodeRepair/docs/MULTI_AGENT_BOUNDARY.md)

完成标准：

- 你能解释 `LangGraph` 和 `StateGraph` 的关系
- 你能解释为什么主链不是全都交给 LangGraph

## Day 5：写回、验证、回滚

重点：

- 看懂为什么不是“直接改文件”
- 看懂本地 / Docker / auto 验证
- 看懂 backup/rollback 边界

要读：

- [executors/validator.py](/home/xiaobin/myproject/CodeRepair/executors/validator.py)
- [patcher/writer.py](/home/xiaobin/myproject/CodeRepair/patcher/writer.py)
- [sandbox/docker_runner.py](/home/xiaobin/myproject/CodeRepair/sandbox/docker_runner.py)
- [docs/DOCKER_SETUP.md](/home/xiaobin/myproject/CodeRepair/docs/DOCKER_SETUP.md)

完成标准：

- 你能完整讲出 `apply -> validate -> rollback`
- 你能说清楚为什么这是保守闭环

## Day 6：评估、benchmark 与可追问点

重点：

- 看懂单次运行评估
- 看懂 benchmark 套件
- 整理项目的取舍、失败和边界

要读：

- [evaluation/metrics.py](/home/xiaobin/myproject/CodeRepair/evaluation/metrics.py)
- [evaluation/benchmark_suite.py](/home/xiaobin/myproject/CodeRepair/evaluation/benchmark_suite.py)
- [docs/BENCHMARKING.md](/home/xiaobin/myproject/CodeRepair/docs/BENCHMARKING.md)
- [docs/INTERVIEW_GUIDE.md](/home/xiaobin/myproject/CodeRepair/docs/INTERVIEW_GUIDE.md)

要跑：

```bash
./.venv/bin/python scripts/run_benchmarks.py --provider groq --validation-mode local
```

完成标准：

- 你能说出这个项目怎么证明自己有用
- 你能说出 single 和 multi 怎么比较

## Day 7：简历与面试表达

重点：

- 固定项目边界
- 固定简历讲法
- 固定高频问答

要读：

- [docs/RESUME_PROJECT2.md](/home/xiaobin/myproject/CodeRepair/docs/RESUME_PROJECT2.md)
- [docs/PROJECT_STATUS.md](/home/xiaobin/myproject/CodeRepair/docs/PROJECT_STATUS.md)
- [docs/INTERVIEW_GUIDE.md](/home/xiaobin/myproject/CodeRepair/docs/INTERVIEW_GUIDE.md)

完成标准：

- 你能用 1 分钟讲清项目
- 你能回答 8 个高频追问
- 你能明确说出“做了什么”和“没做什么”

## 每天固定动作

1. 跑一组测试
2. 读一个核心模块
3. 看一个 artifact 目录
4. 用自己的话复述今天学到的内容

## 推荐的最小每日命令

```bash
./.venv/bin/python -m pytest \
  tests/test_app_cli_flow.py \
  tests/test_multi_agent_flow.py \
  tests/test_vector_retriever.py \
  -q
```
