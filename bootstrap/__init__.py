"""
Bootstrap 模块 - 从零生成 Go 项目

功能：
  • 支持多种项目模板（Web、CLI、Library）
  • 自动生成项目骨架和初始文件
  • 支持自定义配置和依赖
"""

from bootstrap.generator import ProjectGenerator
from bootstrap.templates import ProjectTemplate, TemplateType

__all__ = [
    "ProjectGenerator",
    "ProjectTemplate",
    "TemplateType",
]
