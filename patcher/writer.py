"""
文件写入器

提供安全的文件操作接口，支持：
  • 创建新文件
  • 更新现有文件
  • 备份管理
  • 原子操作
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from core.logger import get_logger

logger = get_logger(__name__)


class FileWriter:
    """文件写入器 - 提供安全的文件操作"""
    
    def __init__(self, workspace: str, backup_enabled: bool = True):
        """
        初始化文件写入器
        
        Args:
            workspace: 工作目录
            backup_enabled: 是否启用备份
        """
        self.workspace = Path(workspace)
        self.backup_enabled = backup_enabled
        self.backup_dir = self.workspace / ".coderepair_backups"
        self.operations_log = []  # 记录所有操作，便于回滚
        
        if self.backup_enabled:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = get_logger(__name__)
    
    def write_file(
        self,
        file_path: str,
        content: str,
        create_backup: bool = True,
    ) -> Dict:
        """
        写入文件
        
        Args:
            file_path: 文件相对路径
            content: 文件内容
            create_backup: 是否创建备份
        
        Returns:
            操作结果字典
        """
        full_path = self.workspace / file_path
        
        self.logger.info(f"[Patcher] 写入文件 | path={file_path}")
        
        # 确认目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建备份（如果文件已存在）
        backup_path = None
        if full_path.exists() and create_backup and self.backup_enabled:
            backup_path = self._create_backup(full_path)
            self.logger.debug(f"  Backup created: {backup_path}")
        
        # 写入文件
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            operation = {
                "type": "write_file",
                "path": file_path,
                "timestamp": datetime.now().isoformat(),
                "backup_path": str(backup_path) if backup_path else None,
                "status": "success",
            }
            self.operations_log.append(operation)
            
            self.logger.info(f"[Patcher] 文件写入成功 | path={file_path}")
            
            return {
                "status": "success",
                "path": file_path,
                "size": len(content),
                "backup": backup_path,
            }
        
        except Exception as e:
            self.logger.error(f"[Patcher] 文件写入失败 | path={file_path} | error={e}")
            # 恢复备份
            if backup_path:
                self._restore_backup(full_path, backup_path)
            raise
    
    def update_file(
        self,
        file_path: str,
        old_content: Optional[str] = None,
        new_content: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Dict:
        """
        更新文件（带备份）
        
        Args:
            file_path: 文件相对路径
            old_content: 旧内容（用于查找替换）
            new_content: 新内容
            content: 直接替换为此内容（当new_content未提供时使用）
        
        Returns:
            操作结果
        """
        full_path = self.workspace / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 如果提供了old_content，进行内容替换
        if old_content is not None and new_content is not None:
            with open(full_path, "r", encoding="utf-8") as f:
                current_content = f.read()
            
            if old_content not in current_content:
                raise ValueError(f"Cannot find '{old_content}' in {file_path}")
            
            updated_content = current_content.replace(old_content, new_content, 1)
            return self.write_file(file_path, updated_content, create_backup=True)
        
        # 否则直接使用content或new_content
        final_content = new_content if new_content is not None else content
        if final_content is None:
            raise ValueError("Must provide either old_content/new_content or content")
        
        return self.write_file(file_path, final_content, create_backup=True)
    
    def append_to_file(
        self,
        file_path: str,
        content: str,
    ) -> Dict:
        """
        追加内容到文件
        
        Args:
            file_path: 文件相对路径
            content: 要追加的内容
        
        Returns:
            操作结果
        """
        full_path = self.workspace / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self.logger.info(f"[Patcher] 追加内容到文件 | path={file_path}")
        
        # 创建备份
        backup_path = None
        if self.backup_enabled:
            backup_path = self._create_backup(full_path)
        
        try:
            with open(full_path, "a", encoding="utf-8") as f:
                f.write(content)

            operation = {
                "type": "append",
                "path": file_path,
                "timestamp": datetime.now().isoformat(),
                "backup_path": str(backup_path) if backup_path else None,
                "status": "success",
            }
            self.operations_log.append(operation)
            
            self.logger.info(f"[Patcher] 内容追加成功 | path={file_path}")
            
            return {
                "status": "success",
                "path": file_path,
                "appended_size": len(content),
                "backup": backup_path,
            }
        
        except Exception as e:
            self.logger.error(f"[Patcher] 内容追加失败 | error={e}")
            if backup_path:
                self._restore_backup(full_path, backup_path)
            raise
    
    def delete_file(self, file_path: str) -> Dict:
        """
        删除文件
        
        Args:
            file_path: 文件相对路径
        
        Returns:
            操作结果
        """
        full_path = self.workspace / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self.logger.info(f"[Patcher] 删除文件 | path={file_path}")
        
        # 创建备份
        backup_path = None
        if self.backup_enabled:
            backup_path = self._create_backup(full_path)
        
        try:
            full_path.unlink()
            
            operation = {
                "type": "delete",
                "path": file_path,
                "timestamp": datetime.now().isoformat(),
                "backup_path": str(backup_path) if backup_path else None,
                "status": "success",
            }
            self.operations_log.append(operation)
            
            self.logger.info(f"[Patcher] 文件删除成功 | path={file_path}")
            
            return {
                "status": "success",
                "path": file_path,
                "backup": backup_path,
            }
        
        except Exception as e:
            self.logger.error(f"[Patcher] 文件删除失败 | error={e}")
            if backup_path:
                self._restore_backup(full_path, backup_path)
            raise
    
    def _create_backup(self, file_path: Path) -> Path:
        """创建文件备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def _restore_backup(self, original_path: Path, backup_path: Path) -> None:
        """恢复备份"""
        if backup_path.exists():
            shutil.copy2(backup_path, original_path)
            self.logger.info(f"Backup restored: {original_path}")

    def restore_backup(self, file_path: str, backup_path: str) -> Dict:
        """
        从指定备份恢复文件。

        Args:
            file_path: 工作区内相对路径
            backup_path: 备份文件路径
        """
        original_path = self.workspace / file_path
        backup = Path(backup_path)

        if not backup.exists():
            self.logger.warning(f"[Patcher] 备份不存在，无法恢复 | backup={backup}")
            return {
                "status": "warning",
                "path": file_path,
                "reason": "backup_not_found",
                "backup_path": str(backup),
            }

        self._restore_backup(original_path, backup)
        return {
            "status": "success",
            "path": file_path,
            "backup_path": str(backup),
        }
    
    def rollback_last_operation(self) -> Dict:
        """回滚最后一个操作"""
        if not self.operations_log:
            self.logger.warning("No operations to rollback")
            return {"status": "failed", "reason": "No operations"}
        
        operation = self.operations_log.pop()
        self.logger.info(f"[Patcher] 回滚操作 | type={operation['type']} | path={operation['path']}")
        
        if operation["backup_path"]:
            backup_path = Path(operation["backup_path"])
            if backup_path.exists():
                original_path = self.workspace / operation["path"]
                self._restore_backup(original_path, backup_path)
                return {"status": "success", "operation": operation}
        
        return {"status": "warning", "reason": "No backup available"}
    
    def rollback_all(self) -> List[Dict]:
        """回滚所有操作"""
        results = []
        while self.operations_log:
            result = self.rollback_last_operation()
            results.append(result)
        return results
    
    def get_operations_log(self) -> List[Dict]:
        """获取操作日志"""
        return self.operations_log.copy()
    
    def clear_backups(self, days_old: int = 7) -> int:
        """清理旧备份"""
        if not self.backup_enabled or not self.backup_dir.exists():
            return 0
        
        import time
        current_time = time.time()
        deleted_count = 0
        
        for backup_file in self.backup_dir.glob("*.bak"):
            file_age = current_time - backup_file.stat().st_mtime
            if file_age > (days_old * 24 * 3600):
                backup_file.unlink()
                deleted_count += 1
        
        self.logger.info(f"[Patcher] 清理旧备份 | deleted={deleted_count}")
        return deleted_count
