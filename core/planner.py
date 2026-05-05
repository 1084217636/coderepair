"""
任务规划与分类模块
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from core.logger import get_logger

logger = get_logger(__name__)


class TaskType(Enum):
    """任务类型枚举"""
    NEW_FEATURE = "feature"  # 新功能开发
    BUG_FIX = "bug_fix"      # Bug 修复
    CODE_REVIEW = "review"   # 代码审查
    FOLLOW_UP = "follow_up"  # 继续追问
    UNKNOWN = "unknown"      # 未知类型


class Language(Enum):
    """编程语言枚举"""
    GO = "go"
    PYTHON = "python"
    UNKNOWN = "unknown"


@dataclass
class TaskPlan:
    """任务计划"""
    task_type: TaskType
    language: Language
    user_query: str
    session_id: Optional[str] = None  # 如果是 follow-up，记录上一轮的 session_id


class TaskPlanner:
    """
    任务分类与规划器
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def classify_task(self, user_input: str, session_id: Optional[str] = None) -> TaskType:
        """
        分类用户输入的任务类型
        
        Args:
            user_input: 用户输入文本
            session_id: 如果提供，表示这是一个 follow-up
        
        Returns:
            TaskType 枚举值
        """
        self.logger.info(f"[Stage 1.1] 开始任务分类 | input_length={len(user_input)}")
        
        if session_id:
            self.logger.info(f"[Stage 1.1] 检测到会话 ID，分类为 FOLLOW_UP | session_id={session_id}")
            return TaskType.FOLLOW_UP
        
        # 简单的关键词匹配
        lower_input = user_input.lower()
        
        # Bug 类关键词
        bug_keywords = ["bug", "报错", "错误", "修复", "crash", "panic", "fail", "error", "fix"]
        
        # 新功能关键词
        feature_keywords = ["新增", "功能", "能否支持", "实现", "添加", "feature", "add", "implement"]
        
        # 审查关键词
        review_keywords = ["审查", "review", "检查", "检测", "建议", "优化"]
        
        if any(kw in lower_input for kw in bug_keywords):
            self.logger.info("[Stage 1.1] 检测到关键词 → 分类为 BUG_FIX")
            return TaskType.BUG_FIX
        elif any(kw in lower_input for kw in feature_keywords):
            self.logger.info("[Stage 1.1] 检测到关键词 → 分类为 NEW_FEATURE")
            return TaskType.NEW_FEATURE
        elif any(kw in lower_input for kw in review_keywords):
            self.logger.info("[Stage 1.1] 检测到关键词 → 分类为 CODE_REVIEW")
            return TaskType.CODE_REVIEW
        else:
            self.logger.info("[Stage 1.1] 未匹配关键词 → 分类为 UNKNOWN（当作新功能处理）")
            return TaskType.NEW_FEATURE  # 默认当作新功能
    
    def detect_language(self, workspace_root: str) -> Language:
        """
        检测项目编程语言
        
        Args:
            workspace_root: 项目根目录路径
        
        Returns:
            Language 枚举值
        """
        from pathlib import Path
        
        self.logger.info(f"[Stage 1.2] 开始语言检测 | workspace_root={workspace_root}")
        
        root = Path(workspace_root)
        
        # 扫描文件，判断主要编程语言
        go_files = list(root.rglob("*.go"))
        py_files = list(root.rglob("*.py"))
        
        self.logger.debug(f"[Stage 1.2] 扫描结果 | .go 文件数={len(go_files)} | .py 文件数={len(py_files)}")
        
        if go_files and len(go_files) >= len(py_files):
            self.logger.info("[Stage 1.2] 主要语言检测为 GO")
            return Language.GO
        elif py_files:
            self.logger.info("[Stage 1.2] 主要语言检测为 PYTHON")
            return Language.PYTHON
        else:
            self.logger.warning("[Stage 1.2] 未检测到主要语言，使用 UNKNOWN")
            return Language.UNKNOWN
    
    def plan(self, user_input: str, workspace_root: str, session_id: Optional[str] = None) -> TaskPlan:
        """
        生成完整的任务计划
        
        Args:
            user_input: 用户输入
            workspace_root: 项目根目录
            session_id: 可选的上一轮 session_id（用于 follow-up）
        
        Returns:
            TaskPlan 对象
        """
        self.logger.info("=" * 60)
        self.logger.info("[Stage 1] 任务规划与分类")
        self.logger.info("=" * 60)
        
        task_type = self.classify_task(user_input, session_id)
        language = self.detect_language(workspace_root)
        
        plan = TaskPlan(
            task_type=task_type,
            language=language,
            user_query=user_input,
            session_id=session_id
        )
        
        self.logger.info(f"[Stage 1] 规划完成 | task_type={plan.task_type.value} | language={plan.language.value}")
        
        return plan
