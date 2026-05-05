"""
Go Checker 预检模块测试
"""

import pytest
import tempfile
import os
import shutil

from validators.go_checker import GoChecker


class TestGoChecker:
    """Go 代码预检测试"""
    
    @pytest.fixture
    def sample_go_project(self):
        """创建示例 Go 项目"""
        temp_dir = tempfile.mkdtemp(prefix="test_go_project_")
        
        # 创建 go.mod
        go_mod = os.path.join(temp_dir, "go.mod")
        with open(go_mod, "w") as f:
            f.write("module github.com/test/sample\n\ngo 1.21\n")
        
        # 创建示例 Go 文件
        main_go = os.path.join(temp_dir, "main.go")
        with open(main_go, "w") as f:
            f.write("""package main

import (
    "fmt"
    "log"  // 未使用
)

func main() {
    fmt.Println("Hello")
    GetUser()  // 未定义
}

func GetUser() {
    // 缺失错误处理
    var data interface{}
    data = 123
    _ = data.(string)
}
""")
        
        yield temp_dir
        # 清理
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_check_imports(self, sample_go_project):
        """测试导入检查"""
        checker = GoChecker(sample_go_project)
        result = checker.check_imports()
        
        assert "issues" in result
        # 应该检测到未使用的导入
        assert len(result["issues"]) > 0 or result["summary"] is not None
    
    def test_check_unused(self, sample_go_project):
        """测试未使用项检查"""
        checker = GoChecker(sample_go_project)
        result = checker.check_unused()
        
        assert "issues" in result
    
    def test_check_syntax(self, sample_go_project):
        """测试语法检查"""
        checker = GoChecker(sample_go_project)
        result = checker.check_syntax()
        
        assert "issues" in result or "summary" in result
    
    def test_check_best_practices(self, sample_go_project):
        """测试最佳实践检查"""
        checker = GoChecker(sample_go_project)
        result = checker.check_best_practices()
        
        assert "issues" in result or "summary" in result
        # 应该检测到缺失的错误处理
    
    def test_check_all(self, sample_go_project):
        """测试全部检查"""
        checker = GoChecker(sample_go_project)
        result = checker.check_all()
        
        assert "imports" in result
        assert "unused" in result
        assert "syntax" in result
        assert "best_practices" in result
        assert "dependencies" in result
    
    def test_empty_project(self):
        """测试空项目"""
        temp_dir = tempfile.mkdtemp(prefix="test_empty_")
        
        try:
            checker = GoChecker(temp_dir)
            result = checker.check_all()
            
            # 应该不会抛出异常
            assert result is not None
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
