# 多智能体阶段边界

这份文档定义“当前这一阶段的多智能体部分做到什么程度算完成”，目的是防止目标不断膨胀。

## 当前阶段名称

当前阶段按 **基于 LangGraph 的多智能体 MVP+** 处理，不按“成熟 agent 平台”处理。

## 这一阶段必须完成的范围

下面这些能力全部具备，才算本阶段完成：

1. 保留单智能体主链，`--mode single` 仍然稳定可用。
2. `--mode multi` 可切换到 `planner -> implementer -> reviewer` 串行协作链。
3. reviewer 可以给出 `approve / revise`，并触发有限轮次修订。
4. 多智能体链使用 LangGraph `StateGraph` 实现最小状态图和 reviewer 条件回环。
5. 多智能体链和单智能体链共用同一套写回、验证、回滚与 artifacts 机制。
6. 多智能体执行轨迹可以落盘，至少输出 JSON 和 Markdown 两份 trace。
7. mock 回退、reviewer 缺失 verdict、provider 偶发失败这些常见异常有保守处理。
8. 有最小测试覆盖多智能体修订轮次、主链切换、写回/验证/回滚不回归。

## 这一阶段明确不做的范围

下面这些内容全部视为下一阶段，不纳入当前完成标准：

1. 真正并行的多 agent 执行。
2. 独立进程、消息总线、任务队列、Redis 协调。
3. 复杂并行图、消息总线式 LangGraph agent graph 落地。
4. 长时间自治循环、自主拆分子任务、自主调用大量工具。
5. 多文件 patch 规划器和复杂冲突合并器。
6. 自动把所有 reviewer 意见都转成代码修改。
7. 面向生产级别的成本调度、配额治理、熔断和观测平台。

## 当前阶段的验收标准

满足下面这些，就按“阶段完成”处理：

1. `./.venv/bin/python app.py --mode multi ...` 可以稳定产出结果摘要。
2. reviewer 触发 revise 时，链路能完成至少一轮修订。
3. `04_multi_agent_trace.json` 和 `04_multi_agent_trace.md` 会落到 artifacts。
4. 多智能体模式下如果返回完整文件代码块，仍可复用 `--apply-file` 和验证/回滚闭环。
5. 关键测试通过，至少覆盖：
   - `tests/test_multi_agent_flow.py`
   - `tests/test_app_cli_flow.py`
   - `tests/test_langgraph_workflow.py`
6. 至少有一条真实 provider 的 smoke test 能跑通；mock 回退不能算阶段完成。

## 对简历可写到什么程度

当前阶段可以写：

- 已实现基于 LangGraph `StateGraph` 的 `planner / implementer / reviewer` 多智能体 MVP
- 支持 reviewer 驱动的有限轮次修订
- 支持多智能体执行轨迹留痕
- 多智能体与单智能体共用写回、验证、回滚闭环

当前阶段不要写：

- 已实现成熟多智能体平台
- 已实现并行 agent 协作系统
- 已接入 Redis 驱动的 agent 调度
- 已完整落地 LangGraph 多智能体图

## 下一阶段再做什么

只有当前阶段验收完成后，才进入下一阶段。下一阶段优先级按下面顺序走：

1. 每个角色可独立选择 provider/model
2. reviewer 上下文压缩与失败重试
3. Docker 验证在 multi 模式下作为正式主链
4. 更强的 Go AST 调用关系与依赖跨度分析
5. 更强的代码/文档 RAG
