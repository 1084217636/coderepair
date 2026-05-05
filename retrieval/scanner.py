"""
仓库扫描模块
"""
from pathlib import Path
from typing import List, Dict, Any
from core.logger import get_logger
from retrieval.filters import PathFilter

logger = get_logger(__name__)


class RepositoryScanner:
    """
    仓库扫描器
    
    职责：
    1. 扫描 workspace 内的代码文件
    2. 提取文件级别的结构信息（包、导入、函数等）
    3. 过滤掉平台代码和不相关的文件
    """
    
    def __init__(self, path_filter: PathFilter):
        """
        初始化扫描器
        
        Args:
            path_filter: PathFilter 实例
        """
        self.path_filter = path_filter
        self.workspace_root = path_filter.workspace_root
        self.logger = get_logger(__name__)
    
    def scan(self) -> Dict[str, Any]:
        """
        扫描整个 workspace
        
        Returns:
            扫描结果字典
        """
        self.logger.info(f"[Stage 3] 仓库结构分析 | workspace_root={self.workspace_root}")
        
        valid_files = self.path_filter.scan_valid_files()
        
        # 按文件扩展名分类
        go_files = [f for f in valid_files if f.suffix == ".go"]
        py_files = [f for f in valid_files if f.suffix == ".py"]
        engineering_files = [f for f in valid_files if f not in go_files and f not in py_files]
        
        result = {
            "workspace_root": str(self.workspace_root),
            "total_files": len(valid_files),
            "go_files": len(go_files),
            "py_files": len(py_files),
            "engineering_files": len(engineering_files),
            "files": valid_files,
            "go_files_list": go_files,
            "py_files_list": py_files,
            "engineering_files_list": engineering_files,
        }
        
        self.logger.info(
            f"[Stage 3] 扫描完成 | "
            f"total_files={len(valid_files)} | "
            f"go_files={len(go_files)} | "
            f"py_files={len(py_files)} | "
            f"engineering_files={len(engineering_files)}"
        )
        
        return result
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """
        获取单个文件的信息
        
        Args:
            file_path: 文件路径
        
        Returns:
            文件信息字典
        """
        if not self.path_filter.is_valid_path(file_path):
            raise ValueError(f"文件不在有效范围内: {file_path}")
        
        return {
            "path": str(file_path),
            "name": file_path.name,
            "size": file_path.stat().st_size,
            "suffix": file_path.suffix,
            "relative_path": str(file_path.relative_to(self.workspace_root)),
        }
