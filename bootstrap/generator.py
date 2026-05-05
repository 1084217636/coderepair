"""
项目生成器

将模板转化为实际的项目文件和目录
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from core.logger import get_logger
from bootstrap.templates import TemplateType, get_template, ProjectTemplate

logger = get_logger(__name__)


class ProjectGenerator:
    """Go 项目生成器"""
    
    def __init__(self, workspace: str):
        """
        初始化生成器
        
        Args:
            workspace: 项目根目录
        """
        self.workspace = Path(workspace)
        self.logger = get_logger(__name__)
    
    def generate(
        self,
        project_name: str,
        template_type: TemplateType,
        module_path: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        生成项目
        
        Args:
            project_name: 项目名称
            template_type: 模板类型
            module_path: Go 模块路径 (例如: github.com/user/project)
            description: 项目描述
        
        Returns:
            包含生成结果的字典
        """
        self.logger.info(
            f"[Bootstrap] 生成项目 | "
            f"名称={project_name} | "
            f"模板={template_type.value}"
        )
        
        # 验证输入
        if not project_name:
            return {
                "status": "error",
                "error": "Project name cannot be empty",
                "success": False,
            }
        
        # 验证模块路径格式
        if module_path and not self._is_valid_module_path(module_path):
            return {
                "status": "error",
                "error": f"Invalid module path: {module_path}",
                "success": False,
            }
        
        if module_path is None:
            module_path = project_name
        
        # 获取模板
        template = get_template(template_type)
        
        # 准备目录
        project_dir = self.workspace / project_name
        if project_dir.exists():
            self.logger.warning(f"Project directory exists: {project_dir}")
            return {
                "status": "error",
                "error": f"Project directory already exists: {project_dir}",
                "success": False,
            }
        
        try:
            # 1. 创建目录结构
            self._create_directories(project_dir, template)
            
            # 2. 生成文件
            self._generate_files(
                project_dir,
                template,
                module_path,
                project_name,
            )
            
            # 3. 生成 go.mod
            self._generate_go_mod(project_dir, module_path, template)
            
            # 4. 生成元数据
            metadata = self._generate_metadata(
                project_dir,
                project_name,
                template_type,
                module_path,
                description,
            )
            
            self.logger.info(f"[Bootstrap] 项目生成完成 | 路径={project_dir}")
            
            return {
                "status": "success",
                "success": True,
                "project_dir": str(project_dir),
                "project_name": project_name,
                "module_path": module_path,
                "template": template_type.value,
                "files_created": len(template.files),
                "directories_created": len(template.directories),
                "metadata_file": str(project_dir / ".bootstrap.json"),
            }
        
        except Exception as e:
            self.logger.error(f"[Bootstrap] 生成失败: {e}")
            raise
    
    def _is_valid_module_path(self, module_path: str) -> bool:
        """验证模块路径格式"""
        import re
        # Go module路径格式: example.com/module 或 github.com/user/repo
        # 可以包含字母、数字、点、破折号和下划线
        pattern = r'^[a-zA-Z0-9\.\-_/]+$'
        if not re.match(pattern, module_path):
            return False
        # 不能以点或斜杠开头或结尾
        if module_path.startswith('.') or module_path.startswith('/'):
            return False
        if module_path.endswith('.') or module_path.endswith('/'):
            return False
        return True
    
    def _create_directories(self, project_dir: Path, template: ProjectTemplate) -> None:
        """创建目录结构"""
        self.logger.debug(f"[Bootstrap] 创建目录结构")
        
        for dir_name in template.directories:
            dir_path = project_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"  Created: {dir_path}")
        
        # 创建日志目录
        logs_dir = project_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_files(
        self,
        project_dir: Path,
        template: ProjectTemplate,
        module_path: str,
        project_name: str,
    ) -> None:
        """生成文件"""
        self.logger.debug(f"[Bootstrap] 生成文件")
        
        package_name = project_name.replace("-", "_")
        
        for file_path, content in template.files.items():
            # 替换占位符
            content = content.replace("{module_path}", module_path)
            content = content.replace("{project_name}", project_name)
            content = content.replace("{package_name}", package_name)
            
            full_path = project_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, "w") as f:
                f.write(content)
            
            self.logger.debug(f"  Created: {full_path}")
    
    def _generate_go_mod(self, project_dir: Path, module_path: str, template: ProjectTemplate = None) -> None:
        """生成 go.mod 文件"""
        self.logger.debug(f"[Bootstrap] 生成 go.mod")
        
        go_mod_path = project_dir / "go.mod"
        content = f"module {module_path}\n\ngo 1.21"
        
        # 添加依赖
        if template and template.dependencies:
            content += "\n\nrequire ("
            for dep in template.dependencies:
                if dep.version:
                    content += f"\n\t{dep.name} {dep.version}"
                else:
                    content += f"\n\t{dep.name} latest"
            content += "\n)"
        
        with open(go_mod_path, "w") as f:
            f.write(content)
        
        self.logger.debug(f"  Created: {go_mod_path}")
    
    def _generate_metadata(
        self,
        project_dir: Path,
        project_name: str,
        template_type: TemplateType,
        module_path: str,
        description: Optional[str],
    ) -> Dict:
        """生成项目元数据"""
        self.logger.debug(f"[Bootstrap] 生成元数据")
        
        metadata = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "created_by": "CodeRepair Bootstrap",
            "project_name": project_name,
            "module_path": module_path,
            "template": template_type.value,
            "description": description or "",
            "structure": {
                "go_version": "1.21",
                "has_makefile": True,
                "has_gitignore": True,
                "has_logs_dir": True,
            },
        }
        
        metadata_file = project_dir / ".bootstrap.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.debug(f"  Created: {metadata_file}")
        
        return metadata
    
    def bootstrap_from_requirement(
        self,
        requirement: str,
        template_type: Optional[TemplateType] = None,
    ) -> Dict:
        """
        从需求描述生成项目
        
        这个方法允许 LLM 根据需求自动确定项目类型
        
        Args:
            requirement: 需求描述 (例如: "创建一个 RESTful API 服务")
            template_type: 可选的模板类型，如果未指定会自动推断
        
        Returns:
            生成结果
        """
        self.logger.info(f"[Bootstrap] 从需求生成项目 | 需求={requirement}")
        
        # 如果没有指定模板，尝试推断
        if template_type is None:
            template_type = self._infer_template_type(requirement)
        
        # 从需求提取项目名
        project_name = self._extract_project_name(requirement)
        
        # 生成项目
        return self.generate(
            project_name=project_name,
            template_type=template_type,
            description=requirement,
        )
    
    @staticmethod
    def _infer_template_type(requirement: str) -> TemplateType:
        """从需求描述推断模板类型"""
        requirement_lower = requirement.lower()
        
        if "web" in requirement_lower or "api" in requirement_lower or "rest" in requirement_lower:
            return TemplateType.WEB
        elif "cli" in requirement_lower or "command" in requirement_lower or "tool" in requirement_lower:
            return TemplateType.CLI
        elif "grpc" in requirement_lower:
            return TemplateType.GRPC
        elif "library" in requirement_lower or "package" in requirement_lower:
            return TemplateType.LIBRARY
        else:
            return TemplateType.WEB  # 默认
    
    @staticmethod
    def _extract_project_name(requirement: str) -> str:
        """从需求描述提取项目名"""
        # 简单的启发式方法
        words = requirement.split()
        if len(words) > 0:
            # 取第一个单词作为项目名，转换为小写
            name = words[0].lower().replace("-", "_").replace(" ", "_")
            return name
        return "my_project"


# 便捷函数
def bootstrap_simple(
    workspace: str,
    project_name: str,
    template_type: TemplateType = TemplateType.WEB,
    module_path: Optional[str] = None,
) -> Dict:
    """
    简单的项目生成
    
    Args:
        workspace: 项目根目录
        project_name: 项目名称
        template_type: 模板类型 (默认 Web)
        module_path: Go 模块路径
    
    Returns:
        生成结果
    """
    generator = ProjectGenerator(workspace)
    return generator.generate(
        project_name=project_name,
        template_type=template_type,
        module_path=module_path,
    )
