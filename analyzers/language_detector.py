"""
语言检测模块
"""
from pathlib import Path
from typing import Dict, List
from core.logger import get_logger

logger = get_logger(__name__)


class LanguageDetector:
    """语言检测器"""
    
    @staticmethod
    def detect_from_files(files: List[Path]) -> Dict[str, int]:
        """
        从文件列表检测编程语言
        
        Args:
            files: 文件列表
        
        Returns:
            语言及其文件数的字典
        """
        lang_count = {}
        
        for file_path in files:
            ext = file_path.suffix
            
            if ext == ".go":
                lang = "Go"
            elif ext == ".py":
                lang = "Python"
            else:
                continue
            
            lang_count[lang] = lang_count.get(lang, 0) + 1
        
        return lang_count
    
    @staticmethod
    def get_primary_language(lang_count: Dict[str, int]) -> str:
        """
        获取主要编程语言
        
        Args:
            lang_count: 语言计数字典
        
        Returns:
            主要语言名称
        """
        if not lang_count:
            return "Unknown"
        
        return max(lang_count, key=lang_count.get)
