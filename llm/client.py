"""
LLM 客户端 - 统一的 LLM 调用接口
"""
import json
import time
from typing import Optional, Dict, Any
from urllib import error, request

import httpx

from core.logger import get_logger
from config import settings

logger = get_logger(__name__)


class LLMClient:
    """
    LLM 客户端
    
    职责：
    1. 初始化 LLM 连接（支持 OpenAI/Groq/Ollama 等 OpenAI 兼容的 API）
    2. 发送请求
    3. 处理响应
    4. 记录调用信息
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """初始化 LLM 客户端"""
        self.logger = get_logger(__name__)
        self.provider = (provider or settings.LLM_PROVIDER).lower()
        self.api_key = api_key if api_key is not None else self._resolve_api_key(self.provider)
        self.api_base = api_base or self._resolve_api_base(self.provider)
        self.model = model or self._resolve_model(self.provider)
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
        self.connect_timeout = settings.LLM_CONNECT_TIMEOUT
        self.read_timeout = settings.LLM_READ_TIMEOUT
        self.retry_attempts = settings.LLM_RETRY_ATTEMPTS
        self.allow_mock = settings.LLM_ALLOW_MOCK
        
        self.client = None
        self._init_client()

    @staticmethod
    def _resolve_model(provider: str) -> str:
        """根据 provider 解析模型名称"""
        models = {
            "groq": settings.GROQ_MODEL,
            "openai": settings.OPENAI_MODEL,
            "ollama": settings.OLLAMA_MODEL,
            "aicanapi": settings.AICANAPI_MODEL,
        }
        return models.get(provider, settings.LLM_MODEL)

    @staticmethod
    def _resolve_api_key(provider: str) -> str:
        """根据 provider 解析 API Key"""
        api_keys = {
            "groq": settings.GROQ_API_KEY,
            "openai": settings.OPENAI_API_KEY,
            "ollama": "",
            "aicanapi": settings.AICANAPI_API_KEY,
        }
        return api_keys.get(provider, settings.LLM_API_KEY)

    @staticmethod
    def _resolve_api_base(provider: str) -> str:
        """根据 provider 解析 API Base"""
        api_bases = {
            "groq": settings.GROQ_API_BASE,
            "openai": settings.OPENAI_API_BASE,
            "ollama": settings.OLLAMA_API_BASE,
            "aicanapi": settings.AICANAPI_API_BASE,
        }
        return api_bases.get(provider, settings.LLM_API_BASE)
    
    def _init_client(self):
        """初始化 LLM 客户端（支持多个提供商）"""
        try:
            from openai import OpenAI
            
            # 所有提供商都使用 OpenAI 兼容的 API
            self.client = OpenAI(
                api_key=self.api_key if self.api_key else "not-needed",  # Ollama 可能不需要
                base_url=self.api_base
            )
            
            self.logger.info(
                f"[LLM] 初始化完成 | "
                f"provider={self.provider} | "
                f"model={self.model} | "
                f"api_base={self.api_base}"
            )
        except ImportError:
            self.logger.warning("[LLM] openai 客户端未安装，将回退到直接 HTTP 调用或模拟模式")
        except Exception as e:
            self.logger.warning(f"[LLM] SDK 初始化失败，将尝试直接 HTTP 调用 | error={e}")
    
    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        调用 LLM
        
        Args:
            system_prompt: 系统提示
            user_message: 用户消息
            max_tokens: 最大令牌数
        
        Returns:
            包含响应和元数据的字典
        """
        self.logger.info(f"[Stage 7] 调用 LLM | provider={self.provider} | model={self.model}")
        self.logger.debug(f"[LLM] System Prompt 长度: {len(system_prompt)}")
        self.logger.debug(f"[LLM] User Message 长度: {len(user_message)}")
        
        # 检查 API Key（某些提供商可能不需要，如 Ollama）
        if self.provider != "ollama" and (not self.api_key or self.api_key == ""):
            return self._handle_failure(
                f"[LLM] 未配置 {self.provider.upper()} API Key",
                system_prompt,
                user_message,
            )
        
        if max_tokens is None:
            max_tokens = self.max_tokens
        
        try:
            if not self.client:
                self.logger.warning("[LLM] SDK 客户端不可用，直接走 HTTP 调用")
                return self._call_via_http(system_prompt, user_message, max_tokens)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            
            result = {
                "response": response.choices[0].message.content,
                "model": response.model,
                "stop_reason": response.choices[0].finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            }
            
            self.logger.info(
                f"[Stage 7] LLM 调用完成 | "
                f"tokens_used={result['usage']['total_tokens']} | "
                f"finish_reason={result['stop_reason']}"
            )
            
            return result
        
        except Exception as e:
            self.logger.warning(f"[LLM] SDK 调用失败，尝试直接 HTTP 调用 | error={e}")
            try:
                return self._call_via_http(system_prompt, user_message, max_tokens)
            except Exception as http_error:
                return self._handle_failure(
                    f"[LLM] HTTP 调用失败 | error={http_error}",
                    system_prompt,
                    user_message,
                    exception=http_error,
                )

    def _call_via_http(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """使用 OpenAI 兼容接口直接发 HTTP 请求"""
        url = self._chat_completions_url()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CodeRepair/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.logger.info(f"[LLM] 使用直接 HTTP 调用 | provider={self.provider} | url={url}")

        last_error: Optional[Exception] = None
        for attempt in range(self.retry_attempts + 1):
            try:
                with httpx.Client(
                    timeout=httpx.Timeout(
                        connect=self.connect_timeout,
                        read=self.read_timeout,
                        write=30.0,
                        pool=5.0,
                    )
                ) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    body = response.text
                    break
            except httpx.HTTPStatusError as e:
                last_error = self._format_http_status_error(e)
                status_code = e.response.status_code
                if self._should_retry_status(status_code) and attempt < self.retry_attempts:
                    self.logger.warning(
                        f"[LLM] HTTP 状态可重试 | status={status_code} | attempt={attempt + 1}"
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise last_error from e
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = RuntimeError(f"网络异常: {e}")
                if attempt < self.retry_attempts:
                    self.logger.warning(
                        f"[LLM] 网络异常，准备重试 | attempt={attempt + 1} | error={e}"
                    )
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise last_error from e
        else:
            raise last_error or RuntimeError("HTTP 调用失败")

        data = json.loads(body)
        content = self._extract_response_content(data)
        usage = data.get("usage") or {}
        finish_reason = None
        if data.get("choices"):
            finish_reason = data["choices"][0].get("finish_reason")

        result = {
            "response": content,
            "model": data.get("model", self.model),
            "stop_reason": finish_reason or "http",
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        }

        self.logger.info(
            f"[Stage 7] HTTP 调用完成 | "
            f"tokens_used={result['usage']['total_tokens']} | "
            f"finish_reason={result['stop_reason']}"
        )

        return result

    @staticmethod
    def _should_retry_status(status_code: int) -> bool:
        """仅对典型瞬时错误执行重试。"""
        return status_code == 429 or 500 <= status_code < 600

    @staticmethod
    def _format_http_status_error(exc: httpx.HTTPStatusError) -> RuntimeError:
        """解析结构化错误，便于上层判断是否可恢复。"""
        status_code = exc.response.status_code
        body = exc.response.text
        try:
            error_data = exc.response.json()
        except json.JSONDecodeError:
            error_data = {}

        error_info = error_data.get("error") or {}
        error_code = error_info.get("code", "")
        error_message = error_info.get("message", body[:300])

        if status_code == 400:
            return RuntimeError(f"HTTP 400 [{error_code or 'bad_request'}]: {error_message}")
        return RuntimeError(f"HTTP {status_code} [{error_code or 'unknown'}]: {error_message}")

    def _handle_failure(
        self,
        reason: str,
        system_prompt: str,
        user_message: str,
        exception: Optional[Exception] = None,
    ) -> Dict[str, Any]:
        """根据配置决定是否允许回退到 mock。"""
        if not self.allow_mock:
            if exception:
                raise RuntimeError(reason) from exception
            raise RuntimeError(reason)

        self.logger.error(f"{reason}，回退模拟模式")
        return self._mock_response(system_prompt, user_message)

    def _chat_completions_url(self) -> str:
        """拼接 chat completions URL"""
        base = self.api_base.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    @staticmethod
    def _extract_response_content(data: Dict[str, Any]) -> str:
        """从 OpenAI 兼容响应里提取文本内容"""
        choices = data.get("choices") or []
        if not choices:
            return ""

        message = choices[0].get("message") or {}
        content = message.get("content", "")

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return "\n".join(part for part in text_parts if part)

        return str(content)
    
    def _mock_response(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """生成模拟响应"""
        mock_responses = {
            "bug_fix": """根据代码分析，我发现了以下问题：

1. **问题分析**：代码中存在逻辑错误
2. **修复建议**：优化算法或修改返回值
3. **代码示例**：
```go
// 修复后的代码
func (u *User) Calculate(x int) int {
    result := x * u.Age
    if result > 1000 {
        return 1000
    }
    return result  // 移除了原来的 - 1 错误
}
```
4. **测试建议**：添加单元测试确保边界条件

（这是模拟回复，实际使用时请配置真实的 LLM API）""",
            
            "feature": """我建议实现以下功能：

1. **需求分析**：完整的需求理解
2. **架构设计**：清晰的接口设计
3. **实现代码**：完整的实现示例
4. **使用示例**：演示如何使用新功能
5. **扩展建议**：未来可能的改进方向

（这是模拟回复，实际使用时请配置真实的 LLM API）""",
            
            "review": """我已经完成了基础审查，建议优先关注以下方向：

1. 检查关键函数的边界条件和异常路径
2. 为核心逻辑补充单元测试，避免回归
3. 关注可维护性：命名、注释和职责拆分
4. 如果后续接入真实 LLM，可结合更多上下文给出更细的修改建议

（这是模拟回复，实际使用时请配置真实的 LLM API）""",
        }

        lower_user_message = user_message.lower()
        lower_system_prompt = system_prompt.lower()
        combined_text = f"{lower_system_prompt}\n{lower_user_message}"

        bug_keywords = ("bug", "fix", "修复", "错误", "报错", "panic", "crash", "error")
        feature_keywords = ("feature", "implement", "新增", "实现", "添加", "功能")
        review_keywords = ("review", "审查", "检查", "建议", "优化")

        # 检测任务类型
        if any(keyword in combined_text for keyword in bug_keywords):
            response = mock_responses["bug_fix"]
        elif any(keyword in combined_text for keyword in feature_keywords):
            response = mock_responses["feature"]
        elif any(keyword in combined_text for keyword in review_keywords):
            response = mock_responses["review"]
        else:
            response = (
                "我对您的代码做了分析。请配置真实的 LLM API Key 获得完整的 AI 辅助服务。\n\n"
                f"当前配置：\n"
                f"- 提供商: {self.provider}\n"
                f"- API Base: {self.api_base}\n"
                f"- Model: {self.model}\n"
                f"- Status: 模拟模式\n\n"
                "（这是模拟回复，实际使用时请配置真实的 LLM API）"
            )

        return {
            "response": response,
            "model": self.model,
            "stop_reason": "mock",
            "usage": {
                "prompt_tokens": len(system_prompt.split()),
                "completion_tokens": len(response.split()),
                "total_tokens": len(system_prompt.split()) + len(response.split()),
            }
        }
