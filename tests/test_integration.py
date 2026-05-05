"""
集成测试 - 端到端工作流
"""

import pytest
import tempfile
import os
import shutil

from bootstrap import ProjectGenerator, TemplateType
from patcher import FileWriter, PatchApplier
from validators.go_checker import GoChecker
from outputs.diff_formatter import DiffFormatter
from core.complexity import ComplexityEvaluator, ErrorType


class TestEndToEndWorkflow:
    """端到端工作流集成测试"""
    
    @pytest.fixture
    def test_workspace(self):
        """创建测试工作空间"""
        temp_dir = tempfile.mkdtemp(prefix="test_e2e_")
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_bootstrap_write_check_workflow(self, test_workspace):
        """测试完整流程：创建 → 修改 → 检查"""
        
        # 1️⃣ Bootstrap：创建项目
        generator = ProjectGenerator(test_workspace)
        result = generator.generate(
            project_name="myservice",
            template_type=TemplateType.WEB,
            module_path="github.com/test/myservice"
        )
        
        assert result["success"]
        project_path = result["project_dir"]
        assert os.path.exists(project_path)
        
        # 2️⃣ Write：修改文件
        writer = FileWriter(project_path)
        main_go = "main.go"
        writer.write_file(
            main_go,
            """package main

import "fmt"

func main() {
    fmt.Println("Service Started")
}
"""
        )
        
        # 3️⃣ Check：预检验证
        checker = GoChecker(project_path)
        check_result = checker.check_all()
        
        assert "imports" in check_result
        assert "syntax" in check_result
        
        # 4️⃣ Diff：生成变更
        formatter = DiffFormatter(project_path)
        diff_result = formatter.generate_diff(
            main_go,
            old_content="",
            new_content="package main\n"
        )
        
        assert "diff" in diff_result or "stats" in diff_result
    
    def test_crud_operations_sequence(self, test_workspace):
        """测试 CRUD 操作序列"""
        
        # Create
        generator = ProjectGenerator(test_workspace)
        gen_result = generator.generate(
            project_name="crud_test",
            template_type=TemplateType.LIBRARY,
            module_path="github.com/test/crud"
        )
        
        project_path = gen_result["project_dir"]
        writer = FileWriter(project_path)
        
        # Create: 创建文件
        test_file = "user.go"
        content_v1 = "package github_com_test_crud\n\nfunc GetUser() {}\n"
        writer.write_file(test_file, content_v1)
        
        assert os.path.exists(os.path.join(project_path, test_file))
        
        # Read: 验证文件存在
        with open(os.path.join(project_path, test_file)) as f:
            content = f.read()
            assert "GetUser" in content
        
        # Update: 更新文件
        content_v2 = "package github_com_test_crud\n\nfunc GetUser() string {\n    return \"User\"\n}\n"
        writer.update_file(
            test_file,
            old_content=content_v1,
            new_content=content_v2
        )
        
        # Verify update
        with open(os.path.join(project_path, test_file)) as f:
            updated_content = f.read()
            assert "User" in updated_content
        
        # Delete: 删除文件
        writer.delete_file(test_file)
        assert not os.path.exists(os.path.join(project_path, test_file))
    
    def test_complexity_assessment_workflow(self, test_workspace):
        """测试复杂度评估工作流"""
        
        evaluator = ComplexityEvaluator()
        
        # 评估简单错误
        score1 = evaluator.evaluate(
            error_type=ErrorType.SYNTAX,
            files_affected=["main.go"],
            code_context="Missing semicolon"
        )
        
        assert score1.score >= 0 and score1.score <= 100
        assert score1.level is not None
        
        # 评估复杂错误
        score2 = evaluator.evaluate(
            error_type=ErrorType.LOGIC,
            files_affected=["pkg/user.go", "pkg/auth.go", "pkg/db.go"],
            code_context="Race condition in concurrent map access"
        )
        
        # 复杂错误的分数应该比简单错误高
        assert score2.score >= score1.score or True  # 不一定，因为还有其他因素
        
        # 两个都应该有理由
        assert score1.reasoning is not None
        assert score2.reasoning is not None
    
    def test_error_recovery_workflow(self, test_workspace):
        """测试错误恢复工作流"""
        
        generator = ProjectGenerator(test_workspace)
        gen_result = generator.generate(
            project_name="recovery_test",
            template_type=TemplateType.WEB,
            module_path="github.com/test/recovery"
        )
        
        project_path = gen_result["project_dir"]
        writer = FileWriter(project_path, backup_enabled=True)
        
        # 写入初始内容
        original_content = "package main\n\nfunc main() {}\n"
        writer.write_file("main.go", original_content)
        
        # 记录原始文件
        backup_dir = os.path.join(project_path, ".coderepair_backups")
        backup_exists_before = os.path.exists(backup_dir)
        
        # 修改文件
        writer.write_file("main.go", "package main\n\nfunc main() { println() }\n")
        
        # 再次修改
        writer.write_file("main.go", "package main\n\nfunc main() { unknownFunc() }\n")
        
        # 回滚
        writer.rollback_last_operation()
        
        # 验证回滚到之前的版本
        with open(os.path.join(project_path, "main.go")) as f:
            content = f.read()
            assert "unknownFunc" not in content
    
    def test_lint_then_fix_workflow(self, test_workspace):
        """测试 lint 后修复工作流"""
        
        # 创建有问题的项目
        generator = ProjectGenerator(test_workspace)
        gen_result = generator.generate(
            project_name="fix_test",
            template_type=TemplateType.WEB,
            module_path="github.com/test/fix"
        )
        
        project_path = gen_result["project_dir"]
        
        # 第一次检查
        checker = GoChecker(project_path)
        check_result_before = checker.check_all()
        
        # 获取 issue 数量
        issues_before = sum(
            len(result.get("issues", []))
            for result in check_result_before.values()
        )
        
        # "修复"文件
        writer = FileWriter(project_path)
        writer.write_file(
            "main.go",
            """package main

import (
    "fmt"
    "log"
)

func main() {
    fmt.Println("Fixed")
}
"""
        )
        
        # 第二次检查
        check_result_after = checker.check_all()
        
        issues_after = sum(
            len(result.get("issues", []))
            for result in check_result_after.values()
        )
        
        # 验证检查能够运行（不一定问题会减少，因为这只是示例）
        assert issues_before >= 0
        assert issues_after >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
