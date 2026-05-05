"""
路径过滤模块 - 确保 RAG 检索范围正确
【关键】这一层确保只检索 workspace 代码，不污染平台代码
"""
from pathlib import Path
from typing import List, Set
from fnmatch import fnmatch
from core.logger import get_logger

logger = get_logger(__name__)


class PathFilter:
    """
    路径过滤器
    
    职责：
    1. 接收平台根目录和 workspace 根目录
    2. 定义哪些模式应该被排除
    3. 验证文件/目录是否在允许的范围内
    4. 生成清理后的文件列表
    """
    
    def __init__(
        self,
        platform_root: Path,
        workspace_root: Path,
        exclude_patterns: List[str] = None,
        include_extensions: List[str] = None,
        include_filenames: List[str] = None,
        allow_platform_source: bool = False,
    ):
        """
        初始化过滤器
        
        Args:
            platform_root: 平台代码根目录（绝对不检索）
            workspace_root: 用户项目根目录（仅检索此目录）
            exclude_patterns: 排除的 glob 模式列表
            include_extensions: 包含的文件扩展名列表
        """
        self.platform_root = platform_root
        self.workspace_root = workspace_root
        self.exclude_patterns = exclude_patterns or self._get_default_exclude_patterns()
        self.include_extensions = include_extensions or [".go", ".py"]
        self.include_filenames = include_filenames or []
        self.allow_platform_source = allow_platform_source
        
        self.logger = get_logger(__name__)
        
        self.logger.info(
            f"[PathFilter] 初始化完成 | "
            f"platform_root={self.platform_root} | "
            f"workspace_root={self.workspace_root} | "
            f"allow_platform_source={self.allow_platform_source}"
        )
        self.logger.debug(f"[PathFilter] 排除模式: {self.exclude_patterns}")
        self.logger.debug(f"[PathFilter] 包含扩展: {self.include_extensions}")
        self.logger.debug(f"[PathFilter] 包含文件名: {self.include_filenames}")
    
    @staticmethod
    def _get_default_exclude_patterns() -> List[str]:
        """
        获取默认的排除模式
        
        Returns:
            排除模式列表
        """
        return [
            ".*",                    # 隐藏文件和目录
            "__pycache__",
            "*.pyc", "*.pyo",
            ".git", ".gitignore",
            "node_modules",
            ".venv", "venv",
            "dist", "build",
            "*.egg-info",
            ".pytest_cache",
            ".coverage",
            ".mypy_cache",
            ".DS_Store",
            "artifacts",             # 平台输出目录
        ]
    
    def is_valid_path(self, file_path: Path) -> bool:
        """
        检查路径是否有效（应该被检索）
        
        Args:
            file_path: 要检查的文件路径
        
        Returns:
            True 表示有效，False 表示应该排除
        """
        # 检查 1：必须在 workspace 内
        try:
            file_path.relative_to(self.workspace_root)
        except ValueError:
            # 路径不在 workspace 内
            return False
        
        # 检查 2：默认不允许扫描平台源码，避免普通用户任务污染平台上下文。
        if not self.allow_platform_source:
            platform_source_dirs = {"core", "retrieval", "analyzers", "llm", "executors", "outputs", "tests"}
            try:
                rel_to_platform = file_path.relative_to(self.platform_root)
                if rel_to_platform.parts and rel_to_platform.parts[0] in platform_source_dirs:
                    return False
            except ValueError:
                # 路径不在 platform_root 内，这是好的
                pass
        
        # 检查 3：检查文件扩展名
        explicitly_included = file_path.name in self.include_filenames
        if file_path.is_file():
            if file_path.suffix not in self.include_extensions and not explicitly_included:
                return False
        
        # 检查 4：检查排除模式
        relative_path = file_path.relative_to(self.workspace_root)
        path_str = str(relative_path)
        
        for pattern in self.exclude_patterns:
            if explicitly_included and pattern == ".*":
                continue
            # 检查完整路径和路径的各个部分
            if fnmatch(path_str, pattern) or fnmatch(path_str, f"*/{pattern}/*") or fnmatch(path_str, f"*/{pattern}"):
                return False
            # 检查目录名
            for part in relative_path.parts:
                if explicitly_included and part == file_path.name:
                    continue
                if fnmatch(part, pattern):
                    return False
        
        return True
    
    def filter_files(self, files: List[Path]) -> List[Path]:
        """
        过滤文件列表
        
        Args:
            files: 输入文件列表
        
        Returns:
            过滤后的文件列表
        """
        valid_files = [f for f in files if self.is_valid_path(f)]
        
        self.logger.info(
            f"[PathFilter] 文件过滤完成 | "
            f"输入={len(files)} | 输出={len(valid_files)}"
        )
        
        return valid_files
    
    def scan_valid_files(self, pattern: str = "*") -> List[Path]:
        """
        扫描 workspace 内所有有效的文件
        
        Args:
            pattern: 文件 glob 模式
        
        Returns:
            有效的文件列表
        """
        files = []
        
        for ext in self.include_extensions:
            # 构建 glob 模式
            glob_pattern = f"{pattern}{ext}"
            found_files = list(self.workspace_root.rglob(glob_pattern))
            files.extend(found_files)

        for name in self.include_filenames:
            files.extend(self.workspace_root.rglob(name))
        
        deduped_files = list(dict.fromkeys(files))
        return self.filter_files(deduped_files)
