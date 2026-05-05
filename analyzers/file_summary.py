"""
文件摘要生成模块
"""
from pathlib import Path
from typing import Dict, Any
from core.logger import get_logger

logger = get_logger(__name__)


class FileSummary:
    """
    文件摘要生成器
    
    职责：
    1. 生成源代码文件的摘要
    2. 提取关键信息（注释、函数签名等）
    """
    
    @staticmethod
    def generate_go_summary(file_path: Path) -> str:
        """
        生成 Go 文件的摘要
        
        Args:
            file_path: .go 文件路径
        
        Returns:
            文件摘要字符串
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            summary_lines = []
            
            # 提取文件头的注释
            for line in lines[:20]:
                if line.strip().startswith("//"):
                    summary_lines.append(line.strip())
                else:
                    break
            
            # 如果没有头部注释，提取前几个重要定义
            if not summary_lines:
                summary_lines.append(f"// File: {file_path.name}")
            
            return "\n".join(summary_lines) if summary_lines else f"// {file_path.name}"
        
        except Exception as e:
            logger.error(f"[FileSummary] 生成摘要失败 | file={file_path} | error={e}")
            return f"// {file_path.name}"
