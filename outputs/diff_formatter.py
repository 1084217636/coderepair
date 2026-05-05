"""
Diff 产物生成

生成可视化的代码变更输出

功能：
  • Unified Diff 格式
  • 变更统计信息
  • HTML 可视化（可选）
"""

import difflib
from typing import Dict, List, Tuple
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)


class DiffFormatter:
    """Diff 格式化器"""
    
    def __init__(self, workspace: str):
        """
        初始化 Diff 格式化器
        
        Args:
            workspace: 工作目录
        """
        self.workspace = Path(workspace)
        self.logger = get_logger(__name__)
    
    def generate_diff(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        context_lines: int = 3,
    ) -> Dict:
        """
        生成 Unified Diff
        
        Args:
            file_path: 文件相对路径
            old_content: 原文件内容
            new_content: 新文件内容
            context_lines: 上下文行数
        
        Returns:
            包含 Diff 内容和统计信息的字典
        """
        self.logger.info(f"[DiffFormatter] 生成 Diff | file={file_path}")
        
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        # 生成 Unified Diff
        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
            n=context_lines,
        ))
        
        diff_content = "\n".join(diff_lines)
        
        # 计算统计信息
        stats = self._calculate_stats(diff_lines)
        
        return {
            "file": file_path,
            "diff": diff_content,
            "stats": stats,
        }
    
    def generate_multiple_diffs(
        self,
        changes: List[Dict],
    ) -> Dict:
        """
        生成多个文件的 Diff
        
        Args:
            changes: 改动列表，每项包含 {file_path, old_content, new_content}
        
        Returns:
            所有 Diff 的内容和统计信息
        """
        self.logger.info(f"[DiffFormatter] 生成多文件 Diff | 文件数={len(changes)}")
        
        all_diffs = []
        total_stats = {
            "files_changed": 0,
            "additions": 0,
            "deletions": 0,
            "total_changes": 0,
        }
        
        for change in changes:
            diff_result = self.generate_diff(
                file_path=change["file_path"],
                old_content=change.get("old_content", ""),
                new_content=change.get("new_content", ""),
            )
            
            all_diffs.append(diff_result)
            
            # 累计统计
            stats = diff_result["stats"]
            total_stats["files_changed"] += 1
            total_stats["additions"] += stats["additions"]
            total_stats["deletions"] += stats["deletions"]
            total_stats["total_changes"] += stats["total_changes"]
        
        # 生成统一的 Diff 内容
        full_diff = "\n".join([d["diff"] for d in all_diffs])
        
        return {
            "files": [d["file"] for d in all_diffs],
            "full_diff": full_diff,
            "total_stats": total_stats,
            "diffs": all_diffs,
        }
    
    def format_diff_for_markdown(self, diff_content: str) -> str:
        """
        格式化为 Markdown
        
        Args:
            diff_content: Unified Diff 内容
        
        Returns:
            Markdown 格式的 Diff
        """
        return f"```diff\n{diff_content}\n```"
    
    def format_diff_for_html(
        self,
        diff_content: str,
        file_path: str,
    ) -> str:
        """
        格式化为 HTML
        
        Args:
            diff_content: Unified Diff 内容
            file_path: 文件路径
        
        Returns:
            HTML 格式的 Diff
        """
        lines = diff_content.split("\n")
        html_lines = ['<div class="diff">']
        
        for line in lines:
            if line.startswith("---"):
                html_lines.append(f'<div class="diff-header">{self._escape_html(line)}</div>')
            elif line.startswith("+++"):
                html_lines.append(f'<div class="diff-header">{self._escape_html(line)}</div>')
            elif line.startswith("-"):
                html_lines.append(f'<div class="diff-remove">{self._escape_html(line)}</div>')
            elif line.startswith("+"):
                html_lines.append(f'<div class="diff-add">{self._escape_html(line)}</div>')
            elif line.startswith(" "):
                html_lines.append(f'<div class="diff-context">{self._escape_html(line)}</div>')
            elif line.startswith("@@"):
                html_lines.append(f'<div class="diff-hunk">{self._escape_html(line)}</div>')
            else:
                html_lines.append(f'<div>{self._escape_html(line)}</div>')
        
        html_lines.append("</div>")
        
        return "\n".join(html_lines)
    
    def generate_diff_summary(
        self,
        changes: List[Dict],
    ) -> Dict:
        """
        生成 Diff 摘要
        
        Args:
            changes: 改动列表
        
        Returns:
            摘要信息
        """
        summary = {
            "total_files": len(changes),
            "files_by_type": {},
            "total_additions": 0,
            "total_deletions": 0,
            "total_lines_changed": 0,
        }
        
        for change in changes:
            diff_result = self.generate_diff(
                file_path=change["file_path"],
                old_content=change.get("old_content", ""),
                new_content=change.get("new_content", ""),
            )
            
            stats = diff_result["stats"]
            file_ext = Path(change["file_path"]).suffix[1:] or "unknown"
            
            if file_ext not in summary["files_by_type"]:
                summary["files_by_type"][file_ext] = 0
            summary["files_by_type"][file_ext] += 1
            
            summary["total_additions"] += stats["additions"]
            summary["total_deletions"] += stats["deletions"]
            summary["total_lines_changed"] += stats["total_changes"]
        
        return summary
    
    @staticmethod
    def _calculate_stats(diff_lines: List[str]) -> Dict:
        """计算 Diff 统计信息"""
        additions = 0
        deletions = 0
        
        for line in diff_lines:
            if line.startswith("+") and not line.startswith("+++"):
                additions += 1
            elif line.startswith("-") and not line.startswith("---"):
                deletions += 1
        
        return {
            "additions": additions,
            "deletions": deletions,
            "total_changes": additions + deletions,
        }
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&#39;")
        )


def generate_combined_diff(
    changes: List[Tuple[str, str, str]],
) -> str:
    """
    生成合并后的 Diff
    
    Args:
        changes: 改动列表，每项为 (file_path, old_content, new_content)
    
    Returns:
        完整的 Diff 内容
    """
    formatter = DiffFormatter(".")
    all_diffs = []
    
    for file_path, old_content, new_content in changes:
        result = formatter.generate_diff(file_path, old_content, new_content)
        all_diffs.append(result["diff"])
    
    return "\n".join(all_diffs)
