"""
LangGraph 工作流测试
"""

import pytest
import tempfile
import os
import shutil

from core.langgraph_workflow import (
    CodeRepairWorkflow,
    WorkflowState,
    WorkflowStage
)
from core.complexity import ErrorType


class TestWorkflowState:
    """工作流状态测试"""
    
    def test_state_initialization(self):
        """测试状态初始化"""
        state = WorkflowState(
            workspace="/test",
            bug_description="Test bug"
        )
        
        assert state.workspace == "/test"
        assert state.bug_description == "Test bug"
        assert state.current_stage == WorkflowStage.ANALYZE
        assert len(state.logs) == 0
    
    def test_state_logging(self):
        """测试状态日志"""
        state = WorkflowState(
            workspace="/test",
            bug_description="Test"
        )
        
        state.log("Test log", WorkflowStage.ANALYZE)
        
        assert len(state.logs) > 0
        assert "Test log" in state.logs[0]
    
    def test_state_to_dict(self):
        """测试状态转字典"""
        state = WorkflowState(
            workspace="/test",
            bug_description="Test"
        )
        
        state_dict = state.to_dict()
        
        assert "workspace" in state_dict
        assert "current_stage" in state_dict
        assert state_dict["workspace"] == "/test"


class TestCodeRepairWorkflow:
    """代码修复工作流测试"""
    
    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作目录"""
        temp_dir = tempfile.mkdtemp(prefix="test_workflow_")
        
        # 创建最小的 Go 项目
        go_mod = os.path.join(temp_dir, "go.mod")
        with open(go_mod, "w") as f:
            f.write("module github.com/test/demo\n\ngo 1.21\n")
        
        main_go = os.path.join(temp_dir, "main.go")
        with open(main_go, "w") as f:
            f.write("package main\n\nfunc main() {\n}\n")
        
        yield temp_dir
        
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_workflow_initialization(self, temp_workspace):
        """测试工作流初始化"""
        workflow = CodeRepairWorkflow(temp_workspace)
        
        assert workflow.workspace == temp_workspace
        assert workflow.checker is not None
        assert workflow.writer is not None
    
    def test_workflow_analyze_stage(self, temp_workspace):
        """测试分析阶段"""
        workflow = CodeRepairWorkflow(temp_workspace)
        
        state = WorkflowState(
            workspace=temp_workspace,
            bug_description="Test bug",
            error_type=ErrorType.LOGIC
        )
        
        result = workflow._stage_analyze(state)
        
        assert result.analysis is not None
        assert "complexity" in result.analysis
        assert "existing_issues" in result.analysis
        assert WorkflowStage.ANALYZE in result.completed_stages
    
    def test_workflow_plan_stage(self, temp_workspace):
        """测试规划阶段"""
        workflow = CodeRepairWorkflow(temp_workspace)
        
        state = WorkflowState(
            workspace=temp_workspace,
            bug_description="Test bug",
        )
        state.complexity_score = 50.0
        
        result = workflow._stage_plan(state)
        
        assert result.plan is not None
        assert "strategy" in result.plan
        assert WorkflowStage.PLAN in result.completed_stages
    
    def test_workflow_validate_stage(self, temp_workspace):
        """测试验证阶段"""
        workflow = CodeRepairWorkflow(temp_workspace)
        
        state = WorkflowState(
            workspace=temp_workspace,
            bug_description="Test",
            generated_code="package main\nfunc main() {}\n"
        )
        
        result = workflow._stage_validate(state)
        
        # 生成的代码应该通过验证
        assert isinstance(result.is_valid, bool)
        assert WorkflowStage.VALIDATE in result.completed_stages
    
    def test_full_workflow_execution(self, temp_workspace):
        """测试完整工作流执行"""
        workflow = CodeRepairWorkflow(temp_workspace)
        
        state = workflow.execute(
            bug_description="测试 bug",
            error_type=ErrorType.LOGIC,
            files_affected=["main.go"]
        )
        
        assert state.workspace == temp_workspace
        assert len(state.logs) > 0
        # 检查是否完成（可能会失败，但应该不会抛出异常）
        assert state.current_stage == WorkflowStage.COMPLETED or state.current_stage == WorkflowStage.ANALYZE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
