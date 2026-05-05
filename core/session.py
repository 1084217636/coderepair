"""
会话管理模块（用于支持多轮追问）
"""
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List
from datetime import datetime
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    task_type: str
    language: str
    workspace_root: str
    user_query: str
    created_at: str
    parent_session_id: Optional[str] = None
    
    # 历史信息（用于 follow-up）
    retrieval_summary: Optional[str] = None  # 上一轮检索结果摘要
    llm_output_summary: Optional[str] = None  # 上一轮 LLM 输出摘要
    feedback: Optional[str] = None  # 用户反馈或继续追问


class SessionManager:
    """
    会话管理器
    """
    
    def __init__(self, artifacts_root: Path):
        self.artifacts_root = artifacts_root
        self.logger = get_logger(__name__)
    
    def create_session_id(self) -> str:
        """生成新的 session_id"""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    def save_session(self, context: SessionContext, session_dir: Path) -> Path:
        """
        保存会话信息到文件
        
        Args:
            context: SessionContext 对象
            session_dir: 会话目录
        
        Returns:
            保存的 session 文件路径
        """
        session_file = session_dir / "session.json"
        
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(asdict(context), f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"[Session] 会话已保存 | session_id={context.session_id} | file={session_file}")
            return session_file
        except Exception as e:
            self.logger.error(f"[Session] 保存会话失败 | error={e}")
            raise
    
    def load_session(self, session_id: str) -> Optional[SessionContext]:
        """
        从文件加载会话
        
        Args:
            session_id: 会话 ID
        
        Returns:
            SessionContext 对象，或 None（如果不存在）
        """
        session_dir = self.artifacts_root / f"session_{session_id}"
        session_file = session_dir / "session.json"
        
        if not session_file.exists():
            self.logger.warning(f"[Session] 会话文件不存在 | session_id={session_id}")
            return None
        
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            context = SessionContext(**data)
            self.logger.info(f"[Session] 加载会话成功 | session_id={session_id}")
            return context
        except Exception as e:
            self.logger.error(f"[Session] 加载会话失败 | session_id={session_id} | error={e}")
            return None
    
    def add_feedback(self, session_id: str, feedback: str) -> bool:
        """
        为现有会话添加用户反馈（用于 follow-up）
        
        Args:
            session_id: 会话 ID
            feedback: 用户的继续追问文本
        
        Returns:
            成功返回 True
        """
        session_dir = self.artifacts_root / f"session_{session_id}"
        session_file = session_dir / "session.json"
        
        if not session_file.exists():
            self.logger.error(f"[Session] 会话不存在，无法添加反馈 | session_id={session_id}")
            return False
        
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            data["feedback"] = feedback
            
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"[Session] 反馈已添加 | session_id={session_id}")
            return True
        except Exception as e:
            self.logger.error(f"[Session] 添加反馈失败 | session_id={session_id} | error={e}")
            return False
    
    def list_recent_sessions(self, limit: int = 10) -> List[Path]:
        """
        列出最近的 session 目录
        
        Args:
            limit: 返回的最大数量
        
        Returns:
            session 目录列表（按时间倒序）
        """
        session_dirs = sorted(
            self.artifacts_root.glob("session_*"),
            key=lambda p: p.name,
            reverse=True
        )
        return session_dirs[:limit]
