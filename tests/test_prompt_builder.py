from llm.prompt_builder import PromptBuilder


def test_prompt_builder_uses_structured_evidence_fusion():
    builder = PromptBuilder("bug_fix", "go")

    prompt = builder.build_user_prompt(
        user_query="修复 CreateUser 逻辑错误",
        analysis_info={
            "package": "service",
            "language": "go",
            "imports": ["context", "fmt", "errors"],
            "functions": ["CreateUser", "DeleteUser"],
            "methods": ["Service.Validate"],
            "types": ["Service", "User"],
            "dependency_span": {"local_imports": 2, "external_imports": 1},
        },
        retrieval_results=[
            {
                "relative_path": "Dockerfile",
                "language": "dockerfile",
                "text": "FROM golang:1.22\nWORKDIR /app\n",
                "start_line": 1,
                "end_line": 2,
                "summary": "Dockerfile:1",
                "chunk_kind": "window",
            },
            {
                "relative_path": "service/user.go",
                "language": "go",
                "text": "func CreateUser() error {\n    return nil\n}\n",
                "start_line": 10,
                "end_line": 12,
                "summary": "func CreateUser",
                "chunk_kind": "function",
                "symbol": "CreateUser",
                "score": 0.91,
            },
        ],
    )

    assert "## 仓库事实" in prompt
    assert "## 主证据" in prompt
    assert "## 补充证据" in prompt
    primary_section = prompt.split("## 主证据", 1)[1].split("## 补充证据", 1)[0]
    supporting_section = prompt.split("## 补充证据", 1)[1]
    assert "service/user.go" in primary_section
    assert "Dockerfile" in supporting_section
    assert "命中信息" in prompt
