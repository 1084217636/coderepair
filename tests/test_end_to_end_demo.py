"""
端到端演示测试

展示完整的代码修复流程：
  1. 生成项目
  2. 编写有问题的Go代码
  3. 检查代码问题
  4. 修复问题
  5. 验证修复结果
"""

import os
import json
import tempfile
import shutil
from pathlib import Path

import pytest

from bootstrap import ProjectGenerator, TemplateType
from patcher import FileWriter
from validators.go_checker import GoChecker
from outputs.diff_formatter import DiffFormatter
from core.complexity import ComplexityEvaluator, ErrorType, ModelRouter
from core.router import IntelligentLLMRouter


class TestEndToEndDemo:
    """端到端演示测试"""
    
    @pytest.fixture
    def demo_workspace(self):
        """创建演示工作目录"""
        temp_dir = tempfile.mkdtemp(prefix="demo_e2e_")
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_001_bootstrap_create_project(self, demo_workspace):
        """测试1️⃣：使用Bootstrap生成项目"""
        generator = ProjectGenerator(demo_workspace)
        
        result = generator.generate(
            project_name="buggy_service",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/buggy_service",
            description="A demo service with intentional bugs"
        )
        
        # 验证生成
        assert result["success"]
        assert result["status"] == "success"
        assert os.path.exists(result["project_dir"])
        assert "go.mod" in os.listdir(result["project_dir"])
        
        print(f"\n✅ 项目已生成: {result['project_dir']}")
        print(f"   创建文件数: {result['files_created']}")
        print(f"   创建目录数: {result['directories_created']}")
    
    def test_002_write_buggy_code(self, demo_workspace):
        """测试2️⃣：编写有问题的Go代码"""
        # 先生成项目
        generator = ProjectGenerator(demo_workspace)
        gen_result = generator.generate(
            project_name="buggy_service",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/buggy_service"
        )
        
        project_dir = gen_result["project_dir"]
        writer = FileWriter(project_dir)
        
        # 编写有问题的代码：
        # 1. 未使用的导入
        # 2. 逻辑错误
        buggy_code = '''package main

import (
    "fmt"
    "os"
    "unused_package"  // 未使用
)

func main() {
    x := 10
    y := 20
    
    // 逻辑错误：应该是 x+y 而不是 x-y
    result := x - y
    
    fmt.Println("Result:", result)
}
'''
        
        result = writer.write_file("main.go", buggy_code)
        
        # 验证文件写入
        assert result["status"] == "success"
        assert os.path.exists(os.path.join(project_dir, "main.go"))
        
        print("\n✅ 有问题的代码已写入")
        print("   - 包含未使用的导入")
        print("   - 包含逻辑错误")
    
    def test_003_check_code_issues(self, demo_workspace):
        """测试3️⃣：检查代码问题"""
        # 生成项目和写入代码
        generator = ProjectGenerator(demo_workspace)
        gen_result = generator.generate(
            project_name="buggy_service",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/buggy_service"
        )
        
        project_dir = gen_result["project_dir"]
        writer = FileWriter(project_dir)
        
        buggy_code = '''package main

import (
    "fmt"
    "os"
    "bytes"  // 未使用
)

func main() {
    result := 10 - 20
    fmt.Println("Result:", result)
}
'''
        writer.write_file("main.go", buggy_code)
        
        # 检查代码
        checker = GoChecker(project_dir)
        check_result = checker.check_imports()
        
        # 验证检查结果
        assert "issues" in check_result
        assert "summary" in check_result
        
        print("\n✅ 代码检查完成")
        print(f"   总问题数: {check_result['total_issues']}")
        if check_result['total_issues'] > 0:
            for issue in check_result['issues']:
                print(f"   - [{issue['type']}] {issue['file']}: {issue['suggestion']}")
    
    def test_004_complexity_assessment(self, demo_workspace):
        """测试4️⃣：复杂度评估"""
        evaluator = ComplexityEvaluator()
        
        # 评估逻辑错误的复杂度
        logic_error_score = evaluator.evaluate(
            error_type=ErrorType.LOGIC,
            files_affected=["main.go"],
            code_context="Subtraction instead of addition"
        )
        
        # 评估导入错误的复杂度
        import_error_score = evaluator.evaluate(
            error_type=ErrorType.IMPORTS,
            files_affected=["main.go"],
            code_context="Unused import statement"
        )
        
        # 验证评估
        assert logic_error_score is not None
        assert import_error_score is not None
        assert hasattr(logic_error_score, 'score')
        assert hasattr(import_error_score, 'level')
        
        print("\n✅ 复杂度评估完成")
        print(f"   逻辑错误评分: {logic_error_score.score:.1f} ({logic_error_score.level.value})")
        print(f"   导入错误评分: {import_error_score.score:.1f} ({import_error_score.level.value})")
    
    def test_005_router_select_model(self, demo_workspace):
        """测试5️⃣：模型路由选择"""
        router = IntelligentLLMRouter()
        
        # 不同复杂度的问题应该选择不同的模型
        route_config_simple = router.router.route(
            complexity_score=ComplexityEvaluator().evaluate(
                error_type=ErrorType.SYNTAX,
                files_affected=["test.go"],
                code_context="Simple syntax error"
            )
        )
        
        route_config_complex = router.router.route(
            complexity_score=ComplexityEvaluator().evaluate(
                error_type=ErrorType.LOGIC,
                files_affected=["test.go"],
                code_context="Complex logic issue"
            )
        )
        
        # 验证路由
        assert route_config_simple is not None
        assert route_config_complex is not None
        assert "model" in route_config_simple
        assert "selected_provider" in route_config_complex
        
        print("\n✅ 模型路由完成")
        print(f"   低复杂度: {route_config_simple['model']} (成本级别: {route_config_simple['cost_tier']})")
        print(f"   高复杂度: {route_config_complex['model']} (成本级别: {route_config_complex['cost_tier']})")
    
    def test_006_fix_and_generate_diff(self, demo_workspace):
        """测试6️⃣：修复代码并生成Diff"""
        # 生成项目
        generator = ProjectGenerator(demo_workspace)
        gen_result = generator.generate(
            project_name="buggy_service",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/buggy_service"
        )
        
        project_dir = gen_result["project_dir"]
        writer = FileWriter(project_dir)
        
        # 原始有问题的代码
        buggy_code = '''package main

import (
    "fmt"
)

func main() {
    x := 10
    y := 20
    result := x - y  // BUG: 应该是 x + y
    fmt.Println("Result:", result)
}
'''
        
        # 修复后的代码
        fixed_code = '''package main

import (
    "fmt"
)

func main() {
    x := 10
    y := 20
    result := x + y  // FIXED: 改为 x + y
    fmt.Println("Result:", result)
}
'''
        
        # 写入原始代码
        writer.write_file("main.go", buggy_code)
        
        # 生成Diff
        formatter = DiffFormatter(project_dir)
        diff_result = formatter.generate_diff(
            file_path="main.go",
            old_content=buggy_code,
            new_content=fixed_code
        )
        
        # 验证Diff
        assert diff_result is not None
        assert diff_result["file"] == "main.go"
        assert "main.go" in diff_result["diff"]
        
        print("\n✅ Diff已生成")
        print("   修改内容:")
        print("   - 移除: x - y")
        print("   + 添加: x + y")
    
    def test_007_apply_fix_and_verify(self, demo_workspace):
        """测试7️⃣：应用修复并验证"""
        # 生成项目
        generator = ProjectGenerator(demo_workspace)
        gen_result = generator.generate(
            project_name="buggy_service",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/buggy_service"
        )
        
        project_dir = gen_result["project_dir"]
        writer = FileWriter(project_dir)
        
        # 原始代码
        buggy_code = '''package main

func main() {
    result := 10 - 20
}
'''
        
        # 写入原始代码
        writer.write_file("main.go", buggy_code)
        
        # 应用修复（使用update_file的old_content/new_content）
        fix_result = writer.update_file(
            "main.go",
            old_content="result := 10 - 20",
            new_content="result := 10 + 20"
        )
        
        # 验证修复
        assert fix_result["status"] == "success"
        
        # 读取修复后的文件
        fixed_content = Path(project_dir) / "main.go"
        with open(fixed_content, "r") as f:
            content = f.read()
        
        assert "10 + 20" in content
        assert "10 - 20" not in content
        
        print("\n✅ 修复已应用")
        print("   - 修改前: result := 10 - 20")
        print("   + 修改后: result := 10 + 20")
    
    def test_008_full_workflow_simulation(self, demo_workspace):
        """测试8️⃣：完整工作流模拟"""
        print("\n" + "="*70)
        print("完整代码修复流程演示")
        print("="*70)
        
        # 步骤1: 生成项目
        print("\n1️⃣ 生成项目...")
        generator = ProjectGenerator(demo_workspace)
        gen_result = generator.generate(
            project_name="full_demo",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/full"
        )
        assert gen_result["success"]
        print(f"   ✅ 项目已在 {gen_result['project_dir']}")
        
        # 步骤2: 编写有问题的代码
        print("\n2️⃣ 编写有问题的代码...")
        project_dir = gen_result["project_dir"]
        writer = FileWriter(project_dir)
        
        buggy_code = '''package main

import (
    "fmt"
    "unused"
)

// BUG 1: 未使用的导入
// BUG 2: 逻辑错误（应该是乘法而不是除法）
func calculate(a, b int) int {
    return a / b
}

func main() {
    result := calculate(10, 2)
    fmt.Println("Result:", result)
}
'''
        writer.write_file("main.go", buggy_code)
        print("   ✅ 代码已写入（包含2个问题）")
        
        # 步骤3: 检查问题
        print("\n3️⃣ 检查代码问题...")
        checker = GoChecker(project_dir)
        issues = checker.check_imports()
        print(f"   ✅ 发现 {issues['total_issues']} 个问题")
        
        # 步骤4: 评估复杂度
        print("\n4️⃣ 评估修复复杂度...")
        evaluator = ComplexityEvaluator()
        score = evaluator.evaluate(
            error_type=ErrorType.LOGIC,
            files_affected=["main.go"],
            code_context="Division instead of multiplication"
        )
        print(f"   ✅ 复杂度评分: {score.score:.1f}/{10} ({score.level.value})")
        
        # 步骤5: 选择模型
        print("\n5️⃣ 选择修复模型...")
        router = IntelligentLLMRouter()
        model_choice = router.router.route(complexity_score=score)
        print(f"   ✅ 选择模型: {model_choice['model']}")
        print(f"   💰 成本级别: {model_choice['cost_tier']}")
        estimated = model_choice.get('estimated_cost')
        if isinstance(estimated, dict):
            print(f"   📊 预计费用: ${estimated.get('estimated_total_usd', 0):.6f}")
        else:
            print(f"   📊 预计费用: $0.00")
        
        # 步骤6: 应用修复
        print("\n6️⃣ 应用修复...")
        fixed_code = '''package main

import (
    "fmt"
)

// FIXED: 移除未使用导入，改为乘法
func calculate(a, b int) int {
    return a * b
}

func main() {
    result := calculate(10, 2)
    fmt.Println("Result:", result)
}
'''
        
        writer.update_file(
            "main.go",
            old_content=buggy_code,
            new_content=fixed_code
        )
        print("   ✅ 修复已应用")
        
        # 步骤7: 生成差异
        print("\n7️⃣ 生成修改报告...")
        formatter = DiffFormatter(project_dir)
        diff = formatter.generate_diff(
            file_path="main.go",
            old_content=buggy_code,
            new_content=fixed_code
        )
        print("   ✅ 差异已生成")
        
        # 步骤8: 验证结果
        print("\n8️⃣ 验证修复结果...")
        operations_log = writer.get_operations_log()
        print(f"   ✅ 执行了 {len(operations_log)} 个操作")
        print(f"   ✅ 创建了 {len([op for op in operations_log if op['type'] == 'write_file'])} 个备份")
        
        print("\n" + "="*70)
        print("✅ 完整工作流演示成功！")
        print("="*70)


class TestRealWorldScenarios:
    """真实场景测试"""
    
    @pytest.fixture
    def real_workspace(self):
        """创建真实工作目录"""
        temp_dir = tempfile.mkdtemp(prefix="real_scenario_")
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_nil_pointer_dereference_fix(self, real_workspace):
        """测试场景：修复空指针解引用"""
        # 生成项目
        generator = ProjectGenerator(real_workspace)
        gen_result = generator.generate(
            project_name="nil_fix",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/nil_fix"
        )
        
        project_dir = gen_result["project_dir"]
        writer = FileWriter(project_dir)
        
        # 有空指针问题的代码
        buggy = '''package main

import "fmt"

type User struct {
    Name string
    Age  int
}

func printUser(u *User) {
    // BUG: 没有检查 u 是否为 nil
    fmt.Println(u.Name)
}

func main() {
    var user *User
    printUser(user)
}
'''
        
        # 修复后的代码
        fixed = '''package main

import "fmt"

type User struct {
    Name string
    Age  int
}

func printUser(u *User) {
    // FIXED: 添加 nil 检查
    if u == nil {
        fmt.Println("User is nil")
        return
    }
    fmt.Println(u.Name)
}

func main() {
    var user *User
    printUser(user)
}
'''
        
        writer.write_file("main.go", buggy)
        
        # 应用修复
        writer.update_file(
            "main.go",
            old_content="fmt.Println(u.Name)",
            new_content='if u == nil {\n        fmt.Println("User is nil")\n        return\n    }\n    fmt.Println(u.Name)'
        )
        
        # 验证
        with open(os.path.join(project_dir, "main.go"), "r") as f:
            content = f.read()
        
        assert "nil" in content
        assert "User is nil" in content
        print("\n✅ 空指针解引用修复完成")
    
    def test_race_condition_analysis(self, real_workspace):
        """测试场景：竞态条件分析"""
        generator = ProjectGenerator(real_workspace)
        gen_result = generator.generate(
            project_name="race_condition",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/race"
        )
        
        # 模拟竞态条件代码
        racey_code = '''package main

var counter int  // BUG: 多线程未保护

func increment() {
    counter++  // 竞态条件
}

func main() {
    go increment()
    go increment()
}
'''
        
        project_dir = gen_result["project_dir"]
        writer = FileWriter(project_dir)
        writer.write_file("race.go", racey_code)
        
        # 评估复杂度
        evaluator = ComplexityEvaluator()
        score = evaluator.evaluate(
            error_type=ErrorType.CONCURRENCY,
            files_affected=["race.go"],
            code_context="Race condition in global counter"
        )
        
        assert score is not None
        assert score.level.value != "trivial"
        print(f"\n✅ 竞态条件复杂度评分: {score.score:.1f}/{10}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
