"""
Bootstrap 模块测试
"""

import pytest
import tempfile
import os
import shutil
from pathlib import Path

from bootstrap import ProjectGenerator, TemplateType


class TestBootstrapGenerator:
    """Bootstrap 项目生成器测试"""
    
    @pytest.fixture
    def temp_workspace(self):
        """创建临时工作目录"""
        temp_dir = tempfile.mkdtemp(prefix="test_bootstrap_")
        yield temp_dir
        # 清理
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_generate_web_project(self, temp_workspace):
        """测试生成 Web API 项目"""
        generator = ProjectGenerator(temp_workspace)
        
        result = generator.generate(
            project_name="test_api",
            template_type=TemplateType.WEB,
            module_path="github.com/test/api"
        )
        
        assert result.get("status") == "success" or result.get("success")
        assert os.path.exists(result["project_dir"])
        assert os.path.exists(os.path.join(result["project_dir"], "go.mod"))
        assert os.path.exists(os.path.join(result["project_dir"], "main.go"))
        assert os.path.exists(os.path.join(result["project_dir"], "Makefile"))
    
    def test_generate_cli_project(self, temp_workspace):
        """测试生成 CLI 项目"""
        generator = ProjectGenerator(temp_workspace)
        
        result = generator.generate(
            project_name="test_cli",
            template_type=TemplateType.CLI,
            module_path="github.com/test/cli"
        )
        
        assert result.get("status") == "success" or result.get("success")
        assert os.path.exists(result["project_dir"])
        assert "cobra" in open(os.path.join(result["project_dir"], "go.mod")).read()
    
    def test_generate_library_project(self, temp_workspace):
        """测试生成库项目"""
        generator = ProjectGenerator(temp_workspace)
        
        result = generator.generate(
            project_name="test_lib",
            template_type=TemplateType.LIBRARY,
            module_path="github.com/test/lib"
        )
        
        assert result.get("status") == "success" or result.get("success")
        assert os.path.exists(result["project_dir"])
        assert os.path.exists(os.path.join(result["project_dir"], "lib.go"))
    
    def test_project_already_exists(self, temp_workspace):
        """测试项目已存在时的处理"""
        generator = ProjectGenerator(temp_workspace)
        
        # 第一次生成
        result1 = generator.generate(
            project_name="duplicate",
            template_type=TemplateType.WEB,
            module_path="github.com/test/dup"
        )
        assert result1.get("status") == "success" or result1.get("success")
        
        # 第二次生成相同项目
        result2 = generator.generate(
            project_name="duplicate",
            template_type=TemplateType.WEB,
            module_path="github.com/test/dup"
        )
        # 应该失败
        assert not (result2.get("status") == "success" or result2.get("success"))
    
    def test_invalid_module_path(self, temp_workspace):
        """测试无效的模块路径"""
        generator = ProjectGenerator(temp_workspace)
        
        result = generator.generate(
            project_name="test",
            template_type=TemplateType.WEB,
            module_path="invalid module path"  # 无效
        )
        # 不应该成功（或者应该处理异常）
        assert "error" in result or not result.get("success", True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
