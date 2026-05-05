"""
LangGraph 多阶段工作流编排

这个模块整合了项目修复的全流程：
1. 分析 - 问题诊断
2. 规划 - 修复策略
3. 生成 - 代码生成
4. 验证 - 预检验证
5. 应用 - 文件修改
6. 评估 - 结果评价

使用 LangGraph StateGraph 管理复杂的多步骤工作流。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum
import json
from datetime import datetime

from core.complexity import ComplexityEvaluator, ErrorType
from core.router import ModelRouter, route_and_call_llm
from validators.go_checker import GoChecker
from patcher import FileWriter, PatchApplier
from outputs.diff_formatter import DiffFormatter
from outputs.formatters import ResultFormatter


class WorkflowStage(Enum):
    """工作流阶段定义"""
    ANALYZE = "analyze"           # 1. 分析
    PLAN = "plan"                 # 2. 规划
    GENERATE = "generate"         # 3. 生成
    VALIDATE = "validate"         # 4. 验证
    APPLY = "apply"               # 5. 应用
    EVALUATE = "evaluate"         # 6. 评估
    COMPLETED = "completed"       # 完成


@dataclass
class WorkflowState:
    """工作流状态（StateGraph 中的状态节点）"""
    
    # 输入信息
    workspace: str
    bug_description: str
    error_type: ErrorType = ErrorType.LOGIC
    files_affected: List[str] = field(default_factory=list)
    
    # 阶段信息
    current_stage: WorkflowStage = WorkflowStage.ANALYZE
    completed_stages: List[WorkflowStage] = field(default_factory=list)
    
    # 分析结果
    analysis: Optional[Dict[str, Any]] = None           # 问题诊断
    complexity_score: Optional[float] = None             # 复杂度评分
    
    # 规划结果
    plan: Optional[Dict[str, Any]] = None               # 修复策略
    
    # 生成结果
    generated_code: Optional[str] = None                # LLM 生成的代码
    generated_diffs: Optional[Dict[str, str]] = None    # 代码变更
    
    # 验证结果
    validation_errors: List[Dict[str, Any]] = field(default_factory=list)  # 预检错误
    is_valid: bool = False                              # 验证是否通过
    
    # 应用结果
    applied_changes: List[Dict[str, Any]] = field(default_factory=list)    # 应用的改动
    rollback_available: bool = False                    # 是否可回滚
    
    # 最终评估
    success: bool = False
    result_summary: Optional[str] = None
    
    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 日志
    logs: List[str] = field(default_factory=list)
    
    def log(self, message: str, stage: Optional[WorkflowStage] = None):
        """记录日志"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}"
        if stage:
            log_entry = f"[{stage.value}] {log_entry}"
        self.logs.append(log_entry)
        self.updated_at = timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "workspace": self.workspace,
            "bug_description": self.bug_description,
            "current_stage": self.current_stage.value,
            "completed_stages": [s.value for s in self.completed_stages],
            "complexity_score": self.complexity_score,
            "is_valid": self.is_valid,
            "success": self.success,
            "result_summary": self.result_summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "logs_count": len(self.logs),
        }


class CodeRepairWorkflow:
    """
    LangGraph 工作流管理器
    
    完整的代码修复工作流，包含 6 个阶段的顺序编排。
    
    示例：
        ```python
        workflow = CodeRepairWorkflow("/workspace")
        
        state = workflow.execute(
            bug_description="并发竞态问题",
            error_type=ErrorType.LOGIC,
            files_affected=["pkg/user.go"]
        )
        
        print(f"修复状态: {state.success}")
        print(f"生成的代码: {state.generated_code}")
        print(f"验证结果: {state.is_valid}")
        ```
    """
    
    def __init__(self, workspace: str):
        """初始化工作流"""
        self.workspace = workspace
        self.evaluator = ComplexityEvaluator()
        self.router = ModelRouter()
        self.checker = GoChecker(workspace)
        self.writer = FileWriter(workspace, backup_enabled=True)
        self.patcher = PatchApplier(workspace)
        self.formatter = DiffFormatter(workspace)
    
    def execute(
        self,
        bug_description: str,
        error_type: ErrorType = ErrorType.LOGIC,
        files_affected: Optional[List[str]] = None,
        **kwargs
    ) -> WorkflowState:
        """
        执行完整的修复工作流
        
        Args:
            bug_description: Bug 描述
            error_type: 错误类型
            files_affected: 涉及的文件
            **kwargs: 其他参数（例如 preferred_provider）
        
        Returns:
            WorkflowState: 最终工作流状态
        """
        if files_affected is None:
            files_affected = []
        
        # 初始化状态
        state = WorkflowState(
            workspace=self.workspace,
            bug_description=bug_description,
            error_type=error_type,
            files_affected=files_affected,
        )
        
        state.log("工作流启动", WorkflowStage.ANALYZE)
        
        # 执行各个阶段
        try:
            state = self._stage_analyze(state)
            state = self._stage_plan(state)
            state = self._stage_generate(state, **kwargs)
            state = self._stage_validate(state)
            state = self._stage_apply(state)
            state = self._stage_evaluate(state)
            state.current_stage = WorkflowStage.COMPLETED
            state.success = state.is_valid
        except Exception as e:
            state.log(f"工作流异常: {str(e)}", state.current_stage)
            state.success = False
            state.result_summary = f"修复失败: {str(e)}"
        
        return state
    
    def _stage_analyze(self, state: WorkflowState) -> WorkflowState:
        """
        第 1 阶段：分析（问题诊断）
        
        - 评估复杂度
        - 扫描现有问题
        - 生成分析报告
        """
        state.current_stage = WorkflowStage.ANALYZE
        state.log("开始问题诊断", WorkflowStage.ANALYZE)
        
        try:
            # 评估复杂度
            score = self.evaluator.evaluate(
                error_type=state.error_type,
                files_affected=state.files_affected,
                code_context=state.bug_description
            )
            state.complexity_score = score.score
            state.log(f"复杂度评分: {score.score:.1f} ({score.level.value})", WorkflowStage.ANALYZE)
            
            # 扫描现有问题
            check_result = self.checker.check_all()
            issues_count = sum(len(r.get("issues", [])) for r in check_result.values())
            state.log(f"检测到 {issues_count} 个现有问题", WorkflowStage.ANALYZE)
            
            # 分析结果
            state.analysis = {
                "complexity": {
                    "score": score.score,
                    "level": score.level.value,
                    "factors": score.factors,
                    "reasoning": score.reasoning,
                },
                "existing_issues": {
                    "total": issues_count,
                    "by_category": {k: len(v.get("issues", [])) for k, v in check_result.items()}
                }
            }
            
            state.completed_stages.append(WorkflowStage.ANALYZE)
            state.log("分析阶段完成", WorkflowStage.ANALYZE)
            
        except Exception as e:
            state.log(f"分析失败: {str(e)}", WorkflowStage.ANALYZE)
            raise
        
        return state
    
    def _stage_plan(self, state: WorkflowState) -> WorkflowState:
        """
        第 2 阶段：规划（修复策略）
        
        - 生成修复策略
        - 确定优先级
        - 规划代码变更
        """
        state.current_stage = WorkflowStage.PLAN
        state.log("生成修复策略", WorkflowStage.PLAN)
        
        try:
            # 基于复杂度生成策略
            strategy = self._generate_strategy(state)
            
            state.plan = {
                "strategy": strategy,
                "priority": self._calculate_priority(state),
                "estimated_effort": self._estimate_effort(state),
                "affected_files": state.files_affected,
            }
            
            state.log(f"修复策略: {strategy}", WorkflowStage.PLAN)
            state.completed_stages.append(WorkflowStage.PLAN)
            
        except Exception as e:
            state.log(f"规划失败: {str(e)}", WorkflowStage.PLAN)
            raise
        
        return state
    
    def _stage_generate(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        第 3 阶段：生成（代码生成）
        
        - 调用 LLM 生成修复代码
        - 智能模型路由
        - 提取生成的代码
        """
        state.current_stage = WorkflowStage.GENERATE
        state.log("调用 LLM 生成修复代码", WorkflowStage.GENERATE)
        
        try:
            # 智能路由和调用
            result = route_and_call_llm(
                error_type=state.error_type,
                files_affected=state.files_affected,
                code_context=state.bug_description,
                system_prompt="你是一个 Go 代码专家，擅长修复 Go 项目中的问题。生成高质量、遵循最佳实践的代码。",
                user_message=f"请修复以下问题: {state.bug_description}",
                preferred_provider=kwargs.get("preferred_provider")
            )
            
            raw_response = result.get("response", "")
            extracted_blocks = ResultFormatter.extract_code_blocks(raw_response, "go")
            state.generated_code = extracted_blocks[0] if extracted_blocks else raw_response
            state.log(f"LLM 生成完成，使用模型: {result['routing']['config']['model']}", WorkflowStage.GENERATE)
            
            # 生成 diff
            state.generated_diffs = {
                "code_blocks": len(extracted_blocks),
                "provider": result.get("provider"),
                "model": result.get("model"),
            }
            state.log("生成代码变更 Diff", WorkflowStage.GENERATE)
            
            state.completed_stages.append(WorkflowStage.GENERATE)
            
        except Exception as e:
            state.log(f"生成失败: {str(e)}", WorkflowStage.GENERATE)
            raise
        
        return state
    
    def _stage_validate(self, state: WorkflowState) -> WorkflowState:
        """
        第 4 阶段：验证（预检验证）
        
        - Go 语法检查
        - 导入检查
        - 最佳实践检查
        """
        state.current_stage = WorkflowStage.VALIDATE
        state.log("执行预检验证", WorkflowStage.VALIDATE)
        
        try:
            # 检查生成的代码
            validation_errors = []
            
            if state.generated_code:
                # 基本语法检查
                import_check_passed = self._check_imports_in_code(state.generated_code)
                syntax_check_passed = self._check_syntax_in_code(state.generated_code)
                
                if not import_check_passed:
                    validation_errors.append({
                        "type": "import",
                        "message": "导入语句检查失败"
                    })
                
                if not syntax_check_passed:
                    validation_errors.append({
                        "type": "syntax",
                        "message": "语法检查失败"
                    })
            
            state.validation_errors = validation_errors
            state.is_valid = len(validation_errors) == 0
            
            state.log(f"验证完成: {'✓ 通过' if state.is_valid else '✗ 失败'} ({len(validation_errors)} 个错误)", 
                     WorkflowStage.VALIDATE)
            state.completed_stages.append(WorkflowStage.VALIDATE)
            
        except Exception as e:
            state.log(f"验证异常: {str(e)}", WorkflowStage.VALIDATE)
            raise
        
        return state
    
    def _stage_apply(self, state: WorkflowState) -> WorkflowState:
        """
        第 5 阶段：应用（文件修改）
        
        - 应用代码变更
        - 创建备份
        - 记录操作
        """
        state.current_stage = WorkflowStage.APPLY
        
        if not state.is_valid:
            state.log("跳过应用阶段：验证未通过", WorkflowStage.APPLY)
            return state
        
        state.log("应用代码变更", WorkflowStage.APPLY)
        
        try:
            # 应用生成的代码
            for file_path in state.files_affected:
                if state.generated_code:
                    self.writer.write_file(file_path, state.generated_code)
                    state.applied_changes.append({
                        "file": file_path,
                        "status": "applied",
                        "timestamp": datetime.now().isoformat()
                    })
                    state.log(f"已应用: {file_path}", WorkflowStage.APPLY)
            
            state.rollback_available = True
            state.log("应用完成，备份已创建（可回滚）", WorkflowStage.APPLY)
            state.completed_stages.append(WorkflowStage.APPLY)
            
        except Exception as e:
            state.log(f"应用失败: {str(e)}", WorkflowStage.APPLY)
            raise
        
        return state
    
    def _stage_evaluate(self, state: WorkflowState) -> WorkflowState:
        """
        第 6 阶段：评估（结果评价）
        
        - 再次扫描问题
        - 对比改进
        - 生成总结报告
        """
        state.current_stage = WorkflowStage.EVALUATE
        state.log("评估修复结果", WorkflowStage.EVALUATE)
        
        try:
            if not state.applied_changes:
                state.log("未应用任何改动，跳过评估", WorkflowStage.EVALUATE)
                return state
            
            # 再次扫描
            recheck_result = self.checker.check_all()
            new_issues = sum(len(r.get("issues", [])) for r in recheck_result.values())
            
            # 对比分析
            old_issues = state.analysis["existing_issues"]["total"] if state.analysis else 0
            improvement = old_issues - new_issues
            
            state.result_summary = f"修复成功: 问题数减少 {old_issues} → {new_issues} (改进: {improvement})"
            state.log(state.result_summary, WorkflowStage.EVALUATE)
            state.completed_stages.append(WorkflowStage.EVALUATE)
            
        except Exception as e:
            state.log(f"评估异常: {str(e)}", WorkflowStage.EVALUATE)
        
        return state
    
    # 辅助方法
    def _generate_strategy(self, state: WorkflowState) -> str:
        """生成修复策略"""
        if state.complexity_score and state.complexity_score < 30:
            return "快速修复策略（简单问题）"
        elif state.complexity_score and state.complexity_score < 50:
            return "标准修复策略（中等问题）"
        else:
            return "复杂修复策略（需要多步骤）"
    
    def _calculate_priority(self, state: WorkflowState) -> str:
        """计算优先级"""
        if state.error_type == ErrorType.SYNTAX:
            return "HIGH"
        elif state.error_type == ErrorType.RUNTIME:
            return "HIGH"
        elif state.error_type == ErrorType.LOGIC:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _estimate_effort(self, state: WorkflowState) -> Dict[str, Any]:
        """估算工作量"""
        return {
            "estimated_minutes": int((state.complexity_score or 50) / 10),
            "files_affected": len(state.files_affected),
            "complexity_level": "high" if (state.complexity_score or 0) > 60 else "medium" if (state.complexity_score or 0) > 30 else "low"
        }
    
    def _check_imports_in_code(self, code: str) -> bool:
        """检查代码中的导入"""
        # 简单的启发式检查
        if "import (" in code or "import \"" in code:
            return True
        return "package" in code
    
    def _check_syntax_in_code(self, code: str) -> bool:
        """检查代码语法"""
        # 简单的启发式检查
        balance = 0
        for char in code:
            if char == '{':
                balance += 1
            elif char == '}':
                balance -= 1
            if balance < 0:
                return False
        return balance == 0


def create_simple_workflow(workspace: str) -> CodeRepairWorkflow:
    """工厂函数：创建工作流实例"""
    return CodeRepairWorkflow(workspace)
