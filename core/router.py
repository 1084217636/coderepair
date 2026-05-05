"""
模型路由集成

将复杂度评估与 LLM 客户端集成
"""

from typing import Optional, Dict

from core.logger import get_logger
from core.complexity import (
    ComplexityEvaluator,
    ModelRouter,
    ErrorType,
)
from llm.client import LLMClient

logger = get_logger(__name__)


class IntelligentLLMRouter:
    """智能 LLM 路由器 - 集合复杂度评估和模型选择"""
    
    def __init__(self):
        """初始化智能路由器"""
        self.evaluator = ComplexityEvaluator()
        self.router = ModelRouter()
        self.llm_client = None
        self.logger = get_logger(__name__)
    
    def call_with_routing(
        self,
        error_type: ErrorType,
        files_affected: list,
        code_context: str,
        system_prompt: str,
        user_message: str,
        preferred_provider: Optional[str] = None,
    ) -> Dict:
        """
        根据复杂度智能路由并调用 LLM
        
        Args:
            error_type: 错误类型
            files_affected: 受影响的文件
            code_context: 代码上下文
            system_prompt: 系统提示
            user_message: 用户消息
            preferred_provider: 首选提供商
        
        Returns:
            LLM 响应和路由信息
        """
        self.logger.info("[IntelligentRouter] 开始智能路由调用")
        
        # 1. 评估复杂度
        complexity_score = self.evaluator.evaluate(
            error_type=error_type,
            files_affected=files_affected,
            code_context=code_context,
        )
        
        self.logger.info(
            f"[IntelligentRouter] 复杂度评估 | "
            f"级别={complexity_score.level.value} | "
            f"评分={complexity_score.score:.1f}"
        )
        
        # 2. 路由选择模型
        route_config = self.router.route(
            complexity_score=complexity_score,
            preferred_provider=preferred_provider,
        )
        
        # 3. 调用 LLM
        response = self._call_llm_with_config(
            config=route_config,
            system_prompt=system_prompt,
            user_message=user_message,
        )
        
        return {
            "response": response.get("response", ""),
            "model": response.get("model"),
            "provider": response.get("provider"),
            "stop_reason": response.get("stop_reason"),
            "usage": response.get("usage"),
            "estimated_cost": response.get("estimated_cost"),
            "routing": {
                "complexity": complexity_score,
                "config": route_config,
            },
        }
    
    def _call_llm_with_config(
        self,
        config: Dict,
        system_prompt: str,
        user_message: str,
    ) -> Dict:
        """使用指定配置调用 LLM"""
        self.logger.info(
            f"[IntelligentRouter] 调用 LLM | "
            f"提供商={config['selected_provider']} | "
            f"模型={config['model']}"
        )
        
        client = LLMClient(
            provider=config["selected_provider"],
            model=config["model"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
        )
        response = client.call(
            system_prompt=system_prompt,
            user_message=user_message,
        )
        response["provider"] = config["selected_provider"]
        response["estimated_cost"] = config.get("estimated_cost")
        return response


def route_and_call_llm(
    error_type: ErrorType,
    files_affected: list,
    code_context: str,
    system_prompt: str,
    user_message: str,
    preferred_provider: Optional[str] = None,
) -> Dict:
    """
    便捷函数：一键路由和调用 LLM
    
    Args:
        error_type: 错误类型
        files_affected: 受影响的文件
        code_context: 代码上下文
        system_prompt: 系统提示
        user_message: 用户消息
        preferred_provider: 首选提供商
    
    Returns:
        响应和路由信息
    """
    router = IntelligentLLMRouter()
    return router.call_with_routing(
        error_type=error_type,
        files_affected=files_affected,
        code_context=code_context,
        system_prompt=system_prompt,
        user_message=user_message,
        preferred_provider=preferred_provider,
    )
