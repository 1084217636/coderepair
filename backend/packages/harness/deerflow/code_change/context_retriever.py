from __future__ import annotations

import re
from pathlib import Path

from deerflow.code_change.models import CodeFile, RetrievedContext


def retrieve_context(repo_path: str, requirement: str, files: list[CodeFile], limit: int = 5) -> list[RetrievedContext]:
    terms = tokenize(requirement)
    root = Path(repo_path)
    scored: list[RetrievedContext] = []
    for item in files:
        path_score = sum(3 for term in terms if term in item.path.lower())
        summary_score = sum(2 for term in terms if term in item.summary.lower())
        text = ""
        try:
            text = (root / item.path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            pass
        content_score = sum(1 for term in terms if term in text.lower())
        score = path_score + summary_score + content_score
        if score <= 0 and item.language in {"go", "python"}:
            score = 1
        if score <= 0:
            continue
        scored.append(
            RetrievedContext(
                path=item.path,
                score=score,
                reason=f"path={path_score}, summary={summary_score}, content={content_score}",
                snippet=text[:800],
            )
        )
    scored.sort(key=lambda ctx: (-ctx.score, ctx.path))
    return scored[:limit]


def tokenize(text: str) -> set[str]:
    terms = {token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", text)}
    for segment in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", text):
        terms.add(segment)
        for width in (2, 3):
            terms.update(segment[index : index + width] for index in range(len(segment) - width + 1))
    return terms
