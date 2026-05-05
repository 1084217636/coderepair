"""
改动验证器

验证代码改动是否符合预期
"""

import re
from pathlib import Path
from typing import List, Dict

from core.logger import get_logger

logger = get_logger(__name__)


class ChangeValidator:
    """改动验证器"""
    
    def __init__(self, workspace: str):
        """
        初始化验证器
        
        Args:
            workspace: 工作目录
        """
        self.workspace = Path(workspace)
        self.logger = get_logger(__name__)
    
    def validate_change(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> Dict:
        """
        验证改动
        
        Args:
            file_path: 文件路径
            old_content: 原文件内容
            new_content: 新文件内容
        
        Returns:
            验证结果
        """
        self.logger.info(f"[Validator] 验证改动 | file={file_path}")
        
        issues = []
        
        # 1. 检查文件类型
        if file_path.endswith(".go"):
            issues.extend(self._validate_go_file(file_path, old_content, new_content))
        
        # 2. 检查基本完整性
        issues.extend(self._check_basic_integrity(new_content))
        
        # 3. 检查语法
        issues.extend(self._check_syntax(file_path, new_content))
        
        status = "valid" if not issues else "warning" if len(issues) <= 2 else "invalid"
        
        return {
            "status": status,
            "file": file_path,
            "issues": issues,
        }
    
    def _validate_go_file(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> List[Dict]:
        """验证 Go 文件"""
        issues = []
        
        # 检查 package 声明
        if not re.search(r"^package\s+\w+", new_content, re.MULTILINE):
            issues.append({
                "type": "error",
                "message": "Missing package declaration",
            })
        
        # 检查导入
        if "import" in new_content:
            if not re.search(r"import\s*\(", new_content):
                issues.append({
                    "type": "warning",
                    "message": "Multiple imports should use parentheses",
                })
        
        # 检查括号匹配
        if new_content.count("{") != new_content.count("}"):
            issues.append({
                "type": "error",
                "message": "Unmatched braces",
            })
        
        return issues
    
    def _check_basic_integrity(self, content: str) -> List[Dict]:
        """检查基本完整性"""
        issues = []
        
        # 检查是否为空
        if not content.strip():
            issues.append({
                "type": "error",
                "message": "File is empty",
            })
        
        # 检查是否包含有效字符
        if len(content) < 10:
            issues.append({
                "type": "warning",
                "message": "File is very short",
            })
        
        return issues
    
    def _check_syntax(self, file_path: str, content: str) -> List[Dict]:
        """检查语法"""
        issues = []
        
        # 基本的语法检查
        if file_path.endswith(".go"):
            # 检查 Go 特定语法
            if re.search(r":=\s*$", content, re.MULTILINE):
                issues.append({
                    "type": "error",
                    "message": "Incomplete assignment",
                })
        
        return issues
    
    def validate_diff(
        self,
        file_path: str,
        diff_content: str,
    ) -> Dict:
        """
        验证 Diff
        
        Args:
            file_path: 文件路径
            diff_content: Diff 内容
        
        Returns:
            验证结果
        """
        self.logger.info(f"[Validator] 验证 Diff | file={file_path}")
        
        # 检查 Diff 格式
        if not diff_content.startswith("---"):
            return {
                "status": "invalid",
                "error": "Invalid diff format",
            }
        
        # 检查是否包含有效的改动
        if not ("+" in diff_content or "-" in diff_content):
            return {
                "status": "warning",
                "reason": "No actual changes in diff",
            }
        
        return {
            "status": "valid",
            "diff_size": len(diff_content),
        }
