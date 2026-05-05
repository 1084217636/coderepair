"""
Go AST 分析模块 - 提取包、导入、函数等结构信息
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GoPackageInfo:
    """Go 包信息"""
    name: str
    imports: List[str]
    functions: List[str]
    types: List[str]


class GoAnalyzer:
    """
    Go 代码分析器
    
    职责：
    1. 解析包名和导入
    2. 提取函数签名
    3. 提取类型定义
    4. 生成文件摘要
    """
    
    def __init__(self, workspace_root: Optional[Path] = None):
        self.logger = get_logger(__name__)
        self.workspace_root = workspace_root.resolve() if workspace_root else None
        self.module_name = self._load_module_name(self.workspace_root) if self.workspace_root else None
    
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """
        分析单个 Go 文件
        
        Args:
            file_path: .go 文件路径
        
        Returns:
            包含包名、导入、函数等信息的字典
        """
        self.logger.debug(f"[GoAnalyzer] 分析文件 | file={file_path.name}")
        
        try:
            content = file_path.read_text(encoding="utf-8")
            
            package_name = self._extract_package(content)
            imports = self._extract_imports(content)
            functions = self._extract_functions(content)
            methods = self._extract_methods(content)
            types_list = self._extract_types(content)
            call_edges = self._extract_call_edges(content)
            dependency_span = self._analyze_dependency_span(imports)
            
            return {
                "file_path": str(file_path),
                "package": package_name,
                "imports": imports,
                "functions": functions,
                "methods": methods,
                "types": types_list,
                "call_edges": call_edges,
                "dependency_span": dependency_span,
                "lines": len(content.split("\n")),
            }
        except Exception as e:
            self.logger.error(f"[GoAnalyzer] 分析失败 | file={file_path} | error={e}")
            return {}
    
    def analyze_package(self, package_dir: Path) -> Dict[str, Any]:
        """
        分析整个 Go 包（目录）
        
        Args:
            package_dir: 包目录路径
        
        Returns:
            包的汇总信息
        """
        self.logger.debug(f"[GoAnalyzer] 分析包 | package={package_dir.name}")
        
        all_functions = []
        all_methods = []
        all_types = []
        all_imports = set()
        all_call_edges = []
        package_name = None
        
        for go_file in package_dir.glob("*.go"):
            analysis = self.analyze_file(go_file)
            
            if analysis:
                if not package_name:
                    package_name = analysis.get("package")
                
                all_functions.extend(analysis.get("functions", []))
                all_methods.extend(analysis.get("methods", []))
                all_types.extend(analysis.get("types", []))
                all_imports.update(analysis.get("imports", []))
                all_call_edges.extend(analysis.get("call_edges", []))
        
        return {
            "package": package_name or package_dir.name,
            "functions": list(set(all_functions)),  # 去重
            "methods": list(set(all_methods)),
            "types": list(set(all_types)),
            "imports": sorted(list(all_imports)),
            "call_edges": all_call_edges,
            "files": len(list(package_dir.glob("*.go"))),
        }
    
    @staticmethod
    def _extract_package(content: str) -> str:
        """
        提取包名
        
        Args:
            content: 文件内容
        
        Returns:
            包名
        """
        match = re.search(r"^package\s+(\w+)", content, re.MULTILINE)
        return match.group(1) if match else "main"
    
    @staticmethod
    def _extract_imports(content: str) -> List[str]:
        """
        提取导入列表
        
        Args:
            content: 文件内容
        
        Returns:
            导入路径列表
        """
        imports = []
        
        # 单行导入
        single_imports = re.findall(r'import\s+"([^"]+)"', content)
        imports.extend(single_imports)
        
        # 多行导入块
        import_block = re.search(r"import\s*\((.*?)\)", content, re.DOTALL)
        if import_block:
            lines = import_block.group(1).split("\n")
            for line in lines:
                # 提取引号内的内容
                match = re.search(r'"([^"]+)"', line)
                if match:
                    imports.append(match.group(1))
        
        return sorted(list(set(imports)))
    
    @staticmethod
    def _extract_functions(content: str) -> List[str]:
        """
        提取函数名
        
        Args:
            content: 文件内容
        
        Returns:
            函数名列表
        """
        # 匹配 func 定义（不包括方法）
        functions = re.findall(r"^func\s+(\w+)\s*\(", content, re.MULTILINE)
        return sorted(list(set(functions)))

    @staticmethod
    def _extract_methods(content: str) -> List[str]:
        methods = []
        pattern = r"^func\s*\(([^)]*)\)\s*(\w+)\s*\("
        for receiver, name in re.findall(pattern, content, re.MULTILINE):
            receiver_type = GoAnalyzer._normalize_receiver(receiver)
            methods.append(f"{receiver_type}.{name}" if receiver_type else name)
        return sorted(list(set(methods)))
    
    @staticmethod
    def _extract_types(content: str) -> List[str]:
        """
        提取类型定义
        
        Args:
            content: 文件内容
        
        Returns:
            类型名列表
        """
        types_list = []
        
        # 匹配 type 定义
        type_defs = re.findall(r"^type\s+(\w+)\s+(?:struct|interface|func)", content, re.MULTILINE)
        types_list.extend(type_defs)
        
        # 匹配 const/var 块中的类型
        const_patterns = re.findall(r"^const\s+(\w+)\s*=", content, re.MULTILINE)
        types_list.extend(const_patterns)
        
        return sorted(list(set(types_list)))

    @staticmethod
    def _normalize_receiver(receiver: str) -> str:
        match = re.search(r"\*?(\w+)\s*$", receiver.strip())
        return match.group(1) if match else ""

    def _extract_call_edges(self, content: str) -> List[Dict[str, Any]]:
        edges = []
        current_callable = None
        brace_depth = 0
        func_started = False
        call_keywords = {"if", "for", "switch", "return", "func", "go", "defer", "select", "make", "new"}
        func_pattern = re.compile(r"^func\s*(?:\(([^)]*)\)\s*)?(\w+)\s*\(", re.MULTILINE)
        method_call_pattern = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*\(")
        func_call_pattern = re.compile(r"\b([A-Za-z_]\w*)\s*\(")

        for line_no, raw_line in enumerate(content.splitlines(), 1):
            line = raw_line.strip()
            func_match = func_pattern.match(line)
            if func_match:
                receiver, name = func_match.groups()
                receiver_type = self._normalize_receiver(receiver or "")
                current_callable = f"{receiver_type}.{name}" if receiver_type else name
                brace_depth = raw_line.count("{") - raw_line.count("}")
                func_started = True
                continue

            if not func_started or not current_callable:
                continue

            for qualifier, callee in method_call_pattern.findall(raw_line):
                edges.append(
                    {
                        "caller": current_callable,
                        "callee": f"{qualifier}.{callee}",
                        "line": line_no,
                        "kind": "method_call",
                    }
                )

            for callee in func_call_pattern.findall(raw_line):
                if callee in call_keywords:
                    continue
                if any(item["line"] == line_no and item["callee"].endswith(f".{callee}") for item in edges):
                    continue
                edges.append(
                    {
                        "caller": current_callable,
                        "callee": callee,
                        "line": line_no,
                        "kind": "function_call",
                    }
                )

            brace_depth += raw_line.count("{") - raw_line.count("}")
            if brace_depth <= 0:
                current_callable = None
                func_started = False

        deduped = []
        seen: set[Tuple[str, str, int]] = set()
        for edge in edges:
            key = (edge["caller"], edge["callee"], edge["line"])
            if key not in seen:
                seen.add(key)
                deduped.append(edge)
        return deduped

    def _analyze_dependency_span(self, imports: List[str]) -> Dict[str, Any]:
        stdlib_imports = []
        local_imports = []
        external_imports = []

        for import_path in imports:
            if self.module_name and import_path.startswith(self.module_name):
                local_imports.append(import_path)
            elif "." in import_path.split("/")[0]:
                external_imports.append(import_path)
            else:
                stdlib_imports.append(import_path)

        import_depths = [len(path.split("/")) for path in imports] or [0]

        return {
            "stdlib_imports": len(stdlib_imports),
            "local_imports": len(local_imports),
            "external_imports": len(external_imports),
            "max_import_depth": max(import_depths),
            "cross_package_dependencies": len(local_imports) + len(external_imports),
        }

    @staticmethod
    def _load_module_name(workspace_root: Optional[Path]) -> Optional[str]:
        if not workspace_root:
            return None
        go_mod = workspace_root / "go.mod"
        if not go_mod.exists():
            return None
        try:
            content = go_mod.read_text(encoding="utf-8")
        except Exception:
            return None
        match = re.search(r"^\s*module\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else None
