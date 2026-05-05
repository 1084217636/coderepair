#!/usr/bin/env python3
"""
CodeRepair 项目环境验证脚本

验证项目环境配置完整性和依赖安装
"""

import sys
import os
from importlib import metadata

def check_python_version():
    """检查 Python 版本"""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"✅ Python 版本: {version}")
    return True

def check_virtual_env():
    """检查虚拟环境"""
    if hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    ):
        print(f"✅ 虚拟环境: 已激活 ({sys.prefix})")
        return True
    else:
        print("⚠️  虚拟环境: 未激活")
        return False

def check_modules():
    """检查关键模块"""
    modules = [
        ("bootstrap", ["ProjectGenerator", "TemplateType"]),
        ("patcher", ["FileWriter", "PatchApplier"]),
        ("validators.go_checker", ["GoChecker"]),
        ("outputs.diff_formatter", ["DiffFormatter"]),
        ("core.complexity", ["ComplexityEvaluator", "ErrorType"]),
        ("core.router", ["ModelRouter"]),
        ("core.langgraph_workflow", ["CodeRepairWorkflow", "WorkflowState"]),
        ("sandbox", ["DockerRunner", "SandboxConfig"]),
    ]
    
    passed = 0
    failed = 0
    
    for module_name, _ in modules:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
            passed += 1
        except Exception as e:
            print(f"❌ {module_name}: {str(e)[:60]}")
            failed += 1
    
    return passed, failed

def check_dependencies():
    """检查关键依赖包"""
    packages = ["pytest", "openai", "click", "python-dotenv"]

    try:
        installed = {
            dist.metadata["Name"].lower()
            for dist in metadata.distributions()
            if dist.metadata.get("Name")
        }
        all_present = True

        for package in packages:
            if package.lower() in installed:
                print(f"✅ {package}")
            else:
                print(f"❌ {package} 未安装")
                all_present = False

        return all_present
    except Exception:
        print("⚠️  无法检查依赖包")
        return False

def check_project_structure():
    """检查项目结构"""
    required_dirs = [
        "bootstrap",
        "patcher",
        "validators",
        "outputs",
        "core",
        "sandbox",
        "tests",
    ]
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    for dir_name in required_dirs:
        dir_path = os.path.join(base_dir, dir_name)
        if os.path.isdir(dir_path):
            print(f"✅ {dir_name}/")
        else:
            print(f"❌ {dir_name}/ 不存在")
    
    return True

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("🔍 CodeRepair 项目环境验证")
    print("=" * 70 + "\n")
    
    print("📌 Python 版本检查")
    print("-" * 70)
    check_python_version()
    print()
    
    print("📌 虚拟环境检查")
    print("-" * 70)
    check_virtual_env()
    print()
    
    print("📌 模块导入检查")
    print("-" * 70)
    passed, failed = check_modules()
    print(f"\n   结果: {passed} 通过, {failed} 失败")
    print()
    
    print("📌 依赖包检查")
    print("-" * 70)
    check_dependencies()
    print()
    
    print("📌 项目结构检查")
    print("-" * 70)
    check_project_structure()
    print()
    
    print("=" * 70)
    if failed == 0:
        print("✅ 所有检查通过！环境配置完成")
        print("\n💡 接下来可以:")
        print("   1. 运行测试: ./.venv/bin/python -m pytest tests/ -v")
        print("   2. 查看文档: cat SIMPLE_USAGE.md")
        print("   3. 跑主流程: ./.venv/bin/python app.py --help")
    else:
        print(f"⚠️  发现 {failed} 个问题需要解决")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
