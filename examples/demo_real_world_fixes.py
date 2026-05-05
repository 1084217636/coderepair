#!/usr/bin/env python3
"""
真实Go修复案例演示

展示CodeRepair系统修复实际Go代码问题的完整流程
"""

import os
import tempfile
import shutil
from pathlib import Path

from bootstrap import ProjectGenerator, TemplateType
from patcher import FileWriter
from validators.go_checker import GoChecker
from outputs.diff_formatter import DiffFormatter
from core.complexity import ComplexityEvaluator, ErrorType


# =================================================================
# 案例1：修复空指针解引用
# =================================================================

def case_1_nil_pointer_fix():
    """
    案例1：修复空指针解引用
    
    问题：函数没有检查指针是否为nil
    修复：添加nil检查
    复杂度：简单（修复只需要添加条件检查）
    """
    print("\n" + "="*70)
    print("案例1️⃣：修复空指针解引用 (Nil Pointer Dereference)")
    print("="*70)
    
    # 创建临时工作目录
    workspace = tempfile.mkdtemp(prefix="case1_")
    
    try:
        # 步骤1: 生成项目
        print("\n[步骤1] 生成项目...")
        generator = ProjectGenerator(workspace)
        gen_result = generator.generate(
            project_name="user_service",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/user_service"
        )
        assert gen_result["success"], f"项目生成失败: {gen_result.get('error', 'Unknown error')}"
        project_dir = gen_result["project_dir"]
        print(f"✅ 项目已生成: {project_dir}")
        
        # 步骤2: 编写有空指针问题的代码
        print("\n[步骤2] 编写有空指针问题的代码...")
        writer = FileWriter(project_dir)
        
        buggy_code = '''package main

import "fmt"

type User struct {
    ID   int
    Name string
    Email string
}

// GetUserEmail 获取用户邮箱 - BUG: 没有检查user是否为nil
func GetUserEmail(user *User) string {
    return user.Email  // 可能导致panic
}

// PrintUser 打印用户信息 - BUG: 没有检查user是否为nil
func PrintUser(user *User) {
    fmt.Printf("User: %s (%d)\\n", user.Name, user.ID)
}

func main() {
    var user *User
    
    // 这些调用会导致panic: runtime error
    email := GetUserEmail(user)
    fmt.Println(email)
    
    PrintUser(user)
}
'''
        
        writer.write_file("main.go", buggy_code)
        print("✅ 包含2个空指针问题的代码已写入")
        
        # 步骤3: 分析问题
        print("\n[步骤3] 分析代码...")
        evaluator = ComplexityEvaluator()
        score = evaluator.evaluate(
            error_type=ErrorType.RUNTIME,
            files_affected=["main.go"],
            code_context="Potential nil pointer dereference"
        )
        print(f"✅ 复杂度评分: {score.score:.1f}/10 ({score.level.value})")
        
        # 步骤4: 生成修复建议
        print("\n[步骤5] 修复方案...")
        fixed_code = '''package main

import "fmt"

type User struct {
    ID   int
    Name string
    Email string
}

// GetUserEmail 获取用户邮箱 - FIXED: 添加nil检查
func GetUserEmail(user *User) string {
    if user == nil {
        return ""  // 返回空字符串而不是panic
    }
    return user.Email
}

// PrintUser 打印用户信息 - FIXED: 添加nil检查
func PrintUser(user *User) {
    if user == nil {
        fmt.Println("User is nil")
        return
    }
    fmt.Printf("User: %s (%d)\\n", user.Name, user.ID)
}

func main() {
    var user *User
    
    // 现在这些调用是安全的
    email := GetUserEmail(user)
    fmt.Println("Email:", email)
    
    PrintUser(user)
}
'''
        
        # 步骤5: 应用修复
        print("\n[步骤4] 应用修复...")
        writer.update_file("main.go", old_content=buggy_code, new_content=fixed_code)
        print("✅ 修复已应用")
        
        # 步骤6: 生成Diff
        print("\n[步骤5] 生成修改对比...")
        formatter = DiffFormatter(project_dir)
        diff = formatter.generate_diff(
            file_path="main.go",
            old_content=buggy_code,
            new_content=fixed_code
        )
        
        print(f"✅ Diff生成成功")
        print(f"  - 修改行数: +{diff['stats']['additions']} -{diff['stats']['deletions']}")
        print(f"  - 修改文件: {diff['stats']['total_changes']} 处")
        
        print("\n📝 修复详情:")
        print("  1. GetUserEmail函数: 添加nil指针检查与返回空字符串")
        print("  2. PrintUser函数: 添加nil指针检查与提示消息")
        print("\n✅ 案例1完成！")
        
    finally:
        shutil.rmtree(workspace)


# =================================================================
# 案例2：修复未使用变量
# =================================================================

def case_2_unused_variables():
    """
    案例2：修复未使用的变量和导入
    
    问题：代码中有未使用的变量和导入
    修复：移除未使用的声明
    复杂度：简单（只需删除代码）
    """
    print("\n" + "="*70)
    print("案例2️⃣: 修复未使用的变量和导入（Dead Code Elimination）")
    print("="*70)
    
    workspace = tempfile.mkdtemp(prefix="case2_")
    
    try:
        generator = ProjectGenerator(workspace)
        gen_result = generator.generate(
            project_name="math_lib",
            template_type=TemplateType.LIBRARY,
            module_path="github.com/demo/math_lib"
        )
        assert gen_result["success"]
        project_dir = gen_result["project_dir"]
        print(f"\n✅ 项目已生成")
        
        writer = FileWriter(project_dir)
        
        buggy_code = '''package math_lib

import (
    "fmt"
    "math"
    "strings"  // BUG: 未使用
    "errors"   // BUG: 未使用
)

func Add(a, b int) int {
    unused := 42  // BUG: 未使用的变量
    return a + b
}

func Multiply(a, b int) int {
    result := a * b
    temp := 0  // BUG: 未使用的变量
    return result
}

func Sqrt(x float64) float64 {
    if x < 0 {
        fmt.Println("negative number")  // BUG: fmt未使用本应这样
    }
    return math.Sqrt(x)
}
'''
        
        writer.write_file("math_lib.go", buggy_code)
        print("✅ 包含未使用变量的代码已写入")
        
        # 检查问题
        checker = GoChecker(project_dir)
        result = checker.check_imports()
        print(f"\n✅ 问题检查完成: {result['total_issues']} 个问题")
        
        # 修复后的代码
        fixed_code = '''package math_lib

import (
    "fmt"
    "math"
)

func Add(a, b int) int {
    return a + b
}

func Multiply(a, b int) int {
    result := a * b
    return result
}

func Sqrt(x float64) float64 {
    if x < 0 {
        fmt.Println("negative number")
    }
    return math.Sqrt(x)
}
'''
        
        print("\n[修复] 移除未使用的...")
        writer.update_file("math_lib.go", old_content=buggy_code, new_content=fixed_code)
        print("✅ 修复已应用")
        print("  - 移除导入: strings, errors")
        print("  - 移除变量: unused, temp")
        print("\n✅ 案例2完成！")
        
    finally:
        shutil.rmtree(workspace)


# =================================================================
# 案例3：修复逻辑错误
# =================================================================

def case_3_logic_error_fix():
    """
    案例3：修复逻辑错误
    
    问题：计算逻辑错误（用减法代替乘法）
    修复：更正逻辑操作符
    复杂度：中等（需要理解业务逻辑）
    """
    print("\n" + "="*70)
    print("案例3️⃣: 修复逻辑错误（Logic Error）")
    print("="*70)
    
    workspace = tempfile.mkdtemp(prefix="case3_")
    
    try:
        generator = ProjectGenerator(workspace)
        gen_result = generator.generate(
            project_name="calc_service",
            template_type=TemplateType.WEB,
            module_path="github.com/demo/calc"
        )
        assert gen_result["success"]
        project_dir = gen_result["project_dir"]
        print(f"\n✅ 项目已生成")
        
        writer = FileWriter(project_dir)
        
        buggy_code = '''package main

import "fmt"

// 计算商品总价 - BUG: 使用了减法而不是乘法
func CalculateTotal(price, quantity int) int {
    return price - quantity  // 应该是乘法
}

// 计算折扣后价格 - BUG: 折扣计算错误
func CalculateDiscount(price int, discountPercent float64) float64 {
    return float64(price) + (float64(price) * discountPercent / 100)  // 应该是减法
}

// 计算税费 - 正确
func CalculateTax(price float64, taxRate float64) float64 {
    return price * (1 + taxRate/100)
}

func main() {
    price := 100
    quantity := 5
    
    total := CalculateTotal(price, quantity)
    fmt.Printf("Total for %d items at $%d each: $%d\\n", quantity, price, total)
    
    withDiscount := CalculateDiscount(price, 10)
    fmt.Printf("Price with 10%% discount: $%.2f\\n", withDiscount)
    
    withTax := CalculateTax(withDiscount, 8)
    fmt.Printf("Final price with 8%% tax: $%.2f\\n", withTax)
}
'''
        
        writer.write_file("main.go", buggy_code)
        print("✅ 包含逻辑错误的代码已写入")
        
        # 分析
        evaluator = ComplexityEvaluator()
        score = evaluator.evaluate(
            error_type=ErrorType.LOGIC,
            files_affected=["main.go"],
            code_context="Incorrect calculation logic (subtraction instead of multiplication)"
        )
        print(f"\n✅ 复杂度评分: {score.score:.1f}/10 ({score.level.value})")
        
        # 修复
        fixed_code = '''package main

import "fmt"

// 计算商品总价 - FIXED: 改为乘法
func CalculateTotal(price, quantity int) int {
    return price * quantity
}

// 计算折扣后价格 - FIXED: 改为减法计算折扣
func CalculateDiscount(price int, discountPercent float64) float64 {
    return float64(price) - (float64(price) * discountPercent / 100)
}

// 计算税费 - 正确
func CalculateTax(price float64, taxRate float64) float64 {
    return price * (1 + taxRate/100)
}

func main() {
    price := 100
    quantity := 5
    
    total := CalculateTotal(price, quantity)
    fmt.Printf("Total for %d items at $%d each: $%d\\n", quantity, price, total)
    
    withDiscount := CalculateDiscount(price, 10)
    fmt.Printf("Price with 10%% discount: $%.2f\\n", withDiscount)
    
    withTax := CalculateTax(withDiscount, 8)
    fmt.Printf("Final price with 8%% tax: $%.2f\\n", withTax)
}
'''
        
        print("\n[修复] 更正逻辑错误...")
        writer.update_file("main.go", old_content=buggy_code, new_content=fixed_code)
        print("✅ 修复已应用")
        print("  - CalculateTotal: 减法→乘法")
        print("  - CalculateDiscount: 加法→减法（正确的折扣计算）")
        print("\n✅ 案例3完成！")
        
    finally:
        shutil.rmtree(workspace)


# =================================================================
# 主程序
# =================================================================

def main():
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  CodeRepair - 真实Go代码修复案例演示".center(68) + "║")
    print("║" + "  Demonstrating Real-World Go Code Repair".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    try:
        case_1_nil_pointer_fix()
        case_2_unused_variables()
        case_3_logic_error_fix()
        
        print("\n" + "="*70)
        print("✅ 所有案例演示完成！")
        print("="*70)
        print("\n📊 演示总结:")
        print("  • 案例1（空指针）: 已演示如何修复运行时错误")
        print("  • 案例2（未使用）: 已演示如何消除死代码")
        print("  • 案例3（逻辑错误）: 已演示如何修复业务逻辑错误")
        print("\n🎯 关键功能展示:")
        print("  ✅ 项目生成和代码编写")
        print("  ✅ 问题检查和复杂度评估")
        print("  ✅ 代码修复和Diff生成")
        print("\n想要进一步了解，请查看:")
        print("  • README.md - 项目说明")
        print("  • SIMPLE_USAGE.md - 快速开始")
        print("  • tests/test_integration.py - 集成测试")
        print()
        
    except Exception as e:
        print(f"\n❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
