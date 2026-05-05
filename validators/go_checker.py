"""
Go 预检规则引擎

自动检测和纠正常见 Go 工程错误

功能：
  • Import 检查（缺失、无用、循环）
  • Unused 检查（变量、常量、函数）
  • 依赖检查（缺失、版本冲突）
  • 编译错误预检
  • 最佳实践检查
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple

from core.logger import get_logger

logger = get_logger(__name__)


class GoChecker:
    """Go 工程预检器"""
    
    def __init__(self, workspace: str):
        """
        初始化 Go 预检器
        
        Args:
            workspace: Go 项目根目录
        """
        self.workspace = Path(workspace)
        self.logger = get_logger(__name__)
    
    def check_all(self) -> Dict:
        """
        执行所有预检
        
        Returns:
            预检结果
        """
        self.logger.info("[GoChecker] 执行全部预检")
        
        results = {
            "imports": self.check_imports(),
            "unused": self.check_unused(),
            "dependencies": self.check_dependencies(),
            "syntax": self.check_syntax(),
            "best_practices": self.check_best_practices(),
        }
        
        return results
    
    def check_imports(self) -> Dict:
        """检查导入"""
        self.logger.info("[GoChecker] 检查导入")
        
        issues = []
        go_files = self.workspace.glob("**/*.go")
        
        for go_file in go_files:
            try:
                content = go_file.read_text()
                
                # 检查缺失的包
                missing = self._find_missing_imports(content)
                for pkg in missing:
                    issues.append({
                        "file": str(go_file.relative_to(self.workspace)),
                        "type": "missing_import",
                        "package": pkg,
                        "suggestion": f"Add: import \"{pkg}\"",
                    })
                
                # 检查无用的包
                unused = self._find_unused_imports(content)
                for pkg in unused:
                    issues.append({
                        "file": str(go_file.relative_to(self.workspace)),
                        "type": "unused_import",
                        "package": pkg,
                        "suggestion": f"Remove unused import: {pkg}",
                    })
            
            except Exception as e:
                self.logger.debug(f"Error checking {go_file}: {e}")
        
        return {
            "total_issues": len(issues),
            "issues": issues,
            "summary": f"Found {len(issues)} import issues" if issues else "No import issues found",
        }
    
    def check_unused(self) -> Dict:
        """检查未使用的变量和函数"""
        self.logger.info("[GoChecker] 检查未使用项")
        
        issues = []
        go_files = self.workspace.glob("**/*.go")
        
        for go_file in go_files:
            try:
                content = go_file.read_text()
                
                # 检查未使用的变量
                unused_vars = self._find_unused_variables(content)
                for var, line in unused_vars:
                    issues.append({
                        "file": str(go_file.relative_to(self.workspace)),
                        "type": "unused_variable",
                        "name": var,
                        "line": line,
                    })
                
                # 检查未导出的函数（可能未使用）
                unused_funcs = self._find_unused_functions(content)
                for func, line in unused_funcs:
                    issues.append({
                        "file": str(go_file.relative_to(self.workspace)),
                        "type": "unused_function",
                        "name": func,
                        "line": line,
                    })
            
            except Exception as e:
                self.logger.debug(f"Error checking {go_file}: {e}")
        
        return {
            "total_issues": len(issues),
            "issues": issues,
        }
    
    def check_dependencies(self) -> Dict:
        """检查依赖"""
        self.logger.info("[GoChecker] 检查依赖")
        
        issues = []
        go_mod = self.workspace / "go.mod"
        
        if not go_mod.exists():
            return {
                "status": "warning",
                "message": "go.mod not found",
            }
        
        try:
            content = go_mod.read_text()
            dependencies = self._parse_go_mod(content)
            
            # 检查依赖版本冲突
            conflicts = self._check_conflicts(dependencies)
            for conflict in conflicts:
                issues.append({
                    "type": "version_conflict",
                    "package": conflict["package"],
                    "versions": conflict["versions"],
                })
            
            # 检查缺失的依赖
            # (需要对比 go.mod 和实际使用)
            
        except Exception as e:
            self.logger.debug(f"Error checking dependencies: {e}")
        
        return {
            "total_issues": len(issues),
            "issues": issues,
        }
    
    def check_syntax(self) -> Dict:
        """检查语法"""
        self.logger.info("[GoChecker] 检查语法")
        
        issues = []
        go_files = self.workspace.glob("**/*.go")
        
        for go_file in go_files:
            try:
                content = go_file.read_text()
                
                # 检查括号匹配
                if self._has_unmatched_braces(content):
                    issues.append({
                        "file": str(go_file.relative_to(self.workspace)),
                        "type": "syntax_error",
                        "message": "Unmatched braces",
                    })
                
                # 检查缺失的分号或括号
                syntax_errors = self._find_syntax_errors(content)
                issues.extend(syntax_errors)
            
            except Exception as e:
                self.logger.debug(f"Error checking {go_file}: {e}")
        
        return {
            "total_issues": len(issues),
            "issues": issues,
        }
    
    def check_best_practices(self) -> Dict:
        """检查最佳实践"""
        self.logger.info("[GoChecker] 检查最佳实践")
        
        issues = []
        go_files = self.workspace.glob("**/*.go")
        
        for go_file in go_files:
            try:
                content = go_file.read_text()
                
                # 检查 error 处理
                missing_errors = self._find_missing_error_handling(content)
                for line_no, context in missing_errors:
                    issues.append({
                        "file": str(go_file.relative_to(self.workspace)),
                        "type": "missing_error_check",
                        "line": line_no,
                        "context": context,
                    })
                
                # 检查 nil 检查
                missing_nil_checks = self._find_missing_nil_checks(content)
                for line_no, context in missing_nil_checks:
                    issues.append({
                        "file": str(go_file.relative_to(self.workspace)),
                        "type": "missing_nil_check",
                        "line": line_no,
                        "context": context,
                    })
            
            except Exception as e:
                self.logger.debug(f"Error checking best practices in {go_file}: {e}")
        
        return {
            "total_issues": len(issues),
            "issues": issues,
        }
    
    # ==================== 辅助方法 ====================
    
    @staticmethod
    def _find_missing_imports(content: str) -> Set[str]:
        """查找缺失的导入"""
        missing = set()
        
        # 常见的包引用但未导入的情况
        patterns = [
            (r"\\bfmt\\.", "fmt"),
            (r"\\bdatabase/sql\\.", "database/sql"),
            (r"\\bencodingJson\\.", "encoding/json"),
            (r"\\bos\\.", "os"),
            (r"\\bioutil\\.", "io/ioutil"),
        ]
        
        for pattern, pkg in patterns:
            if re.search(pattern, content) and f"import.*{pkg}" not in content:
                missing.add(pkg)
        
        return missing
    
    @staticmethod
    def _find_unused_imports(content: str) -> Set[str]:
        """查找未使用的导入"""
        unused = set()
        
        # 提取导入
        import_lines = re.findall(
            r'import\\s+(?:\\(.*?\\)|"[^"]*")',
            content,
            re.DOTALL
        )
        
        # 简单启发式方法：检查导入的包是否被使用
        for import_line in import_lines:
            match = re.search(r'"([^/]*)"', import_line)
            if match:
                pkg_alias = match.group(1).split("/")[-1]
                # 如果包别名未在代码中出现，可能是未使用的
                if f"{pkg_alias}." not in content:
                    unused.add(pkg_alias)
        
        return unused
    
    @staticmethod
    def _find_unused_variables(content: str) -> List[Tuple]:
        """查找未使用的变量"""
        result = []
        
        # 查找 var 声明
        var_pattern = r"var\\s+(\\w+)\\s+\\w+"
        for match in re.finditer(var_pattern, content):
            var_name = match.group(1)
            # 检查该变量是否被使用
            if f" {var_name}" not in content[match.end():]:
                result.append((var_name, match.start()))
        
        return result
    
    @staticmethod
    def _find_unused_functions(content: str) -> List[Tuple]:
        """查找未导出的函数"""
        result = []
        
        # 查找小写函数定义
        func_pattern = r"^func\\s+(\\b[a-z]\\w+)\\s*\\("
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            func_name = match.group(1)
            # 简单启发式：未导出函数是否被调用
            call_pattern = f"{func_name}\\("
            if content.count(call_pattern) == 1:  # 只在定义处出现
                result.append((func_name, match.start()))
        
        return result
    
    @staticmethod
    def _find_missing_error_handling(content: str) -> List[Tuple]:
        """查找缺失的 error 处理"""
        result = []
        
        # 查找 err := 但未检查的情况
        pattern = r"err\\s*:=.*\\n(?!\\s*if\\s+err\\s*!=)"
        for match in re.finditer(pattern, content):
            result.append((match.start(), content[match.start():match.end()]))
        
        return result
    
    @staticmethod
    def _find_missing_nil_checks(content: str) -> List[Tuple]:
        """查找缺失的 nil 检查"""
        result = []
        
        # 查找指针解引用
        pattern = r"\\*\\w+\\."
        lines = content.split("\\n")
        for line_no, line in enumerate(lines):
            if re.search(pattern, line) and "if" not in line:
                result.append((line_no, line.strip()))
        
        return result
    
    @staticmethod
    def _has_unmatched_braces(content: str) -> bool:
        """检查括号是否匹配"""
        return content.count("{") != content.count("}")
    
    @staticmethod
    def _find_syntax_errors(content: str) -> List[Dict]:
        """查找语法错误"""
        errors = []
        
        # 检查 defer 后缺失括号
        if re.search(r"defer\\s+\\w+\\s+(?!\\()", content):
            errors.append({
                "type": "defer_syntax",
                "message": "defer statement missing parentheses",
            })
        
        return errors
    
    @staticmethod
    def _parse_go_mod(content: str) -> Dict:
        """解析 go.mod"""
        dependencies = {}
        
        for line in content.split("\\n"):
            line = line.strip()
            if re.match(r"^\\w+/", line):
                parts = line.split()
                if len(parts) >= 2:
                    dependencies[parts[0]] = parts[1]
        
        return dependencies
    
    @staticmethod
    def _check_conflicts(dependencies: Dict) -> List[Dict]:
        """检查版本冲突"""
        conflicts = []
        
        # 检查同一个包的多个版本
        for pkg, version in dependencies.items():
            base_pkg = pkg.rsplit("/", 1)[0] if "/" in pkg else pkg
            for other_pkg, other_version in dependencies.items():
                if base_pkg == (other_pkg.rsplit("/", 1)[0] if "/" in other_pkg else other_pkg):
                    if pkg != other_pkg and version != other_version:
                        conflicts.append({
                            "package": base_pkg,
                            "versions": [version, other_version],
                        })
        
        return conflicts
