"""
主流程最小可用性测试
"""
import json

from pathlib import Path

from app import CodeRepairPlatform
from executors.validator import ValidationResult, Validator
from llm.client import LLMClient
from config import settings


def _create_minimal_go_project(workspace: Path) -> None:
    """创建最小 Go 项目"""
    (workspace / "go.mod").write_text(
        "module github.com/test/appflow\n\ngo 1.21\n",
        encoding="utf-8",
    )
    (workspace / "main.go").write_text(
        "package main\n\nfunc main() {\n    println(\"old\")\n}\n",
        encoding="utf-8",
    )


def test_platform_can_apply_generated_file(monkeypatch, tmp_path):
    """显式传入 apply_file 时，主流程可以写回完整代码块"""
    _create_minimal_go_project(tmp_path)

    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": """修复如下：

```go
package main

func main() {
    println("new")
}
```""",
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    platform = CodeRepairPlatform(provider="openai", model="fake-model")
    result = platform.run(
        user_input="修复 main.go",
        workspace_root=str(tmp_path),
        validate=False,
        apply_file="main.go",
    )

    assert result["apply_output"]["status"] == "applied"
    assert 'println("new")' in (tmp_path / "main.go").read_text(encoding="utf-8")


def test_platform_can_apply_engineering_file(monkeypatch, tmp_path):
    """Go workspace 下也可以写回 Dockerfile 这类工程文件。"""
    _create_minimal_go_project(tmp_path)
    (tmp_path / "Dockerfile").write_text("FROM alpine:3.18\n", encoding="utf-8")

    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": """```dockerfile
FROM golang:1.22
WORKDIR /app
COPY . .
RUN go build ./...
```""",
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    platform = CodeRepairPlatform(provider="ollama", model="llama3")
    result = platform.run(
        user_input="优化 Dockerfile",
        workspace_root=str(tmp_path),
        validate=False,
        apply_file="Dockerfile",
    )

    assert result["apply_output"]["status"] == "applied"
    assert "FROM golang:1.22" in (tmp_path / "Dockerfile").read_text(encoding="utf-8")


def test_platform_skips_mock_apply(monkeypatch, tmp_path):
    """mock 回复默认不允许自动写回文件"""
    _create_minimal_go_project(tmp_path)

    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": """```go
package main

func main() {
    println("should-not-apply")
}
```""",
            "model": "fake-model",
            "stop_reason": "mock",
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    platform = CodeRepairPlatform(provider="openai", model="fake-model")
    result = platform.run(
        user_input="修复 main.go",
        workspace_root=str(tmp_path),
        validate=False,
        apply_file="main.go",
    )

    assert result["apply_output"]["status"] == "skipped"
    assert result["apply_output"]["reason"] == "mock_response"
    assert 'println("old")' in (tmp_path / "main.go").read_text(encoding="utf-8")


def test_filter_scan_result_can_focus_single_file(tmp_path):
    """focus_file 可以将扫描范围收敛到单个文件"""
    file_a = tmp_path / "a.py"
    file_b = tmp_path / "b.py"
    file_a.write_text("print('a')\n", encoding="utf-8")
    file_b.write_text("print('b')\n", encoding="utf-8")

    platform = CodeRepairPlatform()
    scan_result = {
        "workspace_root": str(tmp_path),
        "total_files": 2,
        "go_files": 0,
        "py_files": 2,
        "files": [file_a, file_b],
        "go_files_list": [],
        "py_files_list": [file_a, file_b],
    }

    filtered = platform._filter_scan_result(scan_result, tmp_path, "a.py")

    assert filtered["total_files"] == 1
    assert filtered["py_files"] == 1
    assert filtered["files"] == [file_a]
    assert filtered["py_files_list"] == [file_a]
    assert filtered["focus_file"] == "a.py"


def test_filter_scan_result_can_focus_directory(tmp_path):
    """focus_file 也可以收敛到某个目录"""
    target_dir = tmp_path / "pkg"
    other_dir = tmp_path / "other"
    target_dir.mkdir()
    other_dir.mkdir()
    file_a = target_dir / "a.py"
    file_b = target_dir / "b.py"
    file_c = other_dir / "c.py"
    file_a.write_text("print('a')\n", encoding="utf-8")
    file_b.write_text("print('b')\n", encoding="utf-8")
    file_c.write_text("print('c')\n", encoding="utf-8")

    platform = CodeRepairPlatform()
    scan_result = {
        "workspace_root": str(tmp_path),
        "total_files": 3,
        "go_files": 0,
        "py_files": 3,
        "files": [file_a, file_b, file_c],
        "go_files_list": [],
        "py_files_list": [file_a, file_b, file_c],
    }

    filtered = platform._filter_scan_result(scan_result, tmp_path, "pkg")

    assert filtered["total_files"] == 2
    assert filtered["py_files"] == 2
    assert filtered["files"] == [file_a, file_b]
    assert filtered["focus_file"] == "pkg"


def test_apply_file_cannot_escape_workspace(tmp_path):
    """apply_file 会拒绝通过相对路径逃逸 workspace。"""
    platform = CodeRepairPlatform()

    try:
        platform._normalize_apply_path(tmp_path, "../outside.go")
    except ValueError as exc:
        assert "workspace" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_platform_rolls_back_when_validation_fails(monkeypatch, tmp_path):
    """写回后验证失败时，默认自动回滚到备份版本。"""
    _create_minimal_go_project(tmp_path)

    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": """```go
package main

func main() {
    println("broken")
}
```""",
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    def fake_validation(self, workspace_path, language, validation_mode, validate_cmd=None):
        return ValidationResult(
            success=False,
            source="local",
            stage="build",
            exit_code=1,
            stderr="build failed",
            duration=0.01,
        ).to_dict()

    monkeypatch.setattr(LLMClient, "call", fake_call)
    monkeypatch.setattr(CodeRepairPlatform, "_run_validation", fake_validation)

    platform = CodeRepairPlatform(provider="aicanapi", model="claude-sonnet-4-6")
    result = platform.run(
        user_input="修复 main.go",
        workspace_root=str(tmp_path),
        validate=True,
        apply_file="main.go",
    )

    assert result["apply_output"]["status"] == "rolled_back"
    assert result["apply_output"]["rollback_output"]["status"] == "success"
    assert 'println("old")' in (tmp_path / "main.go").read_text(encoding="utf-8")


def test_platform_auto_validation_falls_back_to_local(monkeypatch, tmp_path):
    """auto 模式下 Docker 不可用时，会自动降级到本地验证。"""
    _create_minimal_go_project(tmp_path)

    def fake_run_go_build(self):
        return ValidationResult(
            success=True,
            source="local",
            stage="build",
            exit_code=0,
            stdout="ok",
            duration=0.01,
        )

    monkeypatch.setattr("app.DockerRunner.try_create", classmethod(lambda cls, docker_client_cmd="docker": (None, "docker missing")))
    monkeypatch.setattr(Validator, "run_go_build", fake_run_go_build)

    platform = CodeRepairPlatform()
    result = platform.run(
        user_input="检查当前项目",
        workspace_root=str(tmp_path),
        validate=True,
        validation_mode="auto",
    )

    assert result["validation_output"]["success"] is True
    assert result["validation_output"]["source"] == "local"
    assert "docker missing" in result["validation_output"]["fallback_reason"]


def test_platform_persists_evaluation_artifact(monkeypatch, tmp_path):
    """主流程会额外保存一次运行评估产物。"""
    _create_minimal_go_project(tmp_path)

    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": "这是一次分析结果，不需要修改文件。",
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    platform = CodeRepairPlatform(provider="aicanapi", model="claude-sonnet-4-6")
    result = platform.run(
        user_input="分析当前项目的入口和主流程",
        workspace_root=str(tmp_path),
        validate=False,
    )

    evaluation_path = settings.ARTIFACTS_ROOT / f"session_{result['session_id']}" / "10_evaluation.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    session_dir = settings.ARTIFACTS_ROOT / f"session_{result['session_id']}"

    assert evaluation_path.exists()
    assert evaluation["execution_mode"] == "single"
    assert "retrieval_hit_rate" in evaluation
    assert result["evaluation_output"]["rag_backend"] == evaluation["rag_backend"]
    assert (session_dir / "task_report.md").exists()
    assert (session_dir / "patch.diff").exists()
    assert (session_dir / "validate.log").exists()
    assert (session_dir / "review.json").exists()
    summary_path = session_dir / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["task_type"] == result["task_type"]
    assert "manual_review_required" in summary
    tool_calls_path = session_dir / "tool_calls.json"
    assert tool_calls_path.exists()
    tool_calls = json.loads(tool_calls_path.read_text(encoding="utf-8"))
    assert tool_calls["call_count"] >= 5
    assert "repository_scan" in {item["name"] for item in tool_calls["calls"]}


def test_platform_marks_apply_as_unverified_when_docker_requested_but_unavailable(monkeypatch, tmp_path):
    """显式要求 docker 验证且 Docker 不可用时，写回结果应标记为未验证。"""
    _create_minimal_go_project(tmp_path)

    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": """```go
package main

func main() {
    println("new")
}
```""",
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)
    monkeypatch.setattr("app.DockerRunner.try_create", classmethod(lambda cls, docker_client_cmd="docker": (None, "docker missing")))

    platform = CodeRepairPlatform(provider="aicanapi", model="claude-sonnet-4-6")
    result = platform.run(
        user_input="修复 main.go",
        workspace_root=str(tmp_path),
        validate=True,
        apply_file="main.go",
        validation_mode="docker",
    )

    assert result["apply_output"]["status"] == "applied_unverified"
    assert result["validation_output"]["source"] == "skipped"
    assert "docker missing" in result["validation_output"]["skipped_reason"]
    assert 'println("new")' in (tmp_path / "main.go").read_text(encoding="utf-8")
