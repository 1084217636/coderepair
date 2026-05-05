# LangGraph 学习笔记

这份文档只服务于当前仓库，不追求大而全，目标是让你能：

1. 看懂现在的多智能体实现
2. 自己改 `planner / implementer / reviewer`
3. 能把这部分讲清楚写进简历

## 先学什么

只需要先掌握 4 个概念：

1. `State`
   共享状态，节点之间靠它传数据
2. `Node`
   每个节点做一件事，比如 planner 或 reviewer
3. `Edge`
   固定流转，比如 `planner -> implementer`
4. `Conditional Edge`
   条件流转，比如 reviewer 判定 `revise` 时回到 implementer

## 当前仓库里的对应关系

- LangGraph 实现入口：[core/multi_agent.py](/home/xiaobin/myproject/CodeRepair/core/multi_agent.py)
- CLI 入口：[app.py](/home/xiaobin/myproject/CodeRepair/app.py)
- 多智能体测试：[tests/test_multi_agent_flow.py](/home/xiaobin/myproject/CodeRepair/tests/test_multi_agent_flow.py)
- 阶段边界文档：[docs/MULTI_AGENT_BOUNDARY.md](/home/xiaobin/myproject/CodeRepair/docs/MULTI_AGENT_BOUNDARY.md)

## 你现在要能说出来的 3 句话

1. 当前多智能体是基于 LangGraph `StateGraph` 的最小 3 角色实现。
2. 图结构是 `planner -> implementer -> reviewer -> {END or implementer}`。
3. reviewer 的 `approve / revise` 决定是否进入下一轮修订。

## 代码里最值得先看的方法

按这个顺序读：

1. `MultiAgentCoordinator._build_graph`
2. `MultiAgentCoordinator._planner_node`
3. `MultiAgentCoordinator._implementer_node`
4. `MultiAgentCoordinator._reviewer_node`
5. `MultiAgentCoordinator._route_after_review`
6. `MultiAgentCoordinator.run`

## 学会后你应该能自己改什么

第一层：

- 改角色 prompt
- 改修订轮次
- 改 reviewer verdict 规则

第二层：

- 给不同角色分配不同 provider/model
- 给 reviewer 增加上下文压缩
- 给 planner 输出增加更细的 validation plan

第三层：

- 把 Docker 验证结果回注到 reviewer
- 把 Go AST 调用关系塞进 planner 上下文
- 把 Redis 用到多轮状态缓存里

## 当前不要钻太深的内容

这阶段先别花太多时间在：

- LangGraph 并行图
- 多子图嵌套
- 持久化 checkpoint
- 人机混合中断恢复
- 复杂 agent runtime

这些都不是你当前项目最短板。

## 学完怎么验证

最小验证：

```bash
./.venv/bin/python -m pytest tests/test_multi_agent_flow.py -q
```

主链验证：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "请分析 Calculate 函数的问题并给出修复建议" \
  --provider aicanapi \
  --model claude-sonnet-4-6 \
  --mode multi \
  --no-validate
```

## 官方资料

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph
- Graph API: https://docs.langchain.com/oss/python/langgraph/use-graph-api
- Workflows and agents: https://docs.langchain.com/oss/python/langgraph/workflows-agents
