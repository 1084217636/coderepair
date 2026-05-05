"""
Prompt 组装模块
"""
from typing import List, Dict, Any, Optional, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


class PromptBuilder:
    """
    Prompt 构建器

    职责：
    1. 根据任务类型、检索结果、历史对话组装 prompt
    2. 生成清晰的系统提示和用户提示
    3. 控制 prompt 长度，优化上下文窗口
    """

    CODE_LANGUAGES = {"go", "python"}

    def __init__(self, task_type: str, language: str):
        """
        初始化 Prompt 构建器

        Args:
            task_type: 任务类型（bug_fix / feature / review / follow_up）
            language: 编程语言（Go / Python 等）
        """
        self.task_type = task_type
        self.language = language
        self.logger = get_logger(__name__)

    def build_system_prompt(self) -> str:
        """
        构建系统提示

        Returns:
            系统提示文本
        """
        base_prompt = f"""你是一个专业的 {self.language} 开发者和代码审查专家。

你的职责是帮助开发者：
- 分析代码问题和需求
- 提供高质量的代码修改建议
- 生成清晰的代码补丁或完整的代码块
- 解释修改的原因和影响

重要要求：
1. 提供的代码必须是生产质量的，遵循最佳实践
2. 如果生成代码，请附加简短的说明
3. 考虑性能、可读性和可维护性
4. 如果有多个方案，比较它们的优缺点
5. 优先基于提供的仓库证据推理，不要脱离上下文臆测
"""

        if self.task_type == "bug_fix":
            base_prompt += "\n当前任务：修复代码中的 Bug。请分析问题根源并提供修复方案。"
        elif self.task_type == "feature":
            base_prompt += "\n当前任务：实现新功能。请设计清晰的接口和实现。"
        elif self.task_type == "review":
            base_prompt += "\n当前任务：代码审查。请指出潜在问题和改进建议。"
        elif self.task_type == "follow_up":
            base_prompt += "\n当前任务：根据之前的反馈继续优化代码。请参考之前的上下文。"

        return base_prompt

    def build_user_prompt(
        self,
        user_query: str,
        retrieval_results: Optional[List[Dict[str, Any]]] = None,
        analysis_info: Optional[Dict[str, Any]] = None,
        previous_response: Optional[str] = None,
        previous_retrieval_summary: Optional[str] = None,
    ) -> str:
        """
        构建用户提示

        Args:
            user_query: 用户的原始查询
            retrieval_results: 检索到的相关代码片段
            analysis_info: 代码分析信息
            previous_response: 上一轮的 LLM 响应（用于 follow-up）
            previous_retrieval_summary: 上一轮检索摘要（用于 follow-up）

        Returns:
            用户提示文本
        """
        self.logger.info("[Stage 6] 构造 Prompt")

        context_outline = self.build_context_outline(
            user_query=user_query,
            language=self.language,
            analysis_info=analysis_info,
            retrieval_results=retrieval_results,
            previous_response=previous_response,
            previous_retrieval_summary=previous_retrieval_summary,
            include_history=self.task_type == "follow_up",
            primary_limit=2,
            supporting_limit=3,
            primary_char_limit=800,
            supporting_char_limit=400,
        )

        request = self._build_request_section()
        prompt = "\n\n".join(part for part in (context_outline, request) if part.strip())

        self.logger.debug(f"[Prompt] 长度: {len(prompt)} 字符")

        return prompt

    def _build_request_section(self) -> str:
        parts = ["## 输出要求"]
        if self.task_type == "bug_fix":
            parts.append(
                """请提供：
1. 问题分析
2. 修复代码（完整的修改）
3. 简短的说明（为什么这样修复）
4. 任何可能的副作用或需要注意的地方"""
            )
        elif self.task_type == "feature":
            parts.append(
                """请提供：
1. 功能设计说明
2. 完整的代码实现
3. 使用示例
4. 关键实现细节的解释"""
            )
        elif self.task_type == "review":
            parts.append(
                """请提供：
1. 关键风险点
2. 证据依据（引用相关代码片段）
3. 修改建议或进一步验证建议"""
            )
        elif self.task_type == "follow_up":
            parts.append("请根据之前的反馈进一步改进代码，优先处理这轮主证据里暴露的问题。")
        else:
            parts.append("请提供你的建议。")
        return "\n".join(parts)

    @classmethod
    def build_context_outline(
        cls,
        user_query: str,
        language: str,
        analysis_info: Optional[Dict[str, Any]] = None,
        retrieval_results: Optional[List[Dict[str, Any]]] = None,
        previous_response: Optional[str] = None,
        previous_retrieval_summary: Optional[str] = None,
        include_history: bool = False,
        primary_limit: int = 2,
        supporting_limit: int = 3,
        primary_char_limit: int = 700,
        supporting_char_limit: int = 350,
    ) -> str:
        parts = [
            "## 用户需求",
            user_query,
            "",
        ]

        repository_facts = cls._render_repository_facts(analysis_info)
        if repository_facts:
            parts.append("## 仓库事实")
            parts.extend(repository_facts)
            parts.append("")

        primary_chunks, supporting_chunks = cls._select_evidence_chunks(
            retrieval_results or [],
            primary_limit=primary_limit,
            supporting_limit=supporting_limit,
        )

        if primary_chunks:
            parts.append("## 主证据")
            parts.append("这些片段最可能直接对应本轮问题的修改点或根因。")
            parts.extend(
                cls._render_chunk_list(primary_chunks, default_language=language, text_limit=primary_char_limit)
            )
            parts.append("")

        if supporting_chunks:
            parts.append("## 补充证据")
            parts.append("这些片段用于补充依赖、配置或邻近实现上下文。")
            parts.extend(
                cls._render_chunk_list(supporting_chunks, default_language=language, text_limit=supporting_char_limit)
            )
            parts.append("")

        if include_history:
            history = cls._render_history(previous_retrieval_summary, previous_response)
            if history:
                parts.append("## 历史摘要")
                parts.extend(history)
                parts.append("")

        return "\n".join(parts).strip()

    @classmethod
    def _render_repository_facts(cls, analysis_info: Optional[Dict[str, Any]]) -> List[str]:
        if not analysis_info:
            return []

        parts: List[str] = []
        for key in ("package", "language", "focus_file", "validation_mode", "self_dev"):
            if key in analysis_info:
                parts.append(f"- {key}: {analysis_info[key]}")

        for key, label, limit in (
            ("imports", "imports", 8),
            ("functions", "functions", 12),
            ("methods", "methods", 12),
            ("types", "types", 10),
        ):
            values = analysis_info.get(key) or []
            if values:
                parts.append(f"- {label}: {cls._join_items(values, limit)}")

        dependency_span = analysis_info.get("dependency_span") or {}
        if dependency_span:
            summary = ", ".join(
                f"{key}={value}"
                for key, value in dependency_span.items()
                if value
            )
            if summary:
                parts.append(f"- dependency_span: {summary}")

        if analysis_info.get("call_relations_count"):
            parts.append(f"- call_relations_count: {analysis_info['call_relations_count']}")

        return parts

    @classmethod
    def _render_history(
        cls,
        previous_retrieval_summary: Optional[str],
        previous_response: Optional[str],
    ) -> List[str]:
        parts: List[str] = []
        if previous_retrieval_summary:
            parts.append("### 上一轮检索摘要")
            parts.append(cls._truncate(previous_retrieval_summary, 700))
            parts.append("")
        if previous_response:
            parts.append("### 上一轮输出摘要")
            parts.append(cls._truncate(previous_response, 700))
        return parts

    @classmethod
    def _select_evidence_chunks(
        cls,
        retrieval_results: List[Dict[str, Any]],
        primary_limit: int,
        supporting_limit: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not retrieval_results:
            return [], []

        code_chunks = [chunk for chunk in retrieval_results if not cls._is_engineering_chunk(chunk)]
        engineering_chunks = [chunk for chunk in retrieval_results if cls._is_engineering_chunk(chunk)]

        primary = cls._take_unique(code_chunks, primary_limit)
        if not primary:
            primary = cls._take_unique(retrieval_results, primary_limit)

        used = {cls._chunk_identity(chunk) for chunk in primary}
        supporting: List[Dict[str, Any]] = []

        for pool in (code_chunks, engineering_chunks, retrieval_results):
            for chunk in pool:
                identity = cls._chunk_identity(chunk)
                if identity in used:
                    continue
                supporting.append(chunk)
                used.add(identity)
                if len(supporting) >= supporting_limit:
                    return primary, supporting

        return primary, supporting

    @classmethod
    def _render_chunk_list(
        cls,
        chunks: List[Dict[str, Any]],
        default_language: str,
        text_limit: int,
    ) -> List[str]:
        parts: List[str] = []
        for index, chunk in enumerate(chunks, 1):
            language = chunk.get("language", default_language.lower())
            summary = chunk.get("summary") or chunk.get("chunk_kind") or "chunk"
            chunk_kind = chunk.get("chunk_kind", "chunk")
            symbol = chunk.get("symbol")
            score_info = cls._format_score_info(chunk)

            parts.append(f"### 证据 {index}: {chunk.get('relative_path', 'unknown')}")
            parts.append(f"- 范围: 行 {chunk.get('start_line', 0)}-{chunk.get('end_line', 0)}")
            parts.append(f"- 类型: {chunk_kind}")
            parts.append(f"- 摘要: {summary}")
            if symbol:
                parts.append(f"- 符号: {symbol}")
            if score_info:
                parts.append(f"- 命中信息: {score_info}")
            parts.append(f"```{language}")
            parts.append(cls._truncate(chunk.get("text", ""), text_limit))
            parts.append("```")
            parts.append("")
        return parts

    @staticmethod
    def _chunk_identity(chunk: Dict[str, Any]) -> str:
        return (
            f"{chunk.get('relative_path', 'unknown')}:"
            f"{chunk.get('start_line', 0)}:{chunk.get('end_line', 0)}"
        )

    @staticmethod
    def _take_unique(chunks: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        seen = set()
        results = []
        for chunk in chunks:
            identity = PromptBuilder._chunk_identity(chunk)
            if identity in seen:
                continue
            seen.add(identity)
            results.append(chunk)
            if len(results) >= limit:
                break
        return results

    @classmethod
    def _is_engineering_chunk(cls, chunk: Dict[str, Any]) -> bool:
        return chunk.get("language", "").lower() not in cls.CODE_LANGUAGES

    @staticmethod
    def _format_score_info(chunk: Dict[str, Any]) -> str:
        score_parts = []
        for key in ("score", "lexical_score", "vector_score"):
            value = chunk.get(key)
            if isinstance(value, (int, float)):
                score_parts.append(f"{key}={value:.3f}")
        backend = chunk.get("retrieval_backend")
        if backend:
            score_parts.append(f"backend={backend}")
        return ", ".join(score_parts)

    @staticmethod
    def _join_items(values: List[str], limit: int) -> str:
        preview = ", ".join(values[:limit])
        if len(values) > limit:
            preview += "..."
        return preview

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 17] + "\n[内容已截断]"
