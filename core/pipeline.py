"""
执行流程管理模块
"""
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineContext:
    """
    流程执行上下文
    """
    session_id: str
    session_dir: Path
    task_type: str
    language: str
    workspace_root: str
    user_query: str
    
    # 各阶段输出
    analysis_result: Optional[Dict[str, Any]] = None  # 代码分析结果
    retrieval_results: Optional[List[Dict]] = None  # 检索结果
    prompt: Optional[str] = None  # 最终 prompt
    llm_response: Optional[str] = None  # LLM 原始输出
    diff: Optional[str] = None  # 生成的 patch
    validation_output: Optional[str] = None  # 验证命令输出
    final_result: Optional[str] = None  # 最终结果总结


class Pipeline:
    """
    流程编排器
    """
    
    def __init__(self, context: PipelineContext):
        self.context = context
        self.logger = get_logger(__name__)
    
    def log_stage(self, stage_num: int, stage_name: str, details: str = ""):
        """
        打印当前执行阶段
        
        Args:
            stage_num: 阶段号
            stage_name: 阶段名称
            details: 额外的详细信息
        """
        if details:
            self.logger.info(f"[Stage {stage_num}] {stage_name} | {details}")
        else:
            self.logger.info(f"[Stage {stage_num}] {stage_name}")
    
    def log_substage(self, main_stage: int, sub_stage: int, name: str, details: str = ""):
        """
        打印子阶段
        
        Args:
            main_stage: 主阶段号
            sub_stage: 子阶段号
            name: 子阶段名称
            details: 额外的详细信息
        """
        if details:
            self.logger.info(f"[Stage {main_stage}.{sub_stage}] {name} | {details}")
        else:
            self.logger.info(f"[Stage {main_stage}.{sub_stage}] {name}")
    
    def save_context_snapshot(self, filename: str, content: str) -> Path:
        """
        保存上下文快照（用于调试和后续查看）
        
        Args:
            filename: 文件名
            content: 内容
        
        Returns:
            保存的文件路径
        """
        file_path = self.context.session_dir / filename
        try:
            file_path.write_text(content, encoding="utf-8")
            return file_path
        except Exception as e:
            self.logger.error(f"保存快照失败 | filename={filename} | error={e}")
            raise
    
    def get_session_artifact_path(self, artifact_name: str) -> Path:
        """
        获取 artifact 文件路径
        
        Args:
            artifact_name: artifact 名称
        
        Returns:
            文件路径
        """
        return self.context.session_dir / artifact_name
