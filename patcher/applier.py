"""
Patch 应用器

支持 Unified Diff 格式的 Patch 应用和管理
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from core.logger import get_logger
from patcher.writer import FileWriter

logger = get_logger(__name__)


class PatchApplier:
    """Unified Diff Patch 应用器"""
    
    def __init__(self, workspace: str):
        """
        初始化 Patch 应用器
        
        Args:
            workspace: 工作目录
        """
        self.workspace = Path(workspace)
        self.writer = FileWriter(workspace)
        self.logger = get_logger(__name__)
    
    def apply_patch(
        self,
        patch_content: str,
        dry_run: bool = False,
    ) -> Dict:
        """
        应用 Unified Diff 格式的 Patch
        
        Args:
            patch_content: Patch 内容
            dry_run: 是否为演练模式（不实际修改）
        
        Returns:
            应用结果
        """
        self.logger.info(
            f"[Patcher] 应用 Patch | dry_run={dry_run}"
        )
        
        # 解析 Patch
        hunks = self._parse_patch(patch_content)
        
        if not hunks:
            self.logger.warning("No hunks found in patch")
            return {"status": "warning", "reason": "No hunks"}
        
        results = []
        
        for hunk in hunks:
            file_path = hunk["file"]
            changes = hunk["changes"]
            
            try:
                if dry_run:
                    # 演练模式：验证 Patch 可以应用
                    success = self._verify_patch(file_path, changes)
                    results.append({
                        "file": file_path,
                        "status": "verified" if success else "failed",
                    })
                else:
                    # 实际应用 Patch
                    self._apply_hunk(file_path, changes)
                    results.append({
                        "file": file_path,
                        "status": "applied",
                    })
            
            except Exception as e:
                self.logger.error(f"Failed to apply patch to {file_path}: {e}")
                results.append({
                    "file": file_path,
                    "status": "failed",
                    "error": str(e),
                })
        
        self.logger.info(f"[Patcher] Patch 应用完成 | 文件数={len(results)}")
        
        return {
            "status": "success" if all(r["status"] in ["applied", "verified"] for r in results) else "partial",
            "results": results,
        }
    
    def _parse_patch(self, patch_content: str) -> List[Dict]:
        """解析 Unified Diff 格式的 Patch"""
        hunks = []
        lines = patch_content.split("\n")
        
        current_file = None
        current_hunk = None
        context_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 文件头
            if line.startswith("---"):
                if current_hunk and current_file:
                    hunks.append({
                        "file": current_file,
                        "changes": current_hunk,
                    })
                current_file = self._extract_filename(line)
                current_hunk = []
                i += 2  # 跳过 +++ 行
            
            # Hunk 头
            elif line.startswith("@@"):
                current_hunk = []
                i += 1
            
            # 内容行
            elif current_hunk is not None and line:
                if line[0] in [" ", "-", "+"]:
                    current_hunk.append(line)
                i += 1
            else:
                i += 1
        
        if current_hunk and current_file:
            hunks.append({
                "file": current_file,
                "changes": current_hunk,
            })
        
        return hunks
    
    @staticmethod
    def _extract_filename(line: str) -> str:
        """从 --- 或 +++ 行提取文件名"""
        # 格式: --- a/path/to/file
        match = re.match(r"^[+-]{3}\s+[ab]/(.+?)(?:\s+|$)", line)
        if match:
            return match.group(1)
        return line[4:].strip()
    
    def _verify_patch(self, file_path: str, changes: List[str]) -> bool:
        """验证 Patch 可以应用"""
        full_path = self.workspace / file_path
        
        if not full_path.exists():
            self.logger.warning(f"File not found: {file_path}")
            return False
        
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            
            # 简单的验证：检查删除行是否存在
            for line in changes:
                if line.startswith("-") and not line.startswith("---"):
                    # 删除行应该在文件中存在
                    content_line = line[1:]
                    if content_line not in file_content:
                        self.logger.warning(f"Line not found in {file_path}: {content_line}")
                        return False
            
            return True
        
        except Exception as e:
            self.logger.error(f"Verification failed for {file_path}: {e}")
            return False
    
    def _apply_hunk(self, file_path: str, changes: List[str]) -> None:
        """应用单个 Hunk"""
        full_path = self.workspace / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 读取原文件
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # 应用改动
        new_lines = []
        line_idx = 0
        
        for change_line in changes:
            if change_line.startswith(" "):
                # 上下文行
                expected = change_line[1:].rstrip() + "\n"
                if line_idx < len(lines):
                    actual = lines[line_idx].rstrip() + "\n"
                    if actual == expected or actual.rstrip() + "\n" == expected:
                        new_lines.append(lines[line_idx])
                        line_idx += 1
            
            elif change_line.startswith("-"):
                # 删除行
                line_idx += 1
            
            elif change_line.startswith("+"):
                # 添加行
                new_content = change_line[1:]
                if not new_content.endswith("\n"):
                    new_content += "\n"
                new_lines.append(new_content)
        
        # 写回文件
        with open(full_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)


class UnifiedDiffGenerator:
    """生成 Unified Diff 格式的 Patch"""
    
    @staticmethod
    def generate_diff(
        old_content: str,
        new_content: str,
        file_path: str,
        context_lines: int = 3,
    ) -> str:
        """
        生成 Unified Diff
        
        Args:
            old_content: 原文件内容
            new_content: 新文件内容
            file_path: 文件路径
            context_lines: 上下文行数
        
        Returns:
            Unified Diff 格式的 Patch
        """
        old_lines = old_content.split("\n")
        new_lines = new_content.split("\n")
        
        diff_lines = [
            f"--- a/{file_path}",
            f"+++ b/{file_path}",
        ]
        
        # 简单的 diff 算法（实际项目应该使用 difflib）
        import difflib
        differ = difflib.unified_diff(
            old_lines,
            new_lines,
            lineterm="",
            n=context_lines,
        )
        
        diff_lines.extend(differ)
        
        return "\n".join(diff_lines)
