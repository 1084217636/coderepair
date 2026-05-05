"""
复杂度评估与模型路由

根据任务复杂度自动选择最合适的 LLM 模型

核心功能：
  • 修改范围评估
  • 依赖跨度计算  
  • 错误类型分类
  • 复杂度打分
  • 模型路由决策
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List

from core.logger import get_logger

logger = get_logger(__name__)


class ComplexityLevel(Enum):
    """复杂度级别"""
    TRIVIAL = "trivial"           # 平凡：简单的格式修复
    SIMPLE = "simple"             # 简单：局部单文件修改
    MODERATE = "moderate"         # 中等：跨文件修改，简单逻辑
    COMPLEX = "complex"           # 复杂：涉及多文件，业务逻辑复杂
    VERY_COMPLEX = "very_complex" # 极复杂：涉及系统设计，深度重构


class ErrorType(Enum):
    """错误类型"""
    SYNTAX = "syntax"                 # 语法错误
    MISSING_IMPORT = "missing_import" # 缺失导入
    IMPORTS = "missing_import"        # 兼容旧测试/旧接口
    RUNTIME = "runtime"               # 运行时错误
    LOGIC = "logic"                   # 逻辑错误
    CONCURRENCY = "concurrency"       # 并发问题
    PERFORMANCE = "performance"       # 性能问题
    DESIGN = "design"                 # 设计问题


@dataclass
class ComplexityScore:
    """复杂度评分"""
    level: ComplexityLevel
    score: float  # 0-100
    factors: Dict[str, float]
    reasoning: str


class ComplexityEvaluator:
    """复杂度评估器"""
    
    def __init__(self):
        """初始化评估器"""
        self.logger = get_logger(__name__)
    
    def evaluate(
        self,
        error_type: ErrorType,
        files_affected: List[str],
        code_context: str,
    ) -> ComplexityScore:
        """
        评估复杂度
        
        Args:
            error_type: 错误类型
            files_affected: 受影响的文件列表
            code_context: 代码上下文
        
        Returns:
            复杂度评分
        """
        self.logger.info(
            f"[Complexity] 评估复杂度 | "
            f"错误类型={error_type.value} | "
            f"受影响文件数={len(files_affected)}"
        )
        
        factors = {}
        
        # 1. 错误类型评分
        error_score = self._evaluate_error_type(error_type)
        factors["error_type"] = error_score
        
        # 2. 修改范围评分
        scope_score = self._evaluate_scope(files_affected)
        factors["scope"] = scope_score
        
        # 3. 依赖跨度评分
        dependency_score = self._evaluate_dependencies(files_affected)
        factors["dependencies"] = dependency_score
        
        # 4. 代码复杂度评分
        code_score = self._evaluate_code_complexity(code_context)
        factors["code_complexity"] = code_score
        
        # 计算总体复杂度
        total_score = (
            error_score * 0.25 +
            scope_score * 0.25 +
            dependency_score * 0.25 +
            code_score * 0.25
        )
        
        # 判断复杂度级别
        level = self._score_to_level(total_score)
        
        reasoning = self._generate_reasoning(factors, total_score, level)
        
        return ComplexityScore(
            level=level,
            score=total_score,
            factors=factors,
            reasoning=reasoning,
        )
    
    def _evaluate_error_type(self, error_type: ErrorType) -> float:
        """评估错误类型的复杂度"""
        scores = {
            ErrorType.SYNTAX: 10,              # 最简单
            ErrorType.MISSING_IMPORT: 15,
            ErrorType.RUNTIME: 30,
            ErrorType.LOGIC: 50,
            ErrorType.CONCURRENCY: 70,
            ErrorType.PERFORMANCE: 65,
            ErrorType.DESIGN: 80,             # 最复杂
        }
        return scores.get(error_type, 30)
    
    def _evaluate_scope(self, files_affected: List[str]) -> float:
        """评估修改范围"""
        if not files_affected:
            return 0
        
        # 文件数量
        file_count_score = min(len(files_affected) * 5, 80)
        
        # 文件类型多样性
        file_types = set(f.split(".")[-1] for f in files_affected)
        type_diversity = len(file_types) * 5
        
        return min((file_count_score + type_diversity) / 2, 100)
    
    def _evaluate_dependencies(self, files_affected: List[str]) -> float:
        """评估依赖跨度"""
        # 简单启发式：计算文件间依赖关系的复杂度
        
        # 目录深度
        max_depth = max(
            len(f.split("/")) for f in files_affected
        ) if files_affected else 1
        depth_score = (max_depth - 1) * 10
        
        # 是否涉及 main.go 或初始化文件
        init_files = {"main.go", "init.go", "go.mod"}
        has_init = any(f.split("/")[-1] in init_files for f in files_affected)
        init_score = 20 if has_init else 0
        
        return min(depth_score + init_score, 100)
    
    def _evaluate_code_complexity(self, code_context: str) -> float:
        """评估代码复杂度"""
        if not code_context:
            return 0
        
        score = 0
        
        # 代码行数
        lines = code_context.count("\n")
        score += min(lines // 10, 30)
        
        # 嵌套深度
        max_indent = self._calculate_max_indent(code_context)
        score += max_indent * 5
        
        # 并发特性出现
        concurrent_keywords = code_context.count("go ") + code_context.count("chan")
        score += concurrent_keywords * 10
        
        # 泛型或高级特性
        if "interface{}" in code_context or "reflect" in code_context:
            score += 15
        
        return min(score, 100)
    
    def _score_to_level(self, score: float) -> ComplexityLevel:
        """根据评分判断复杂度级别"""
        if score < 15:
            return ComplexityLevel.TRIVIAL
        elif score < 30:
            return ComplexityLevel.SIMPLE
        elif score < 50:
            return ComplexityLevel.MODERATE
        elif score < 75:
            return ComplexityLevel.COMPLEX
        else:
            return ComplexityLevel.VERY_COMPLEX
    
    def _generate_reasoning(
        self,
        factors: Dict[str, float],
        total_score: float,
        level: ComplexityLevel,
    ) -> str:
        """生成复杂度评估的理由"""
        return (
            f"基于错误类型（{factors['error_type']:.0f}）、"
            f"修改范围（{factors['scope']:.0f}）、"
            f"依赖跨度（{factors['dependencies']:.0f}）、"
            f"代码复杂度（{factors['code_complexity']:.0f}），"
            f"总体评分为 {total_score:.1f}/100，"
            f"判定为 {level.value} 级别。"
        )
    
    @staticmethod
    def _calculate_max_indent(code: str) -> int:
        """计算代码的最大缩进深度"""
        max_indent = 0
        for line in code.split("\n"):
            if line.strip():
                indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, indent // 4)
        return max_indent


class ModelRouter:
    """模型路由器 - 根据复杂度选择模型"""
    
    # 模型配置
    ROUTER_CONFIG = {
        ComplexityLevel.TRIVIAL: {
            "providers": ["groq", "ollama"],  # 快速、廉价
            "preferred_provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.3,
            "max_tokens": 1024,
            "cost_tier": "free",
        },
        ComplexityLevel.SIMPLE: {
            "providers": ["groq", "openai"],
            "preferred_provider": "groq",
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.5,
            "max_tokens": 2048,
            "cost_tier": "low",
        },
        ComplexityLevel.MODERATE: {
            "providers": ["openai", "aicanapi"],
            "preferred_provider": "openai",
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 4096,
            "cost_tier": "medium",
        },
        ComplexityLevel.COMPLEX: {
            "providers": ["openai", "aicanapi"],
            "preferred_provider": "openai",
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 6000,
            "cost_tier": "high",
        },
        ComplexityLevel.VERY_COMPLEX: {
            "providers": ["openai", "aicanapi"],
            "preferred_provider": "openai",
            "model": "gpt-4",
            "temperature": 0.8,
            "max_tokens": 8000,
            "cost_tier": "very_high",
        },
    }
    
    def __init__(self):
        """初始化路由器"""
        self.logger = get_logger(__name__)
    
    def route(
        self,
        complexity_score: ComplexityScore,
        preferred_provider: Optional[str] = None,
    ) -> Dict:
        """
        路由模型选择
        
        Args:
            complexity_score: 复杂度评分
            preferred_provider: 首选提供商（可选）
        
        Returns:
            模型和配置信息
        """
        level = complexity_score.level
        
        self.logger.info(
            f"[Router] 路由模型选择 | "
            f"复杂度级别={level.value} | "
            f"评分={complexity_score.score:.1f}"
        )
        
        config = self.ROUTER_CONFIG[level].copy()
        
        # 选择提供商
        if preferred_provider and preferred_provider in config["providers"]:
            selected_provider = preferred_provider
        else:
            selected_provider = config["preferred_provider"]
        
        # 根据提供商调整模型
        config["selected_provider"] = selected_provider
        config["model"] = self._get_model_for_provider(selected_provider, level)
        
        # 成本估算
        config["estimated_cost"] = self._estimate_cost(
            config["max_tokens"],
            config["selected_provider"],
            level,
        )
        
        self.logger.info(
            f"[Router] 模型选择完成 | "
            f"提供商={selected_provider} | "
            f"模型={config['model']}"
        )
        
        return config
    
    @staticmethod
    def _get_model_for_provider(provider: str, level: ComplexityLevel) -> str:
        """根据提供商和复杂度级别获取模型"""
        models = {
            "groq": "llama-3.3-70b-versatile",
            "ollama": "llama2",
            "openai": "gpt-4" if level in [
                ComplexityLevel.COMPLEX,
                ComplexityLevel.VERY_COMPLEX
            ] else "gpt-3.5-turbo",
            "aicanapi": "claude-opus-4-6" if level in [
                ComplexityLevel.COMPLEX,
                ComplexityLevel.VERY_COMPLEX
            ] else "claude-sonnet-4-6",
        }
        return models.get(provider, "llama-3.3-70b-versatile")
    
    @staticmethod
    def _estimate_cost(
        max_tokens: int,
        provider: str,
        level: ComplexityLevel,
    ) -> Dict:
        """估算成本"""
        # 近似的 token 成本（USD）
        token_costs = {
            "groq": 0,                    # 免费
            "ollama": 0,                  # 本地
            "openai": {
                "input": 0.00003,         # GPT-4 input
                "output": 0.00006,        # GPT-4 output
            },
            "aicanapi": {
                "input": 0.00001,         # Claude input
                "output": 0.00003,        # Claude output
            },
        }
        
        cost_info = token_costs.get(provider, {})
        
        if isinstance(cost_info, dict):
            input_tokens = max_tokens // 4
            output_tokens = max_tokens
            estimated = (
                input_tokens * cost_info["input"] +
                output_tokens * cost_info["output"]
            )
        else:
            estimated = 0
        
        return {
            "provider": provider,
            "estimated_total_usd": round(estimated, 6),
            "level": level.value,
        }
