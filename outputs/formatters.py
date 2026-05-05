"""
结果格式化模块
"""
from typing import Dict, Any, Optional, List
from core.logger import get_logger

logger = get_logger(__name__)


class ResultFormatter:
    """
    结果格式化器
    
    职责：
    1. 格式化 LLM 输出
    2. 生成 diff
    3. 输出结果摘要
    """
    
    @staticmethod
    def extract_code_blocks(text: str, language: str = "go") -> List[str]:
        """
        从 LLM 输出中提取代码块
        
        Args:
            text: LLM 输出文本
            language: 编程语言
        
        Returns:
            代码块列表
        """
        import re
        
        aliases = {
            "go": {"", "go", "golang"},
            "python": {"", "python", "py"},
            "dockerfile": {"", "dockerfile", "docker"},
            "dockerignore": {"", "dockerignore"},
            "makefile": {"", "makefile", "make"},
            "markdown": {"", "markdown", "md"},
            "gomod": {"", "gomod", "mod", "go.mod"},
            "gosum": {"", "gosum", "go.sum"},
            "yaml": {"", "yaml", "yml"},
            "json": {"", "json"},
            "toml": {"", "toml"},
            "bash": {"", "bash", "sh", "shell"},
        }
        accepted_tags = aliases.get(language.lower(), {"", language.lower()})
        pattern = r"```([^\n`]*)\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

        return [
            code.strip()
            for tag, code in matches
            if (tag or "").strip().lower() in accepted_tags
        ]
    
    @staticmethod
    def generate_summary(task_type: str, result: Dict[str, Any]) -> str:
        """
        生成执行结果摘要
        
        Args:
            task_type: 任务类型
            result: 执行结果字典
        
        Returns:
            摘要文本
        """
        parts = []
        
        parts.append("=" * 60)
        parts.append("执行完成 - 结果摘要")
        parts.append("=" * 60)
        
        if result.get("session_id"):
            parts.append(f"\nSession ID: {result['session_id']}")
        if result.get("parent_session_id"):
            parts.append(f"Parent Session ID: {result['parent_session_id']}")

        parts.append(f"\n任务类型: {task_type}\n")

        if result.get("execution_mode"):
            parts.append(f"执行模式: {result['execution_mode']}\n")

        if result.get("llm_config"):
            llm_config = result["llm_config"]
            parts.append("## LLM 配置\n")
            parts.append(f"- Provider: {llm_config.get('provider')}")
            parts.append(f"- Model: {llm_config.get('model')}\n")

        if result.get("multi_agent"):
            multi_agent = result["multi_agent"]
            review = multi_agent.get("review", {})
            parts.append("## Multi-Agent 协作\n")
            if multi_agent.get("orchestration_backend"):
                parts.append(f"- Backend: {multi_agent.get('orchestration_backend')}")
            parts.append(f"- Agent Steps: {len(multi_agent.get('steps', []))}")
            parts.append(f"- Reviewer Verdict: {review.get('verdict', 'unknown')}")
            parts.append(f"- Revision Count: {multi_agent.get('revision_count', 0)}\n")
        
        if "llm_response" in result:
            parts.append("## LLM 建议\n")
            response = result["llm_response"]
            if len(response) > 500:
                parts.append(response[:500] + "\n... (已截断)\n")
            else:
                parts.append(response + "\n")
        
        if "validation_output" in result and result["validation_output"]:
            validation = result["validation_output"]
            parts.append("## 验证结果\n")
            source = validation.get("source", "unknown")
            if validation.get("skipped_reason"):
                parts.append(f"- 已跳过验证（source={source}）: {validation.get('skipped_reason')}\n")
            elif validation.get("success"):
                parts.append(f"✓ 验证通过（source={source}）\n")
            else:
                parts.append(f"✗ 验证失败（source={source}）\n")
            
            if validation.get("stderr"):
                parts.append("错误信息:\n")
                parts.append(validation.get("stderr", "")[:200])
        elif "validation_output" in result and result["validation_output"] is None:
            parts.append("## 验证结果\n")
            parts.append("- 已跳过验证（--no-validate）\n")

        if result.get("apply_output"):
            apply_output = result["apply_output"]
            parts.append("## 写回结果\n")
            if apply_output.get("status") in {"applied", "validated", "applied_unverified"}:
                stats = apply_output.get("diff_stats", {})
                parts.append(
                    f"- 已写回 `{apply_output.get('file')}` "
                    f"(+{stats.get('additions', 0)} / -{stats.get('deletions', 0)})\n"
                )
                if apply_output.get("status") == "validated":
                    parts.append("- 写回后已完成验证\n")
                if apply_output.get("status") == "applied_unverified":
                    parts.append("- 写回成功，但当前没有拿到可执行的验证结果\n")
            elif apply_output.get("status") == "rolled_back":
                parts.append(f"- 已回滚 `{apply_output.get('file')}`，原因：验证失败\n")
            elif apply_output.get("status") == "rollback_failed":
                parts.append(f"- `{apply_output.get('file')}` 验证失败，且回滚失败\n")
            elif apply_output.get("status") == "validate_failed":
                parts.append(f"- `{apply_output.get('file')}` 已写回，但验证失败\n")
            else:
                parts.append(
                    f"- 未写回 `{apply_output.get('file')}`: {apply_output.get('reason', 'unknown')}\n"
                )

        if result.get("evaluation_output"):
            evaluation = result["evaluation_output"]
            parts.append("## 运行评估\n")
            parts.append(f"- RAG: {evaluation.get('rag_backend')} / {evaluation.get('embedding_provider')}")
            parts.append(f"- 检索命中率: {evaluation.get('retrieval_hit_rate')}")
            parts.append(f"- 修复状态: {evaluation.get('repair_status')}\n")

        parts.append("\n详细信息请查看 artifacts 目录下的完整日志。")
        
        return "\n".join(parts)
