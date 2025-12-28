"""
向后兼容模块：重新导出 llm_service 的内容
这个文件只是为了保持向后兼容性，所有实际逻辑都在 llm_service.py 中
"""

# 从新的通用LLM服务导入所有内容
from .llm_service import (
    LLMService,
    LLMError, LLMAuthError, LLMRateLimitError, LLMBadRequest, 
    LLMServerError, LLMNetworkError, LLMParseError,
    llm_service
)

# 向后兼容：保留旧的类名和实例
DeepSeekService = LLMService
deepseek_service = llm_service

# 向后兼容：保留旧的异常类名
DeepSeekError = LLMError
DeepSeekAuthError = LLMAuthError
DeepSeekRateLimitError = LLMRateLimitError
DeepSeekBadRequest = LLMBadRequest
DeepSeekServerError = LLMServerError
DeepSeekNetworkError = LLMNetworkError
DeepSeekParseError = LLMParseError
