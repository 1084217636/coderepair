from __future__ import annotations

import ast
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path

from deerflow.code_change.embeddings import EmbeddingProvider, embedding_provider_from_env
from deerflow.code_change.models import CodeFile, RetrievedContext

logger = logging.getLogger(__name__)

CHUNK_LINES = 120
CHUNK_OVERLAP = 20


@dataclass(frozen=True, slots=True)
class CodeChunk:
    path: str
    language: str
    start_line: int
    end_line: int
    text: str
    symbols: tuple[str, ...]


@dataclass(slots=True)
class RetrievalContextBundle:
    items: list[RetrievedContext]
    prompt: str
    estimated_tokens: int
    truncated: bool


def retrieve_context(
    repo_path: str,
    requirement: str,
    files: list[CodeFile],
    limit: int = 5,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[RetrievedContext]:
    """Retrieve explainable code chunks using lexical, symbol and semantic signals."""

    terms = tokenize(requirement)
    chunks = _load_chunks(Path(repo_path), files)
    if not chunks or not terms:
        return []

    lexical_raw = [_lexical_score(chunk, terms) for chunk in chunks]
    symbol_raw = [_symbol_score(chunk, terms) for chunk in chunks]
    lexical = _normalize(lexical_raw)
    symbols = _normalize(symbol_raw)
    semantic, semantic_available = _semantic_scores(requirement, chunks, embedding_provider)

    scored: list[RetrievedContext] = []
    for index, chunk in enumerate(chunks):
        if semantic_available:
            fused = 0.45 * lexical[index] + 0.30 * symbols[index] + 0.25 * semantic[index]
            semantic_reason = f"{semantic[index]:.3f}"
        else:
            fused = 0.65 * lexical[index] + 0.35 * symbols[index]
            semantic_reason = "unavailable"
        if fused <= 0:
            continue
        snippet = chunk.text[:6_000]
        scored.append(
            RetrievedContext(
                path=chunk.path,
                score=round(fused, 6),
                reason=(f"lexical={lexical[index]:.3f}, symbol={symbols[index]:.3f}, semantic={semantic_reason}; lines={chunk.start_line}-{chunk.end_line}"),
                snippet=snippet,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                symbols=list(chunk.symbols),
                lexical_score=round(lexical[index], 6),
                symbol_score=round(symbols[index], 6),
                semantic_score=round(semantic[index], 6) if semantic_available else 0.0,
                estimated_tokens=max(1, len(snippet) // 4),
            )
        )
    scored.sort(key=lambda item: (-item.score, item.path, item.start_line))
    return scored[: max(1, limit)]


def build_retrieval_context(contexts: list[RetrievedContext], *, token_budget: int = 4_000) -> RetrievalContextBundle:
    """Pack ranked chunks into an explainable prompt without copying the repository."""

    if token_budget < 128:
        raise ValueError("retrieval token_budget must be at least 128")
    budget_chars = token_budget * 4
    prefix = "<retrieved_code_context>\n"
    suffix = "</retrieved_code_context>"
    used = len(prefix) + len(suffix)
    selected: list[RetrievedContext] = []
    sections: list[str] = []
    truncated = False
    for context in contexts:
        header = f'<code_chunk path="{context.path}" lines="{context.start_line}-{context.end_line}" score="{context.score:.4f}" reason="{context.reason}">\n'
        footer = "\n</code_chunk>\n"
        available = budget_chars - used - len(header) - len(footer)
        if available <= 0:
            truncated = True
            break
        snippet = context.snippet[:available]
        if len(snippet) < len(context.snippet):
            truncated = True
        if not snippet.strip():
            break
        sections.append(f"{header}{snippet}{footer}")
        selected.append(context)
        used += len(header) + len(snippet) + len(footer)
        if truncated:
            break

    prompt = f"{prefix}{''.join(sections)}{suffix}"
    return RetrievalContextBundle(
        items=selected,
        prompt=prompt,
        estimated_tokens=max(1, len(prompt) // 4),
        truncated=truncated or len(selected) < len(contexts),
    )


def tokenize(text: str) -> set[str]:
    terms = {token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,}", text)}
    for segment in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", text):
        terms.add(segment)
        for width in (2, 3):
            terms.update(segment[index : index + width] for index in range(len(segment) - width + 1))
    return terms


def extract_symbols(text: str, language: str) -> list[tuple[str, int]]:
    """Extract interview-explainable symbols without adding compiler dependencies."""

    if language == "python":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        return [(node.name, int(node.lineno)) for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]

    patterns: list[re.Pattern[str]] = []
    if language == "go":
        patterns = [
            re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(", re.M),
            re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+(?:struct|interface)\b", re.M),
        ]
    elif language in {"javascript", "typescript", "java"}:
        patterns = [
            re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", re.M),
            re.compile(r"^\s*(?:export\s+)?(?:class|interface|type)\s+([A-Za-z_$][\w$]*)", re.M),
            re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|static\s+|async\s+)*([A-Za-z_$][\w$]*)\s*\([^;]*\)\s*\{", re.M),
        ]
    symbols: list[tuple[str, int]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            symbols.append((match.group(1), text.count("\n", 0, match.start()) + 1))
    return sorted(set(symbols), key=lambda item: (item[1], item[0]))


def _load_chunks(root: Path, files: list[CodeFile]) -> list[CodeChunk]:
    chunks: list[CodeChunk] = []
    for item in files:
        try:
            text = (root / item.path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        if not lines:
            continue
        symbols = extract_symbols(text, item.language)
        step = CHUNK_LINES - CHUNK_OVERLAP
        for start in range(0, len(lines), step):
            end = min(len(lines), start + CHUNK_LINES)
            chunk_symbols = tuple(name for name, line in symbols if start + 1 <= line <= end)
            chunks.append(
                CodeChunk(
                    path=item.path,
                    language=item.language,
                    start_line=start + 1,
                    end_line=end,
                    text="\n".join(lines[start:end]),
                    symbols=chunk_symbols,
                )
            )
            if end == len(lines):
                break
    return chunks


def _lexical_score(chunk: CodeChunk, terms: set[str]) -> float:
    path = chunk.path.lower()
    content = chunk.text.lower()
    return sum(3.0 for term in terms if term in path) + sum(min(5, content.count(term)) for term in terms)


def _symbol_score(chunk: CodeChunk, terms: set[str]) -> float:
    score = 0.0
    for symbol in chunk.symbols:
        lowered = symbol.lower()
        for term in terms:
            if term == lowered:
                score += 4.0
            elif term in lowered or lowered in term:
                score += 2.0
    return score


def _normalize(values: list[float]) -> list[float]:
    maximum = max(values, default=0.0)
    return [value / maximum if maximum > 0 else 0.0 for value in values]


def _semantic_scores(
    requirement: str,
    chunks: list[CodeChunk],
    provider: EmbeddingProvider | None,
) -> tuple[list[float], bool]:
    try:
        resolved = provider if provider is not None else embedding_provider_from_env()
        if resolved is None:
            return [0.0] * len(chunks), False
        query = resolved.embed_query(requirement)
        documents = resolved.embed_documents([f"{chunk.path}\n{' '.join(chunk.symbols)}\n{chunk.text}" for chunk in chunks])
        if len(documents) != len(chunks):
            raise ValueError("embedding provider returned an unexpected document count")
        return [_cosine(query, vector) for vector in documents], True
    except Exception as exc:
        logger.warning("Semantic code retrieval unavailable; falling back to lexical + symbol: %s", exc)
        return [0.0] * len(chunks), False


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    if denominator == 0:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / denominator))
