from __future__ import annotations

from pathlib import Path

from deerflow.code_change.models import CodeFile

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".deer-flow"}
LANG_BY_SUFFIX = {
    ".go": "go",
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


def scan_repo(repo_path: str, max_files: int = 500) -> list[CodeFile]:
    root = Path(repo_path).resolve()
    files: list[CodeFile] = []
    for path in sorted(root.rglob("*")):
        if len(files) >= max_files:
            break
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        language = LANG_BY_SUFFIX.get(path.suffix.lower())
        if language is None:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        summary = first_non_empty_lines(text)
        files.append(CodeFile(path=str(rel), language=language, size=path.stat().st_size, summary=summary))
    return files


def first_non_empty_lines(text: str, limit: int = 3) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines[:limit])[:240]
