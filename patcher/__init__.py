"""
Patcher 模块 - 代码修改和文件操作

功能：
  • 文件写入和更新
  • Unified Diff 格式 Patch 应用
  • 改动回滚机制
  • 改动验证和备份
"""

from patcher.writer import FileWriter
from patcher.applier import PatchApplier
from patcher.validator import ChangeValidator

__all__ = [
    "FileWriter",
    "PatchApplier",
    "ChangeValidator",
]
