"""
代码分块模块
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CodeChunk:
    """代码片段"""

    file_path: Path
    relative_path: str
    language: str
    text: str
    start_line: int
    end_line: int
    summary: str = ""
    chunk_kind: str = "chunk"
    symbol: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "file_path": str(self.file_path),
            "relative_path": self.relative_path,
            "language": self.language,
            "text": self.text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "summary": self.summary,
            "chunk_kind": self.chunk_kind,
            "symbol": self.symbol,
            "lines": self.end_line - self.start_line + 1,
        }


@dataclass
class GoDeclaration:
    """Go 顶层声明切分结果"""

    start_line: int
    end_line: int
    chunk_kind: str
    summary: str
    symbol: str = ""


class CodeChunker:
    """代码分块器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.logger = get_logger(__name__)

    @staticmethod
    def detect_language(file_path: Path, default_language: str = "go") -> str:
        name = file_path.name
        suffix = file_path.suffix.lower()
        if name == "Dockerfile":
            return "dockerfile"
        if name == "Makefile":
            return "makefile"
        if name == ".dockerignore":
            return "dockerignore"
        if suffix == ".go":
            return "go"
        if suffix == ".py":
            return "python"
        if suffix == ".md":
            return "markdown"
        if suffix == ".mod":
            return "gomod"
        if suffix == ".sum":
            return "gosum"
        if suffix in {".yaml", ".yml"}:
            return "yaml"
        if suffix == ".json":
            return "json"
        if suffix == ".toml":
            return "toml"
        if suffix == ".sh":
            return "bash"
        return default_language or "text"

    def chunk_file(self, file_path: Path, language: str = "go") -> List[CodeChunk]:
        """将单个文件分块"""
        detected_language = self.detect_language(file_path, language)
        self.logger.debug(f"[Chunker] 处理文件 | file={file_path.name} | language={detected_language}")

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            if detected_language == "go":
                chunks = self._chunk_go_file(file_path, lines)
            elif detected_language == "python":
                chunks = self._chunk_python_file(file_path, lines)
            else:
                chunks = self._chunk_naive(file_path, lines, detected_language)

            self.logger.debug(f"[Chunker] 文件分块完成 | chunks={len(chunks)}")
            return chunks
        except Exception as e:
            self.logger.error(f"[Chunker] 分块失败 | file={file_path} | error={e}")
            return []

    def _get_rel_path(self, file_path: Path) -> str:
        """获取相对路径"""
        try:
            return str(file_path.relative_to(file_path.parent.parent))
        except ValueError:
            return file_path.name

    def _chunk_go_file(self, file_path: Path, lines: List[str]) -> List[CodeChunk]:
        """Go 文件按顶层声明边界切分。"""
        rel_path = self._get_rel_path(file_path)
        declarations = self._collect_go_declarations(lines)

        if not declarations:
            return self._chunk_naive(file_path, lines, "go")

        chunks: List[CodeChunk] = []

        header_end = declarations[0].start_line - 1
        if header_end >= 1:
            header_text = "\n".join(lines[:header_end])
            if header_text.strip():
                header_chunk = CodeChunk(
                    file_path=file_path,
                    relative_path=rel_path,
                    language="go",
                    text=header_text,
                    start_line=1,
                    end_line=header_end,
                    summary="package/imports",
                    chunk_kind="file_header",
                )
                chunks.extend(self._split_chunk_by_size(header_chunk))

        for declaration in declarations:
            text = "\n".join(lines[declaration.start_line - 1:declaration.end_line])
            if not text.strip():
                continue
            chunk = CodeChunk(
                file_path=file_path,
                relative_path=rel_path,
                language="go",
                text=text,
                start_line=declaration.start_line,
                end_line=declaration.end_line,
                summary=declaration.summary,
                chunk_kind=declaration.chunk_kind,
                symbol=declaration.symbol,
            )
            chunks.extend(self._split_chunk_by_size(chunk))

        return chunks

    def _collect_go_declarations(self, lines: List[str]) -> List[GoDeclaration]:
        raw_declarations: List[Tuple[int, str, str, str]] = []
        brace_depth = 0
        paren_depth = 0
        in_block_comment = False

        for line_no, line in enumerate(lines, 1):
            clean_line, in_block_comment = self._strip_go_comments(line, in_block_comment)
            stripped = clean_line.strip()

            if brace_depth == 0 and paren_depth == 0 and stripped:
                classified = self._classify_go_declaration(stripped)
                if classified:
                    raw_declarations.append((line_no, *classified))

            brace_depth += clean_line.count("{") - clean_line.count("}")
            paren_depth += clean_line.count("(") - clean_line.count(")")
            brace_depth = max(brace_depth, 0)
            paren_depth = max(paren_depth, 0)

        declarations: List[GoDeclaration] = []
        previous_end = 0
        for index, (line_no, chunk_kind, summary, symbol) in enumerate(raw_declarations):
            start_line = self._expand_go_doc_comments(lines, line_no, previous_end)
            next_start = (
                raw_declarations[index + 1][0]
                if index + 1 < len(raw_declarations)
                else len(lines) + 1
            )
            end_line = next_start - 1
            declarations.append(
                GoDeclaration(
                    start_line=start_line,
                    end_line=end_line,
                    chunk_kind=chunk_kind,
                    summary=summary,
                    symbol=symbol,
                )
            )
            previous_end = end_line

        return declarations

    @staticmethod
    def _strip_go_comments(line: str, in_block_comment: bool) -> Tuple[str, bool]:
        result = []
        index = 0

        while index < len(line):
            if in_block_comment:
                end = line.find("*/", index)
                if end == -1:
                    return "".join(result), True
                index = end + 2
                in_block_comment = False
                continue

            if line.startswith("//", index):
                break
            if line.startswith("/*", index):
                in_block_comment = True
                index += 2
                continue

            result.append(line[index])
            index += 1

        return "".join(result), in_block_comment

    @staticmethod
    def _classify_go_declaration(stripped: str) -> Tuple[str, str, str] | None:
        if stripped.startswith("func "):
            method_match = re.match(r"^func\s*\(([^)]*)\)\s*([A-Za-z_]\w*)", stripped)
            if method_match:
                receiver, name = method_match.groups()
                receiver_type = CodeChunker._normalize_go_receiver(receiver)
                symbol = f"{receiver_type}.{name}" if receiver_type else name
                return "method", f"method {symbol}", symbol

            func_match = re.match(r"^func\s+([A-Za-z_]\w*)", stripped)
            if func_match:
                name = func_match.group(1)
                return "function", f"func {name}", name

        if stripped.startswith("type "):
            type_match = re.match(r"^type\s+([A-Za-z_]\w*)", stripped)
            if type_match:
                name = type_match.group(1)
                return "type", CodeChunker._truncate_summary(stripped), name

        if stripped.startswith("const "):
            const_match = re.match(r"^const\s+([A-Za-z_]\w*)", stripped)
            symbol = const_match.group(1) if const_match else ""
            return "const", CodeChunker._truncate_summary(stripped), symbol

        if stripped.startswith("var "):
            var_match = re.match(r"^var\s+([A-Za-z_]\w*)", stripped)
            symbol = var_match.group(1) if var_match else ""
            return "var", CodeChunker._truncate_summary(stripped), symbol

        return None

    @staticmethod
    def _normalize_go_receiver(receiver: str) -> str:
        match = re.search(r"\*?([A-Za-z_]\w*)\s*$", receiver.strip())
        return match.group(1) if match else ""

    @staticmethod
    def _truncate_summary(text: str, max_chars: int = 80) -> str:
        return text if len(text) <= max_chars else text[: max_chars - 3] + "..."

    @staticmethod
    def _is_go_doc_comment_line(text: str) -> bool:
        stripped = text.strip()
        return (
            stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
            or stripped.endswith("*/")
        )

    def _expand_go_doc_comments(self, lines: List[str], line_no: int, previous_end: int) -> int:
        start_line = line_no
        cursor = line_no - 1

        while cursor > previous_end:
            previous_line = lines[cursor - 1].strip()
            if not previous_line:
                break
            if not self._is_go_doc_comment_line(previous_line):
                break
            start_line = cursor
            cursor -= 1

        return start_line

    def _split_chunk_by_size(self, chunk: CodeChunk) -> List[CodeChunk]:
        if len(chunk.text) <= self.chunk_size:
            return [chunk]

        windows = self._build_line_windows(chunk.text.split("\n"), chunk.start_line)
        if len(windows) <= 1:
            return [chunk]

        chunks: List[CodeChunk] = []
        for index, (start_line, end_line, window_lines) in enumerate(windows, 1):
            text = "\n".join(window_lines)
            summary = f"{chunk.summary} [part {index}]"
            chunks.append(
                CodeChunk(
                    file_path=chunk.file_path,
                    relative_path=chunk.relative_path,
                    language=chunk.language,
                    text=text,
                    start_line=start_line,
                    end_line=end_line,
                    summary=summary,
                    chunk_kind=chunk.chunk_kind,
                    symbol=chunk.symbol,
                )
            )

        return chunks

    def _build_line_windows(
        self,
        lines: List[str],
        start_line: int,
    ) -> List[Tuple[int, int, List[str]]]:
        if not lines:
            return []

        windows: List[Tuple[int, int, List[str]]] = []
        index = 0
        while index < len(lines):
            end = index
            current_size = 0
            while end < len(lines) and (current_size < self.chunk_size or end == index):
                current_size += len(lines[end]) + 1
                end += 1

            window_lines = lines[index:end]
            windows.append((start_line + index, start_line + end - 1, window_lines))

            if end >= len(lines):
                break

            overlap_lines = 0
            overlap_chars = 0
            cursor = end - 1
            while cursor > index and overlap_chars < self.chunk_overlap:
                overlap_chars += len(lines[cursor]) + 1
                overlap_lines += 1
                cursor -= 1

            index = end - overlap_lines if overlap_lines else end

        return windows

    def _chunk_python_file(self, file_path: Path, lines: List[str]) -> List[CodeChunk]:
        """Python 文件分块策略"""
        return self._chunk_naive(file_path, lines, "python")

    def _chunk_naive(self, file_path: Path, lines: List[str], language: str) -> List[CodeChunk]:
        """简单的固定大小分块策略"""
        chunks = []
        rel_path = self._get_rel_path(file_path)

        for start_line, end_line, window_lines in self._build_line_windows(lines, 1):
            text = "\n".join(window_lines)
            if not text.strip():
                continue
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    relative_path=rel_path,
                    language=language,
                    text=text,
                    start_line=start_line,
                    end_line=end_line,
                    summary=f"{file_path.name}:{start_line}",
                    chunk_kind="window",
                )
            )

        return chunks
