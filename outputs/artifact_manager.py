"""
Artifact 管理模块 - 保存执行过程的所有信息
"""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from core.logger import get_logger, setup_logger

logger = get_logger(__name__)


class ArtifactManager:
    """
    Artifact 管理器
    
    职责：
    1. 创建 session 目录
    2. 保存各阶段的输出（prompt、response、diff、日志等）
    3. 组织输出便于后续查看和分析
    """
    
    def __init__(self, artifacts_root: Path):
        """
        初始化 Artifact 管理器
        
        Args:
            artifacts_root: artifacts 根目录
        """
        self.artifacts_root = artifacts_root
        self.logger = get_logger(__name__)
        self.current_session_dir: Path = None
    
    def create_session(
        self,
        session_id: str,
        keep_last: Optional[int] = None,
        retention_days: Optional[int] = None,
    ) -> Path:
        """
        创建新的 session 目录
        
        Args:
            session_id: session 标识符（建议时间戳）
        
        Returns:
            创建的 session 目录路径
        """
        session_dir = self.artifacts_root / f"session_{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_session_dir = session_dir
        
        # 为当前 session 启用文件日志
        log_file = session_dir / "runner.log"
        setup_logger(log_file)
        
        self.logger.info(f"[Artifacts] 创建 session | session_id={session_id} | dir={session_dir}")

        if keep_last or retention_days:
            cleanup_result = self.prune_sessions(
                keep_last=keep_last,
                retention_days=retention_days,
            )
            if cleanup_result["deleted_count"] > 0:
                self.logger.info(
                    "[Artifacts] 已清理旧 session | deleted=%s | keep_last=%s | retention_days=%s",
                    cleanup_result["deleted_count"],
                    keep_last,
                    retention_days,
                )

        return session_dir
    
    def save_artifact(self, filename: str, content: str) -> Path:
        """
        保存文本型 artifact
        
        Args:
            filename: 文件名
            content: 内容
        
        Returns:
            保存的文件路径
        """
        if not self.current_session_dir:
            raise RuntimeError("当前没有活跃的 session，请先调用 create_session()")
        
        file_path = self.current_session_dir / filename
        
        try:
            file_path.write_text(content, encoding="utf-8")
            self.logger.debug(f"[Artifacts] 保存文件 | filename={filename}")
            return file_path
        except Exception as e:
            self.logger.error(f"[Artifacts] 保存失败 | filename={filename} | error={e}")
            raise
    
    def save_json_artifact(self, filename: str, data: Dict[str, Any]) -> Path:
        """
        保存 JSON 型 artifact
        
        Args:
            filename: 文件名（应以 .json 结尾）
            data: 数据字典
        
        Returns:
            保存的文件路径
        """
        if not self.current_session_dir:
            raise RuntimeError("当前没有活跃的 session，请先调用 create_session()")
        
        file_path = self.current_session_dir / filename
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"[Artifacts] 保存 JSON 文件 | filename={filename}")
            return file_path
        except Exception as e:
            self.logger.error(f"[Artifacts] 保存 JSON 失败 | filename={filename} | error={e}")
            raise
    
    def get_session_dir(self) -> Path:
        """
        获取当前 session 目录
        
        Returns:
            session 目录路径
        """
        if not self.current_session_dir:
            raise RuntimeError("当前没有活跃的 session")
        return self.current_session_dir
    
    def list_sessions(self, limit: int = 10) -> list:
        """
        列出所有 session
        
        Args:
            limit: 返回的最大数量
        
        Returns:
            session 目录列表（按时间倒序）
        """
        sessions = sorted(
            self.artifacts_root.glob("session_*"),
            key=lambda p: p.name,
            reverse=True
        )
        return sessions[:limit]

    def prune_sessions(
        self,
        keep_last: Optional[int] = None,
        retention_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        清理旧 session，避免 artifacts 无限增长。

        删除规则：
        - 超出 keep_last 的旧 session 会被删除
        - 或者 session 修改时间早于 retention_days 的也会被删除
        """
        session_dirs = sorted(
            self.artifacts_root.glob("session_*"),
            key=lambda p: p.name,
            reverse=True,
        )
        if not session_dirs:
            return {"deleted_count": 0, "deleted_sessions": []}

        keep_last = keep_last if keep_last is not None and keep_last > 0 else None
        retention_days = retention_days if retention_days is not None and retention_days > 0 else None
        cutoff = (
            datetime.now() - timedelta(days=retention_days)
            if retention_days is not None
            else None
        )

        deleted_sessions = []
        for index, session_dir in enumerate(session_dirs):
            if self.current_session_dir and session_dir == self.current_session_dir:
                continue

            delete_by_count = keep_last is not None and index >= keep_last
            delete_by_age = cutoff is not None and datetime.fromtimestamp(session_dir.stat().st_mtime) < cutoff
            if not delete_by_count and not delete_by_age:
                continue

            shutil.rmtree(session_dir, ignore_errors=True)
            deleted_sessions.append(session_dir.name)

        return {
            "deleted_count": len(deleted_sessions),
            "deleted_sessions": deleted_sessions,
        }
