# 测试指南

## 当前测试文件

当前仓库的测试集中在这些文件：

- `tests/test_artifact_manager.py`
- `tests/test_app_cli_flow.py`
- `tests/test_benchmark_suite.py`
- `tests/test_bootstrap.py`
- `tests/test_end_to_end_demo.py`
- `tests/test_go_checker.py`
- `tests/test_integration.py`
- `tests/test_langgraph_workflow.py`
- `tests/test_multi_agent_flow.py`
- `tests/test_patcher.py`
- `tests/test_path_filter.py`
- `tests/test_sandbox.py`

## 最推荐的测试方式

先跑这组，覆盖主流程且速度快：

```bash
./.venv/bin/python -m pytest \
  tests/test_artifact_manager.py \
  tests/test_app_cli_flow.py \
  tests/test_benchmark_suite.py \
  tests/test_patcher.py \
  tests/test_sandbox.py \
  tests/test_multi_agent_flow.py \
  tests/test_langgraph_workflow.py \
  tests/test_integration.py -q
```

我当前已经实跑通过：

- `tests/test_app_cli_flow.py tests/test_patcher.py tests/test_sandbox.py`: `23 passed, 3 skipped`
- `tests/test_multi_agent_flow.py tests/test_langgraph_workflow.py`: `12 passed`

如果你改了“项目自举开发”相关逻辑，顺手加跑：

```bash
./.venv/bin/python -m pytest tests/test_path_filter.py -q
```

## 想做更完整检查时

```bash
./.venv/bin/python -m pytest tests/ -v
```

如果你只想验证某一块：

```bash
./.venv/bin/python -m pytest tests/test_go_checker.py -v
./.venv/bin/python -m pytest tests/test_patcher.py -v
./.venv/bin/python -m pytest tests/test_sandbox.py -v
./.venv/bin/python -m pytest tests/test_vector_retriever.py -v
```

## Benchmark 验收

如果你想验证“这个项目不只是能跑，还能比较 single / multi 的效果”，跑：

```bash
./.venv/bin/python scripts/run_benchmarks.py --provider groq --validation-mode local --limit 2
```

运行后会在 `artifacts/benchmark_reports/` 下生成 `json + md` 报告。

## Docker 相关说明

`tests/test_sandbox.py` 中有一部分只依赖配置，另一部分依赖 Docker 环境。

如果本机没有 Docker，优先先跑：

```bash
./.venv/bin/python -m pytest tests/test_sandbox.py::TestSandboxConfig -v
```

## 面向用户的最小验收方式

作为用户使用时，最小验收建议直接跑主 CLI：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "请简要分析 Calculate 函数的问题并给出修复建议" \
  --provider aicanapi \
  --model claude-sonnet-4-6 \
  --validation-mode auto
```

如果你想验“写回失败自动回滚”这条链，推荐单独跑：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "修复 main.go 中的问题，并返回完整文件代码" \
  --apply-file main.go \
  --validation-mode auto
```

如果能看到 `07_validation_output.json`、`08_apply_result.json` 和最终摘要里的验证结果，就说明主链路是通的。

## Artifacts 过大怎么办

现在主 CLI 已支持自动清理旧 session。

最简单的临时控制方式：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "分析 Calculate 函数" \
  --artifacts-keep 10 \
  --artifacts-retention-days 7 \
  --no-validate
```

也可以在 `.env` 里固定：

```env
ARTIFACT_AUTO_CLEANUP=true
ARTIFACT_RETENTION_SESSIONS=20
ARTIFACT_RETENTION_DAYS=14
```

### 调试测试

```bash
# 显示打印语句
pytest tests/ -v -s

# 在第一个失败处停止
pytest tests/ -x -v

# 显示局部变量
pytest tests/ -v --tb=long

# 交互式调试
pytest tests/ --pdb -v
```

### 性能测试

```bash
# 显示最慢的 10 个测试
pytest tests/ --durations=10

# 只运行标记为 slow 的测试
pytest tests/ -m "slow" -v
```

---

## ✅ 测试执行检查表

在提交前确保：

- [ ] 所有测试通过: `pytest tests/ -v`
- [ ] 无 lint 错误: （如果有 pylint）
- [ ] 覆盖率 > 80%: `pytest tests/ --cov --cov-report=term`
- [ ] 无警告信息: `pytest tests/ -W default`
- [ ] 集成测试通过: `pytest tests/ -m "integration" -v`

---

## 🔧 故障排查

### 测试找不到模块

```
ImportError: No module named 'bootstrap'
```

**解决方案**:
```bash
# 确保在项目根目录运行
cd /home/xiaobin/myproject/CodeRepair
pytest tests/
```

### Docker 测试失败

```
RuntimeError: Docker not available
```

**解决方案**:
```bash
# 跳过 Docker 测试
pytest tests/ -m "not docker" -v

# 或安装 Docker
# Linux: https://docs.docker.com/engine/install/
# Mac: brew install docker
```

### 权限错误

```
PermissionError: [Errno 13] Permission denied
```

**解决方案**:
```bash
# 确保有写入权限
chmod -R u+w tests/

# 或使用 sudo（不推荐）
sudo pytest tests/
```

### 超时错误

```
TimeoutExpired: command timed out
```

**解决方案**:
```bash
# 增加超时时间
pytest tests/ --timeout=600 -v
```

---

## 📚 参考

- [Pytest 文档](https://docs.pytest.org/)
- [Python unittest](https://docs.python.org/3/library/unittest.html)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/reference.html#fixtures)

---

**最后更新**: 2026-03-31
