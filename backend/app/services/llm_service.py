import asyncio
import copy
import httpx
import json
import logging
import re
from typing import List, Dict, Any, Optional
from ..core.config import settings
from .field_synonyms import FIELD_SYNONYMS, get_field_synonyms, normalize_field_name

logger = logging.getLogger(__name__)

# 通用LLM错误类（保持向后兼容）
class LLMError(Exception):
    status_code: int = 500
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code

class LLMAuthError(LLMError):
    status_code = 401

class LLMRateLimitError(LLMError):
    status_code = 429

class LLMBadRequest(LLMError):
    status_code = 400

class LLMServerError(LLMError):
    status_code = 502

class LLMNetworkError(LLMError):
    status_code = 503

class LLMParseError(LLMError):
    status_code = 502

# 向后兼容：保留旧的异常类名
DeepSeekError = LLMError
DeepSeekAuthError = LLMAuthError
DeepSeekRateLimitError = LLMRateLimitError
DeepSeekBadRequest = LLMBadRequest
DeepSeekServerError = LLMServerError
DeepSeekNetworkError = LLMNetworkError
DeepSeekParseError = LLMParseError

class LLMService:
    """
    通用LLM服务，支持多个provider（DeepSeek、豆包等）
    根据用户配置或系统配置动态选择provider
    """
    def __init__(self, db_session=None, provider: str = "deepseek"):
        """
        初始化LLM服务
        Args:
            db_session: 数据库会话（可选）
            provider: 默认provider（deepseek/doubao等）
        """
        self.db_session = db_session
        self.timeout = 360.0  # 设置为360秒（6分钟）
        self.work_chunk_size = 3
        self.work_chunk_threshold = 6
        
        # 用户上下文（用于动态选择用户配置）
        self._current_user = None
        self._current_db_session = None
        
        # Provider配置映射
        self._provider_configs = {
            "deepseek": {
                "default_base_url": "https://api.deepseek.com/v1",
                "default_model": "deepseek-chat",
                "config_prefix": "llm.deepseek"
            },
            "doubao": {
                "default_base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                "default_model": "doubao-seed-1-6-lite-251015",
                "config_prefix": "llm.doubao"
            },
            "qwen": {
                "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "default_model": "qwen3-next-80b-a3b-instruct",
                "config_prefix": "llm.qwen"
            }
        }
        
        # 当前provider
        self.provider = provider.lower()
        if self.provider not in self._provider_configs:
            logger.warning(f"未知的provider: {self.provider}，使用deepseek作为默认值")
            self.provider = "deepseek"
        
        # 初始化时设置默认值
        self.api_key = None
        self.base_url = self._provider_configs[self.provider]["default_base_url"]
        self.model_name = self._provider_configs[self.provider]["default_model"]
        
        # 如果提供了数据库会话，从数据库读取配置
        if self.db_session:
            self._load_config_from_db()
        
        # 验证 API Key 是否已配置
        if not self.api_key:
            logger.warning(f"[LLM] {self.provider.upper()} API Key 未配置！请在管理后台配置API密钥")
        else:
            logger.info(f"[LLM] {self.provider.upper()} API Key 已配置，长度: {len(self.api_key)} 字符")
    
    def _load_config_from_db(self):
        """从数据库加载配置"""
        try:
            from ..services.config_service import config_service
            config_prefix = self._provider_configs[self.provider]["config_prefix"]
            
            db_api_key = config_service.get_setting(self.db_session, f"{config_prefix}.api_key")
            db_base_url = config_service.get_setting(self.db_session, f"{config_prefix}.base_url")
            db_model_name = config_service.get_setting(self.db_session, f"{config_prefix}.model_name")
            
            if db_api_key:
                self.api_key = db_api_key
                logger.info(f"[LLM] {self.provider.upper()} API Key 从数据库配置读取")
            if db_base_url:
                self.base_url = db_base_url
                logger.info(f"[LLM] {self.provider.upper()} Base URL 从数据库配置读取: {self.base_url}")
            if db_model_name:
                self.model_name = db_model_name
                logger.info(f"[LLM] {self.provider.upper()} Model Name 从数据库配置读取: {self.model_name}")
        except Exception as e:
            logger.error(f"[LLM] 从数据库读取配置失败: {e}")
    
    def set_user_context(self, user, db_session):
        """设置用户上下文，用于动态选择用户配置"""
        self._current_user = user
        self._current_db_session = db_session
    
    def _get_user_llm_config(self, user, db_session):
        """
        获取用户的LLM配置
        优先级：
        1. 管理员账户 -> 使用平台Key
        2. 用户自定义配置 -> 使用用户Key
        3. 无用户配置 -> 返回None，需要从系统配置读取
        """
        from ..models.user_llm_config import UserLLMConfig
        
        # 管理员账户始终使用平台Key
        if user.user_type in ['super_admin', 'template_designer']:
            return None  # 返回None表示使用平台Key
        
        # 获取用户自定义配置
        user_config = db_session.query(UserLLMConfig).filter(UserLLMConfig.user_id == user.id).first()
        if user_config and user_config.api_key:
            logger.debug(f"[LLM] 用户 {user.email} 有个人配置，使用用户Key（provider: {user_config.provider}）")
            return {
                "provider": user_config.provider,
                "api_key": user_config.api_key,
                "base_url": user_config.base_url,
                "model_name": user_config.model_name
            }
        
        # 如果没有用户配置，返回None，让系统使用系统配置（fallback）
        # 如果系统配置也没有，会在 _get_api_key 中抛出错误
        logger.debug(f"[LLM] 用户 {user.email} 没有个人配置，将使用系统配置（如果可用）")
        return None  # 返回None表示使用系统配置
    
    def _is_provider_enabled(self, provider_name: str, db_session=None) -> bool:
        """
        检查provider是否启用
        
        逻辑：
        1. 如果配置存在且值为 'true'，返回 True
        2. 如果配置存在且值为 'false'，返回 False
        3. 如果配置不存在，返回 True（向后兼容，保持原有行为）
        4. 如果检查出错，记录警告并返回 True（容错处理）
        """
        db = db_session or self.db_session
        if not db:
            return True  # 如果没有数据库会话，默认启用（兼容性）
        
        try:
            from ..services.config_service import config_service
            config_prefix = self._provider_configs[provider_name]["config_prefix"]
            enabled_setting = config_service.get_setting(db, f"{config_prefix}.enabled")
            
            # 如果配置不存在，默认启用（向后兼容）
            # 注意：这意味着新安装的系统默认启用所有provider
            if enabled_setting is None:
                logger.debug(f"[LLM] {provider_name.upper()} 启用状态未配置，默认启用（向后兼容）")
                return True
            
            # 检查是否为"true"（字符串，不区分大小写）
            enabled = enabled_setting.lower().strip() == 'true'
            logger.debug(f"[LLM] {provider_name.upper()} 启用状态: {enabled} (配置值: {enabled_setting})")
            return enabled
        except Exception as e:
            logger.warning(f"[LLM] 检查provider {provider_name} 启用状态失败: {e}，默认启用（容错处理）")
            return True  # 出错时默认启用（容错处理）
    
    def _get_api_key(self, user=None, db_session=None, user_config_cache=None):
        """获取API密钥（支持用户配置和系统配置，带fallback逻辑）"""
        effective_user = user or self._current_user
        effective_db_session = db_session or self._current_db_session
        
        # 如果有用户上下文，优先使用用户配置（用户配置不受系统开关限制）
        if effective_user and effective_db_session:
            # 使用缓存的用户配置，避免重复查询数据库
            user_config = user_config_cache if user_config_cache is not None else self._get_user_llm_config(effective_user, effective_db_session)
            if user_config and user_config.get("api_key"):
                # 用户配置的API key直接使用，不受系统开关限制
                logger.debug(f"[LLM] 使用用户配置的API key（provider: {user_config.get('provider', 'unknown')}）")
                return user_config["api_key"]
        
        # 获取当前使用的provider（用于系统配置）
        current_provider = self._get_provider(effective_user, effective_db_session, user_config_cache)
        
        # 从系统配置读取（系统配置受系统开关限制）
        if self.db_session or effective_db_session:
            try:
                from ..services.config_service import config_service
                db = self.db_session or effective_db_session
                config_prefix = self._provider_configs[current_provider]["config_prefix"]
                
                # 检查当前provider是否启用
                if not self._is_provider_enabled(current_provider, db):
                    logger.info(f"[LLM] {current_provider.upper()} 已关闭，尝试查找其他可用的provider...")
                else:
                    db_api_key = config_service.get_setting(db, f"{config_prefix}.api_key")
                    # 如果找到了当前provider的API key，直接返回，不进行fallback
                    if db_api_key and db_api_key.strip():
                        return db_api_key
                
                # Fallback: 只有在当前provider的API密钥确实不可用或已关闭时，才尝试其他provider
                # 只有在没有用户配置的情况下才进行fallback（用户配置的provider优先级最高）
                # 使用缓存的用户配置，避免重复查询数据库
                has_user_config = False
                if effective_user and effective_db_session:
                    cached_config = user_config_cache if user_config_cache is not None else self._get_user_llm_config(effective_user, effective_db_session)
                    has_user_config = cached_config is not None and cached_config.get("api_key") is not None
                
                # 只有在当前provider确实没有配置或已关闭，且用户也没有配置时，才进行fallback
                current_provider_enabled = self._is_provider_enabled(current_provider, db)
                current_provider_has_key = config_service.get_setting(db, f"{config_prefix}.api_key")
                
                if not has_user_config and (not current_provider_enabled or not current_provider_has_key):
                    logger.info(f"[LLM] {current_provider.upper()} 不可用（已关闭或未配置），尝试查找其他可用的provider...")
                    for provider_name, provider_config in self._provider_configs.items():
                        if provider_name == current_provider:
                            continue  # 跳过当前provider
                        # 检查provider是否启用
                        if not self._is_provider_enabled(provider_name, db):
                            logger.debug(f"[LLM] {provider_name.upper()} 已关闭，跳过")
                            continue
                        fallback_api_key = config_service.get_setting(db, f"{provider_config['config_prefix']}.api_key")
                        if fallback_api_key and fallback_api_key.strip():
                            logger.info(f"[LLM] 找到可用的provider: {provider_name.upper()}，将使用该provider")
                            # 更新当前provider（临时，仅用于本次调用）
                            self.provider = provider_name
                            return fallback_api_key
            except Exception as e:
                logger.warning(f"[LLM] 从数据库读取API Key失败: {e}")
        
        return self.api_key
    
    def _get_base_url(self, user=None, db_session=None, user_config_cache=None):
        """获取Base URL（支持用户配置和系统配置，带fallback逻辑）"""
        effective_user = user or self._current_user
        effective_db_session = db_session or self._current_db_session
        
        # 获取当前使用的provider（可能已被fallback修改）
        current_provider = self.provider  # 使用self.provider，因为_get_api_key可能已经更新了它
        
        # 如果有用户上下文，优先使用用户配置（使用缓存的配置，避免重复查询数据库）
        if effective_user and effective_db_session:
            user_config = user_config_cache if user_config_cache is not None else self._get_user_llm_config(effective_user, effective_db_session)
            if user_config and user_config.get("base_url"):
                return user_config["base_url"]
        
        # 从系统配置读取（使用当前provider的配置）
        if self.db_session or effective_db_session:
            try:
                from ..services.config_service import config_service
                db = self.db_session or effective_db_session
                config_prefix = self._provider_configs[current_provider]["config_prefix"]
                db_base_url = config_service.get_setting(db, f"{config_prefix}.base_url")
                if db_base_url:
                    return db_base_url
            except Exception as e:
                logger.warning(f"[LLM] 从数据库读取Base URL失败: {e}")
        
        # 返回当前provider的默认base_url
        return self._provider_configs[current_provider]["default_base_url"]
    
    def _get_model_name(self, user=None, db_session=None, user_config_cache=None):
        """获取模型名称（支持用户配置和系统配置，带fallback逻辑）"""
        effective_user = user or self._current_user
        effective_db_session = db_session or self._current_db_session
        
        # 获取当前使用的provider（可能已被fallback修改）
        current_provider = self.provider  # 使用self.provider，因为_get_api_key可能已经更新了它
        
        # 如果有用户上下文，优先使用用户配置（使用缓存的配置，避免重复查询数据库）
        if effective_user and effective_db_session:
            user_config = user_config_cache if user_config_cache is not None else self._get_user_llm_config(effective_user, effective_db_session)
            if user_config and user_config.get("model_name"):
                return user_config["model_name"]
            # 如果用户配置了provider但没有model_name，使用该provider的默认模型
            if user_config and user_config.get("provider"):
                provider = user_config["provider"].lower()
                if provider in self._provider_configs:
                    return self._provider_configs[provider]["default_model"]
        
        # 从系统配置读取（使用当前provider的配置）
        if self.db_session or effective_db_session:
            try:
                from ..services.config_service import config_service
                db = self.db_session or effective_db_session
                config_prefix = self._provider_configs[current_provider]["config_prefix"]
                db_model_name = config_service.get_setting(db, f"{config_prefix}.model_name")
                if db_model_name:
                    return db_model_name
            except Exception as e:
                logger.warning(f"[LLM] 从数据库读取Model Name失败: {e}")
        
        # 返回当前provider的默认模型
        return self._provider_configs[current_provider]["default_model"]
    
    def _get_provider(self, user=None, db_session=None, user_config_cache=None):
        """获取当前使用的provider"""
        effective_user = user or self._current_user
        effective_db_session = db_session or self._current_db_session
        
        # 如果有用户上下文，优先使用用户配置的provider（使用缓存的配置，避免重复查询数据库）
        if effective_user and effective_db_session:
            user_config = user_config_cache if user_config_cache is not None else self._get_user_llm_config(effective_user, effective_db_session)
            if user_config and user_config.get("provider"):
                return user_config["provider"].lower()
        
        # 如果没有用户配置，尝试从系统配置中选择第一个可用的provider
        # 这样可以确保用户也能使用系统配置的provider（如千问），而不仅仅是默认的deepseek
        if effective_db_session:
            try:
                from ..services.config_service import config_service
                db = effective_db_session
                # 按照优先级顺序检查provider是否可用（启用且有API key）
                for provider_name in self._provider_configs.keys():
                    if self._is_provider_enabled(provider_name, db):
                        config_prefix = self._provider_configs[provider_name]["config_prefix"]
                        api_key = config_service.get_setting(db, f"{config_prefix}.api_key")
                        if api_key and api_key.strip():
                            logger.info(f"[LLM] 从系统配置中选择provider: {provider_name.upper()} (启用状态: True, API key存在: True)")
                            # 更新self.provider，确保后续使用正确的provider
                            self.provider = provider_name
                            return provider_name
                    else:
                        logger.debug(f"[LLM] {provider_name.upper()} 未启用，跳过")
            except Exception as e:
                logger.warning(f"[LLM] 从系统配置选择provider失败: {e}，使用默认provider")
                import traceback
                logger.error(f"[LLM] 错误堆栈: {traceback.format_exc()}")
        
        # 如果系统配置也没有可用的provider，返回默认provider
        logger.warning(f"[LLM] 没有找到可用的provider，使用默认provider: {self.provider}")
        return self.provider

    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        max_tokens: int = 4000,
        user: Optional[Any] = None,
        db_session: Optional[Any] = None
    ) -> str:
        """
        调用LLM聊天补全API（支持多provider）
        """
        # 性能优化：一次性获取用户配置，避免多次数据库查询
        effective_user = user or self._current_user
        effective_db_session = db_session or self._current_db_session
        user_config_cache = None
        is_using_user_config = False
        if effective_user and effective_db_session:
            user_config_cache = self._get_user_llm_config(effective_user, effective_db_session)
            # 检查是否使用用户配置（用户配置不受系统开关限制）
            is_using_user_config = user_config_cache is not None and user_config_cache.get("api_key") is not None
        
        # 获取当前使用的provider和配置
        # 注意：_get_api_key可能会更新self.provider（fallback逻辑）
        api_key = self._get_api_key(user, db_session, user_config_cache)
        current_provider = self.provider  # 使用更新后的provider
        
        # 检查最终使用的provider是否启用（仅对系统配置进行检查，用户配置不受系统开关限制）
        if not is_using_user_config and not self._is_provider_enabled(current_provider, effective_db_session):
            # 如果所有provider都已关闭，抛出错误
            enabled_providers = [name for name in self._provider_configs.keys() 
                               if self._is_provider_enabled(name, effective_db_session)]
            if not enabled_providers:
                raise LLMError("所有LLM provider都已关闭，请至少启用一个provider", 503)
            else:
                raise LLMError(f"{current_provider.upper()} 已关闭，请启用该provider或使用其他可用的provider", 503)
        
        base_url = self._get_base_url(user, db_session, user_config_cache)
        model_name = self._get_model_name(user, db_session, user_config_cache)
        
        if not api_key:
            # 提供更详细的错误信息
            error_message = f"{current_provider.upper()} API密钥未配置"
            if effective_user and effective_db_session:
                # 检查用户是否有个人配置
                user_config = self._get_user_llm_config(effective_user, effective_db_session)
                if not user_config or not user_config.get("api_key"):
                    error_message = (
                        "未配置个人API密钥，且系统配置也不可用。"
                        "请前往\"设置\"页面配置您的大模型API密钥，或联系管理员配置系统API密钥。"
                    )
            raise LLMAuthError(error_message, 401)
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        # 使用更明确的超时设置：连接超时10秒，总超时使用self.timeout（默认360秒）
        timeout = httpx.Timeout(self.timeout, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                # 估算请求大小
                import json as json_lib
                import time
                request_size = len(json_lib.dumps(data))
                logger.info(f"[LLM {current_provider.upper()}] 调用开始: {len(messages)}条消息, 模型: {model_name}, 请求大小: {request_size // 1024}KB")
                
                api_call_start = time.time()
                # 豆包的base_url已经包含完整路径，不需要再追加/chat/completions
                # 其他provider（如DeepSeek）的base_url是基础URL，需要追加/chat/completions
                if current_provider == "doubao" and "/chat/completions" in base_url:
                    api_url = base_url
                else:
                    api_url = f"{base_url}/chat/completions"
                
                response = await client.post(
                    api_url,
                    headers=headers,
                    json=data
                )
                api_call_elapsed = time.time() - api_call_start
                
                # 精细化状态码处理
                from ..core.monitoring import record_llm_call, record_error
                if response.status_code == 401:
                    record_llm_call(current_provider, api_call_elapsed, success=False)
                    record_error("llm_auth_error", f"{current_provider.upper()}鉴权失败")
                    raise LLMAuthError(f"{current_provider.upper()}鉴权失败", 401)
                if response.status_code == 429:
                    record_llm_call(current_provider, api_call_elapsed, success=False)
                    record_error("llm_rate_limit", f"{current_provider.upper()}限流")
                    raise LLMRateLimitError(f"{current_provider.upper()}限流，请稍后重试", 429)
                if 400 <= response.status_code < 500:
                    record_llm_call(current_provider, api_call_elapsed, success=False)
                    record_error("llm_bad_request", f"{current_provider.upper()}请求错误")
                    raise LLMBadRequest(f"{current_provider.upper()}请求错误: {response.text}", response.status_code)
                if response.status_code >= 500:
                    record_llm_call(current_provider, api_call_elapsed, success=False)
                    record_error("llm_server_error", f"{current_provider.upper()}服务不可用")
                    raise LLMServerError(f"{current_provider.upper()}服务不可用", 502)
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # 记录性能指标
                response_size = len(content)
                usage = result.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                # 记录LLM调用指标
                from ..core.monitoring import record_llm_call
                record_llm_call(current_provider, api_call_elapsed, success=True)
                
                logger.info(
                    f"[LLM {current_provider.upper()}] 调用成功: 耗时{api_call_elapsed:.2f}秒, "
                    f"响应大小: {response_size // 1024}KB, "
                    f"Token使用: {total_tokens} (prompt: {prompt_tokens}, completion: {completion_tokens})"
                )
                
                return content
                
            except httpx.HTTPStatusError as e:
                logger.error(f"[LLM {current_provider.upper()}] API HTTP错误: {e.response.status_code} - {e.response.text}")
                raise LLMServerError(f"{current_provider.upper()}响应异常", 502)
            except httpx.TimeoutException as e:
                logger.error(f"[LLM {current_provider.upper()}] 请求超时: {e}, 超时设置: {self.timeout}秒")
                raise LLMNetworkError(f"请求超时（{self.timeout}秒），请检查网络或稍后重试", 504)
            except httpx.RequestError as e:
                logger.error(f"[LLM {current_provider.upper()}] 网络错误: {e}")
                raise LLMNetworkError("网络连接失败", 503)
            except Exception as e:
                logger.error(f"[LLM {current_provider.upper()}] 未知错误: {e}")
                if isinstance(e, LLMError):
                    raise
                raise LLMServerError("服务暂时不可用", 502)

    def _smart_truncate_text(self, text: str, max_length: int) -> str:
        """
        智能截断：在段落边界截断，保留关键信息
        """
        if len(text) <= max_length:
            return text
        
        # 尝试在段落边界截断（以换行符为界）
        target_length = max_length - 100  # 留出100字符的缓冲
        truncated = text[:target_length]
        
        # 查找最后一个换行符（段落边界）
        last_newline = truncated.rfind('\n')
        if last_newline > target_length * 0.8:  # 如果最后一个换行符在80%位置之后，使用它
            truncated = truncated[:last_newline]
        else:
            # 如果找不到合适的换行符，尝试查找句号、分号等句子边界
            sentence_endings = ['。', '；', '. ', '; ', '\n\n']
            for ending in sentence_endings:
                last_ending = truncated.rfind(ending)
                if last_ending > target_length * 0.8:
                    truncated = truncated[:last_ending + len(ending)]
                    break
        
        # 添加截断标记
        truncated += f"\n\n[注意：文本已截断，原始长度{len(text)}字符，当前保留{len(truncated)}字符]"
        
        return truncated
    
    def _sort_work_experiences(self, work_experiences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对工作经历按时间由近及远排序（最新的在前）
        排序规则：
        1. 当前工作（is_current=True）排在最前面
        2. 非当前工作按start_date降序排列（最新的在前）
        3. 如果start_date为空，排到最后
        """
        if not work_experiences:
            return work_experiences
        
        import re
        
        def normalize_date(date_str: str) -> str:
            """标准化日期格式为YYYY-MM，便于比较"""
            if not date_str:
                return "0000-00"  # 空日期返回最小值，排最后
            
            # 处理YYYY-MM-DD格式，取前7位
            if len(date_str) >= 7 and date_str[4] == '-' and date_str[6] == '-':
                return date_str[:7]
            
            # 处理中文日期格式，如"2023年01月"或"2023-01"
            match = re.search(r'(\d{4})[年\-](\d{1,2})', date_str)
            if match:
                year = match.group(1)
                month = match.group(2).zfill(2)
                return f"{year}-{month}"
            
            # 如果已经是YYYY-MM格式，直接返回
            if len(date_str) >= 7 and date_str[4] == '-':
                return date_str[:7]
            
            # 无法解析的日期，返回最小值
            return "0000-00"
        
        def sort_key(exp: Dict[str, Any]) -> tuple:
            is_current = exp.get("is_current", False)
            start_date = exp.get("start_date", "")
            
            # 当前工作排在最前面（优先级0）
            if is_current:
                return (0, "9999-12")  # 使用最大值确保当前工作排在最前
            
            # 非当前工作按start_date降序排列
            normalized_date = normalize_date(start_date)
            
            # 返回(1, normalized_date)，1表示非当前工作
            # 使用负号反转日期实现降序：将日期转换为可比较的格式，然后取负
            # 更简单的方法：返回(1, 反转的日期字符串)，但使用数字更可靠
            # 将YYYY-MM转换为整数：YYYY*100 + MM，然后取负实现降序
            try:
                if normalized_date != "0000-00":
                    year, month = normalized_date.split('-')
                    date_value = int(year) * 100 + int(month)
                    # 使用负号实现降序：日期越大，负值越小，排序越靠前
                    return (1, -date_value)
                else:
                    # 无日期的排最后（返回很大的正数）
                    return (1, 999999)
            except:
                # 解析失败，排最后
                return (1, 999999)
        
        # 排序：当前工作在前（优先级0），然后非当前工作按日期降序（负值越小越靠前）
        sorted_list = sorted(work_experiences, key=sort_key)
        
        return sorted_list
    
    def _format_date(self, date_str: str) -> str:
        """
        格式化日期：将 YYYY-MM 格式转换为 YYYY.MM 格式
        """
        if not date_str:
            return date_str
        # 将 YYYY-MM 格式转换为 YYYY.MM
        return date_str.replace('-', '.')
    
    async def parse_resume_text(self, raw_text: str) -> Dict[str, Any]:
        """
        解析简历文本为结构化数据
        """
        import time
        start_time = time.time()
        text_length = len(raw_text)
        logger.info(f"[解析开始] 文本长度: {text_length} 字符")
        
        # 提高截断限制，确保完整信息能被处理
        # 如果文本已经在前置处理阶段被截断，这里不再截断
        MAX_TEXT_LENGTH = 25000  # 提高到25000字符，与预处理阶段的30000字符配合
        
        if text_length > MAX_TEXT_LENGTH:
            # 检查是否已经在前置处理阶段被截断
            if '[文本已截断' in raw_text or '[注意：文本已截断' in raw_text:
                logger.warning(f"[解析] 文本已在预处理阶段被截断，当前长度: {text_length}字符，直接使用")
            else:
                logger.warning(f"[解析] 文本过长({text_length}字符)，将智能截断至{MAX_TEXT_LENGTH}字符")
                # 智能截断：在段落边界截断（避免循环导入，直接实现）
                raw_text = self._smart_truncate_text(raw_text, MAX_TEXT_LENGTH)
                logger.warning(f"[解析] 截断后长度: {len(raw_text)}字符")
        else:
            logger.info(f"[解析] 文本长度在限制内({text_length}字符)，无需截断")
        
        # 增强解析Prompt：优化后的版本，将Schema和规则移到System Prompt，精简User Prompt
        system_prompt = """你是资深的简历解析专家。目标：在保持事实准确的前提下，输出**稳定、结构清晰的基础解析结果**，用于后续简历生成和填充。

核心能力（必须全部执行）：
1. 段落级结构化提取：识别姓名、公司、职位、时间、职责、成就等字段。
2. 语义理解与隐含信息：在**必要时**从段落推断业务领域、团队规模、技术栈，并记录推断依据。
3. 关联关系挖掘：建立工作经历与项目、技能之间的关系，注明关联理由（如项目属于哪段工作经历）。

输出JSON结构：
{
  "basic_info": {
    "name": "string", "phone": "string", "email": "string", "location": "string",
    "gender": "string|null（性别：男/女）", 
    "birth_date": "string|null（出生日期，格式：YYYY-MM 或 YYYY.MM）",
    "birthday": "string|null（出生日期，兼容字段，与birth_date相同）",
    "hometown": "string|null（籍贯）", 
    "marital_status": "string|null（婚育状态：已婚/未婚/已婚已育等）",
    "family_location": "string|null（家庭所在地）", 
    "current_location": "string|null（现工作地，当前工作的城市或地区）",
    "current_work_location": "string|null（现工作地，兼容字段，与current_location相同）",
    "wechat": "string|null（微信号）",
    "onboard_date": "string|null（入职时间，可以开始工作的时间，格式：YYYY-MM）",
    "other_info": "string|null（其他信息，有利于求职的信息，例如：技能、特长、资质、证书等）"
  },
  "work_experiences": [{
    "company": "string", "position": "string", "start_date": "YYYY-MM",
    "end_date": "YYYY-MM或空", "is_current": true/false, "location": "string",
    "responsibilities": { "raw": ["string"], "optimized": ["string"], "source_paragraphs": ["string"] },
    "achievements": { "raw": ["string"], "optimized": ["string"], "source_paragraphs": ["string"] },
    "skills_used": { "explicit": ["string"], "implicit": ["string"], "application_context": "string" },
    "implicit_info": {
      "team_size": "string", "team_size_basis": "string",
      "business_domain": "string", "domain_basis": "string",
      "tech_stack": ["string"], "tech_stack_basis": "string"
    },
    "related_projects": [{ "project_name": "string", "relation_type": "string", "relation_basis": "string" }],
    "_paragraphs": [{ "text": "string", "type": "string", "importance": "high|medium|low", "extracted_fields": ["string"] }],
    "report_to": "string", "reason_for_leaving": "string"
  }],
  "education": [{
    "school": "string", "major": "string",
    "education_level": "string（学历层次：本科、专科、高中等，不是学位）",
    "degree": "string（学位：学士、硕士、博士等，不是学历）",
    "start_date": "YYYY-MM|null", 
    "graduation_date": "YYYY-MM|null（毕业时间）"
  }],
  "skills": {
    "technical": { "explicit": ["string"], "inferred": ["string"], "application_context": "string" },
    "soft": ["string"], "languages": ["string"]
  },
  "projects": [{
    "name": "string", "description": { "raw": "string", "optimized": "string", "source": "string" },
    "role": "string", "achievements": { "raw": "string", "optimized": "string", "source": "string" },
    "related_work": "string", "related_work_basis": "string"
  }],
  "_metadata": {
    "parsing_version": "2.0"
  }
}

硬性约束：
- 输出严格为 JSON，不含额外文本或代码块标记
- 所有内容必须基于原文，推断信息要写明 inference_basis/source_paragraphs
- raw 与 optimized 必须同时存在（basic_info、education 除外），optimized 只改表达不改事实
- 时间格式统一为 YYYY-MM，当前工作 end_date 为空、is_current=true
- 教育背景应尽量提取 start_date（入学时间）和毕业时间；毕业时间统一使用 graduation_date 字段。
- 如果只有毕业时间，可以只填写 graduation_date，start_date 设为空字符串或null
- **教育背景字段区分（重要）**：
  - education_level（学历层次）：指教育层次，如"研究生"、"本科"、"专科"、"高中"、"中专"等。**注意："硕士"、"博士"不是学历层次，而是学位！**
  - degree（学位）：指学术学位，如"学士"、"硕士"、"博士"等。
  - 区分规则：
    - 如果简历中写"本科"，应填入 education_level="本科"，degree 可为空或推断为"学士"
    - 如果简历中写"硕士"，应填入 education_level="研究生"（如果明确提到研究生阶段）或为空，degree="硕士"。**绝对不要填入 education_level="本科"！**
    - 如果简历中写"博士"，应填入 education_level="研究生"（如果明确提到研究生阶段）或为空，degree="博士"。**绝对不要填入 education_level="本科"或"硕士"！**
    - **关键：绝对不要把"硕士"、"博士"填入 education_level 字段！如果学位是"硕士"或"博士"，education_level 应该是"研究生"或空，而不是"本科"！**
- basic_info 和 education 仅提取原始字段，禁止生成 optimized 或质量评分类字段
- **重要**：basic_info 中的个人信息字段（如 gender性别、birth_date出生日期、birthday出生日期（兼容）、hometown籍贯、marital_status婚育状态、family_location家庭所在地、current_location现工作地、current_work_location现工作地（兼容）、wechat微信号、onboard_date入职时间、other_info其他信息 等）必须直接放在 basic_info 顶层；如果简历中没有，就设为空字符串或null
- 移除空字符串、空数组、空对象；不得编造内容，所有推断都要显式标注
- 必须从简历文本中提取真实信息，如果找不到对应信息，字段设为空字符串或null
"""

        user_prompt = f"""请按照以下流程解析简历文本：

步骤1：基础提取 + 来源记录
- 提取 basic_info、工作/教育/技能等基础字段
- 同步记录每个字段的 source_paragraph 或 inference_basis

步骤2：段落理解与隐含信息
- 识别段落语义类型及重要性，必要时写入 `_paragraphs`
- 从段落推断业务领域、团队规模、技术栈等隐含信息，并注明依据

步骤3：关联与优化
- 关联工作经历与项目、技能，说明 relation_basis
- 在 raw 基础上生成 optimized 描述：职责关注日常贡献，成就突出量化结果

步骤4：一致性检查
- 时间格式统一，移除空值，确保所有生成内容都可追溯

简历文本：
---
{raw_text}
---

直接输出JSON结果："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 估算token数量（粗略：1 token ≈ 4字符）
        estimated_tokens = sum(len(msg["content"]) for msg in messages) // 4
        logger.info(f"[解析进行] 估算token数: {estimated_tokens}, 调用DeepSeek API...")
        
        try:
            api_start = time.time()
            # 增加max_tokens到8192（DeepSeek上限），确保复杂简历的完整JSON响应不被截断
            response = await self.chat_completion(messages, temperature=0.1, max_tokens=8192)
            api_elapsed = time.time() - api_start
            logger.info(f"[解析完成] DeepSeek API耗时: {api_elapsed:.2f}秒")
            
            parsed_data = self._parse_json_response(response)
            total_elapsed = time.time() - start_time
            logger.info(f"[解析总结] 总耗时: {total_elapsed:.2f}秒 (API: {api_elapsed:.2f}秒, 其他: {total_elapsed - api_elapsed:.2f}秒)")
            
            return parsed_data
        except Exception as e:
            total_elapsed = time.time() - start_time
            logger.error(f"[解析失败] 总耗时: {total_elapsed:.2f}秒, 错误: {e}")
            raise

    async def parse_resume_text_v2(self, raw_text: str, user=None, db_session=None) -> Dict[str, Any]:
        """
        使用精简基础模型 schema 解析简历文本。
        与 parse_resume_text 区分开，避免影响已有逻辑。
        
        Args:
            raw_text: 简历文本
            user: 用户对象（可选，用于动态选择LLM配置）
            db_session: 数据库会话（可选，用于读取用户配置）
        """
        import time
        start_time = time.time()
        text_length = len(raw_text)
        logger.info(f"[解析V2开始] 文本长度: {text_length} 字符")

        # 复用与旧版相同的截断策略，避免响应过长
        MAX_TEXT_LENGTH = 25000
        if text_length > MAX_TEXT_LENGTH:
            if '[文本已截断' in raw_text or '[注意：文本已截断' in raw_text:
                logger.warning(f"[解析V2] 文本已在预处理阶段被截断，当前长度: {text_length}字符，直接使用")
            else:
                logger.warning(f"[解析V2] 文本过长({text_length}字符)，将智能截断至{MAX_TEXT_LENGTH}字符")
                raw_text = self._smart_truncate_text(raw_text, MAX_TEXT_LENGTH)
                logger.warning(f"[解析V2] 截断后长度: {len(raw_text)}字符")
        else:
            logger.info(f"[解析V2] 文本长度在限制内({text_length}字符)，无需截断")

        system_prompt = """你是资深的简历解析专家。目标：在保持事实准确的前提下，输出稳定、结构清晰的基础解析结果，用于后续简历生成和填充。

【一、输出 JSON 结构（严格按照此结构，不要增加多余层级）】
{
  "basic_info": {
    "name": "string",
    "phone": "string",
    "email": "string",
    "location": "string",
    "gender": "string|null",
    "birth_date": "string|null",
    "birthday": "string|null（兼容字段）",
    "hometown": "string|null",
    "marital_status": "string|null",
    "family_location": "string|null",
    "current_location": "string|null",
    "current_work_location": "string|null（兼容字段）",
    "wechat": "string|null",
    "onboard_date": "string|null",
    "other_info": "string|null"
  },
  "work_experiences": [{
    "company": "string",                    // 公司名称（完整公司名，如"中国建筑第八工程局有限公司"）
    "position": "string",                   // 职位名称（如果包含部门信息，如"金融业务部 业务经理"，可以保留完整信息，或只提取"业务经理"）
    "location": "string|null",              // 工作地点
    "start_date": "string",                 // 开始时间，格式：YYYY-MM（如"2019-04"）
    "end_date": "string|null",              // 结束时间，格式：YYYY-MM（如"2022-06"）；如在职则为null
    "is_current": true/false,               // 是否当前工作
    "report_to": "string|null",             // 汇报对象
    "team_size": "string|null",            // 团队规模
    "responsibilities": ["string"],        // 工作职责数组（每条职责作为一个元素，必须完整提取，不要因为内容长而忽略）
    "achievements": ["string"],            // 工作业绩数组（每条业绩作为一个元素）
    "reason_for_leaving": "string|null"     // 离职原因
  }],
  "education": [{
    "school": "string",
    "major": "string",
    "education_level": "string",
    "degree": "string|null",
    "start_date": "string|null",
    "graduation_date": "string|null"
  }],
  "skills": {
    "technical": ["string"],
    "soft": ["string"],
    "languages": ["string"]
  },
  "projects": [{
    "name": "string",
    "role": "string|null",                // 项目角色（如"KAM"、"项目经理"、"技术负责人"等），不是职责描述
    "start_date": "string|null",          // 项目开始时间，YYYY-MM
    "end_date": "string|null",            // 项目结束时间，YYYY-MM；如进行中可为空
    "description": "string",              // 项目完整描述（包括背景、目的、职责、业绩等）
    "responsibilities": ["string"],       // 项目职责（在项目中承担的具体任务），从描述中提取
    "achievements": ["string"],           // 项目业绩（项目成果、亮点），从描述中提取
    "related_work": "string|null"
  }],
  "_metadata": {
    "parsing_version": "2.0"
  }
}

【二、拆分与合并规则】
1. **工作经历识别（重要）**：
   - 必须识别所有工作经历，无论时间格式如何（如 `2019/4—2022/6`、`2019.4-2022.6` 等）
   - 如果职位包含部门信息（如"金融业务部 业务经理"），可以保留完整信息，或只提取职位部分（"业务经理"）
   - 如果工作经历包含多个职责模块（如"项目投融资"、"金融产品"、"其他工作"），必须将所有职责完整提取到 responsibilities 数组中
   - **绝对不要因为时间格式不标准、职位包含部门信息、或职责内容较长而忽略整段工作经历**

2. 职责（responsibilities）和业绩（achievements）：
   - 每个数组元素必须是一条完整的职责/业绩描述，可以单独作为一个 bullet 展示。
   - 禁止按逗号、顿号过度拆分一句话；如果原文是一句多分句的长句，也应作为一条完整描述保留。
   - 可以参考原文中的项目符号或明显的段落分隔来决定拆分边界。
   - **重要：必须完整提取所有职责内容，不要因为内容长而截断或忽略**
   - **重要：如果工作职责中包含派遣经历（如"派遣到XX公司"、"从XX派遣到XX"等），必须保留时间信息：**
     - 格式：`"【YYYY.MM-YYYY.MM】派遣到XX公司/单位，具体工作内容..."`
     - 例如：`"【2019.09-2019.12】派遣到钜芯集成电路测试SMIC新0.13 BCD工艺，完成Motor Driver和Test Chip十余个版本..."`
     - 如果只有开始时间，格式：`"【YYYY.MM-至今】派遣到XX公司/单位，具体工作内容..."`
     - 如果时间信息在原文中，必须保留；如果原文没有明确时间，可以根据上下文推断并标注
     - **绝对不要删除或忽略派遣经历中的时间信息**

2. 项目描述（projects.description）：
   - 使用一段长文本，保持原始语义流畅，可以合并多行/多句为一个完整段落。
   - 不要拆成数组结构；如有多段，可用换行或适度的分号、句号自然分隔。
   - **重要：如果项目描述中包含了"项目职责"、"项目业绩"等结构化内容，必须：**
     - 将"项目职责"部分提取出来，填充到 responsibilities 数组（每条职责作为一个元素）
     - 将"项目业绩"部分提取出来，填充到 achievements 数组（每条业绩作为一个元素）
     - **从 description 中移除已提取的职责和业绩内容，description 只保留背景、目的、项目概述等非结构化描述**
     - role 字段填写项目角色（如"项目经理"、"KAM"、"技术负责人"等），**绝对不要将 role 填充到 responsibilities 中**
     - 如果描述中没有明确区分职责和业绩，description 保留原样，responsibilities 和 achievements 可为空

【三、时间与缺失值约束】
1. **时间格式识别与转换（重要）**：
   - 输入时间可能以多种格式出现，必须全部识别并转换为标准格式 YYYY-MM（例如："2019-03"）
   - 常见输入格式示例：
     * `2019/4—2022/6` → start_date: "2019-04", end_date: "2022-06"
     * `2019.4-2022.6` → start_date: "2019-04", end_date: "2022-06"
     * `2019年4月-2022年6月` → start_date: "2019-04", end_date: "2022-06"
     * `2019/04—2022/06` → start_date: "2019-04", end_date: "2022-06"
     * `2019-04 至 2022-06` → start_date: "2019-04", end_date: "2022-06"
   - 如果月份是单数字（如"4月"），必须补零为"04"（即"2019-04"）
   - 如果只有年份（如"2019"），统一写成 "2019-01" 并保持一致
   - **关键：无论输入格式如何，都必须识别并提取时间信息，不得因为格式不标准而忽略整段工作经历**
2. 当前在职的工作：is_current=true，end_date 设为 null 或空字符串。
3. 教育经历：能提取到入学时间时填写 start_date，否则设为 null；毕业时间统一使用 graduation_date。
4. 找不到对应信息时，字段设为 null 或空字符串，不得编造。

【三-1、教育背景字段区分（重要）】
1. education_level（学历层次）：指教育层次，如"研究生"、"本科"、"专科"、"高中"、"中专"等。**注意："硕士"、"博士"不是学历层次，而是学位！**
2. degree（学位）：指学术学位，如"学士"、"硕士"、"博士"等。
3. 区分规则：
   - 如果简历中写"本科"，应填入 education_level="本科"，degree 可为空或推断为"学士"
   - 如果简历中写"硕士"，应填入 education_level="研究生"（如果明确提到研究生阶段）或为空，degree="硕士"。**绝对不要填入 education_level="本科"！**
   - 如果简历中写"博士"，应填入 education_level="研究生"（如果明确提到研究生阶段）或为空，degree="博士"。**绝对不要填入 education_level="本科"或"硕士"！**
   - **关键：绝对不要把"硕士"、"博士"填入 education_level 字段！如果学位是"硕士"或"博士"，education_level 应该是"研究生"或空，而不是"本科"！**

【四、basic_info 的特殊要求】
1. basic_info 中的个人信息字段（gender、birth_date、birthday（兼容）、hometown、marital_status、family_location、current_location、current_work_location（兼容）、wechat、onboard_date、other_info 等）
   必须直接放在 basic_info 顶层，禁止放在“其他联系字段”等嵌套对象中。

【五、输出格式硬性要求】
1. 输出必须是严格合法的 JSON，不包含任何注释、解释性文字或代码块标记。
2. 键名必须使用双引号，字符串值必须使用双引号。
3. 不要输出多余字段（例如 professional_summary、quality_score、raw/optimized/source_paragraphs 等都不要输出）。
"""

        user_prompt = f"""请根据上面的【输出 JSON 结构】和约束，对下面的简历文本进行解析，只输出一个 JSON 对象：

简历文本：
---
{raw_text}
---
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        estimated_tokens = sum(len(msg["content"]) for msg in messages) // 4
        logger.info(f"[解析V2进行] 估算token数: {estimated_tokens}, 调用DeepSeek API...")

        try:
            # 使用上下文中的用户信息（如果方法参数中没有传入）
            effective_user = user or self._current_user
            effective_db_session = db_session or self._current_db_session
            api_start = time.time()
            # 增加max_tokens到8192，确保复杂简历的完整JSON响应不被截断
            response = await self.chat_completion(
                messages, 
                temperature=0.1, 
                max_tokens=8192,
                user=effective_user,
                db_session=effective_db_session
            )
            api_elapsed = time.time() - api_start
            logger.info(f"[解析V2完成] LLM API耗时: {api_elapsed:.2f}秒")

            parsed_data = self._parse_json_response(response)
            total_elapsed = time.time() - start_time
            logger.info(f"[解析V2总结] 总耗时: {total_elapsed:.2f}秒 (API: {api_elapsed:.2f}秒)")
            return parsed_data
        except Exception as e:
            total_elapsed = time.time() - start_time
            logger.error(f"[解析V2失败] 总耗时: {total_elapsed:.2f}秒, 错误: {e}")
            raise

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析API返回的JSON响应
        增强错误处理和JSON修复能力
        """
        try:
            # 清理响应文本
            cleaned_response = response.strip()
            
            # 移除可能的代码块标记
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            
            cleaned_response = cleaned_response.strip()
            
            # 尝试解析JSON
            try:
                parsed_data = json.loads(cleaned_response)
                return parsed_data
            except json.JSONDecodeError as json_err:
                # 如果JSON解析失败，尝试修复常见的格式问题
                logger.warning(f"JSON解析失败，尝试修复: {json_err}")
                
                # 修复策略1: 移除JSON注释（// 和 # 注释）
                fixed_response = self._remove_json_comments(cleaned_response)
                
                # 修复策略2: 修复单引号字符串（转换为双引号）
                fixed_response = self._fix_single_quotes(fixed_response)
                
                # 修复策略3: 修复尾随逗号
                fixed_response = self._fix_trailing_commas(fixed_response)
                
                # 修复策略4: 修复未转义的引号（在字符串值中）
                fixed_response = self._fix_unescaped_quotes(fixed_response)
                
                # 尝试用修复后的JSON解析
                try:
                    parsed_data = json.loads(fixed_response)
                    logger.info("JSON修复成功（通过注释/逗号/引号修复）")
                    return parsed_data
                except json.JSONDecodeError:
                    pass
                
                # 修复策略5: 处理截断问题（特别是未闭合的字符串）
                if "Unterminated string" in str(json_err) or "Expecting" in str(json_err):
                    # 尝试修复未闭合的字符串
                    fixed_truncated = self._fix_truncated_json(fixed_response, json_err)
                    if fixed_truncated:
                        try:
                            parsed_data = json.loads(fixed_truncated)
                            logger.warning(f"JSON修复成功，修复了截断问题（保留{len(fixed_truncated)}/{len(cleaned_response)}字符）")
                            # 标记为可能不完整（因为被截断和修复）
                            if "_metadata" not in parsed_data:
                                parsed_data["_metadata"] = {}
                            parsed_data["_metadata"]["json_truncated"] = True
                            parsed_data["_metadata"]["truncation_info"] = {
                                "original_length": len(cleaned_response),
                                "truncated_length": len(fixed_truncated),
                                "preserved_ratio": len(fixed_truncated) / len(cleaned_response) if cleaned_response else 0
                            }
                            return parsed_data
                        except json.JSONDecodeError:
                            pass
                    
                    # 如果修复未闭合字符串失败，尝试找到最后一个完整的JSON对象
                    last_brace = fixed_response.rfind('}')
                    last_bracket = fixed_response.rfind(']')
                    last_complete = max(last_brace, last_bracket)
                    
                    if last_complete > len(fixed_response) * 0.8:  # 如果至少保留了80%的内容
                        # 尝试补全JSON结构
                        truncated = fixed_response[:last_complete + 1]
                        
                        # 检查是否需要补全结构
                        open_braces = truncated.count('{')
                        close_braces = truncated.count('}')
                        open_brackets = truncated.count('[')
                        close_brackets = truncated.count(']')
                        
                        # 补全缺失的闭合括号
                        while open_braces > close_braces:
                            truncated += '}'
                            close_braces += 1
                        while open_brackets > close_brackets:
                            truncated += ']'
                            close_brackets += 1
                        
                        try:
                            parsed_data = json.loads(truncated)
                            logger.warning(f"JSON修复成功，使用了截断后的响应（保留{len(truncated)}/{len(cleaned_response)}字符）")
                            # 标记为可能不完整（因为被截断和修复）
                            if "_metadata" not in parsed_data:
                                parsed_data["_metadata"] = {}
                            parsed_data["_metadata"]["json_truncated"] = True
                            parsed_data["_metadata"]["truncation_info"] = {
                                "original_length": len(cleaned_response),
                                "truncated_length": len(truncated),
                                "preserved_ratio": len(truncated) / len(cleaned_response) if cleaned_response else 0
                            }
                            return parsed_data
                        except json.JSONDecodeError:
                            pass
                
                # 如果修复失败，记录详细错误并抛出
                error_pos = getattr(json_err, 'pos', None)
                if error_pos:
                    start = max(0, error_pos - 100)
                    end = min(len(cleaned_response), error_pos + 100)
                    logger.error(f"JSON解析失败，错误位置: {error_pos}，上下文: ...{cleaned_response[start:end]}...")
                logger.error(f"JSON解析失败，原始响应长度: {len(cleaned_response)}字符")
                logger.error(f"JSON解析失败，原始响应前500字符: {cleaned_response[:500]}...")
                logger.error(f"JSON解析失败，原始响应后500字符: ...{cleaned_response[-500:]}")
                raise DeepSeekParseError(f"无法解析API响应: {json_err}。响应可能被截断，请检查max_tokens设置。", 502)
            
        except DeepSeekParseError:
            raise
        except Exception as e:
            logger.error(f"JSON解析异常: {e}")
            raise DeepSeekParseError(f"无法解析API响应: {e}", 502)
    
    def _remove_json_comments(self, text: str) -> str:
        """移除JSON中的注释（// 和 # 注释）"""
        lines = text.split('\n')
        result = []
        in_string = False
        escape_next = False
        
        for line in lines:
            new_line = []
            i = 0
            while i < len(line):
                char = line[i]
                
                if escape_next:
                    new_line.append(char)
                    escape_next = False
                    i += 1
                    continue
                
                if char == '\\':
                    escape_next = True
                    new_line.append(char)
                    i += 1
                    continue
                
                if char == '"':
                    in_string = not in_string
                    new_line.append(char)
                    i += 1
                    continue
                
                if not in_string:
                    # 在字符串外，检查注释
                    if i < len(line) - 1 and line[i:i+2] == '//':
                        # 单行注释，跳过剩余部分
                        break
                    if char == '#':
                        # # 注释，跳过剩余部分
                        break
                
                new_line.append(char)
                i += 1
            
            result.append(''.join(new_line))
        
        return '\n'.join(result)
    
    def _fix_trailing_commas(self, text: str) -> str:
        """修复JSON中的尾随逗号"""
        # 匹配尾随逗号：在 } 或 ] 之前的逗号
        # 但要注意不要匹配字符串内的逗号
        # 使用逐字符处理，确保准确性
        result = []
        i = 0
        in_string = False
        escape_next = False
        
        while i < len(text):
            char = text[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                result.append(char)
                i += 1
                continue
            
            if char == '"':
                in_string = not in_string
                result.append(char)
                i += 1
                continue
            
            if not in_string:
                # 检查尾随逗号：,} 或 ,]
                if char == ',' and i + 1 < len(text):
                    next_char = text[i + 1]
                    if next_char in '}]':
                        # 跳过这个逗号
                        i += 1
                        continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    def _find_last_complete_structure(self, text: str, error_pos: int) -> Optional[str]:
        """
        使用栈从错误位置向前查找最后一个完整的JSON结构
        这是处理复杂嵌套截断的最可靠方法
        """
        # 从错误位置向前遍历，使用栈跟踪括号匹配
        stack = []  # 栈中存储 (char, position) 对
        in_string = False
        escape_next = False
        last_complete_pos = -1
        
        # 从错误位置向前遍历（最多向前查找3000字符）
        start_pos = max(0, error_pos - 3000)
        
        for i in range(error_pos - 1, start_pos - 1, -1):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if in_string:
                continue  # 在字符串内，忽略所有其他字符
            
            # 处理括号匹配
            if char == '}' or char == ']':
                stack.append((char, i))
            elif char == '{' or char == '[':
                if stack:
                    last_char, last_pos = stack[-1]
                    # 检查是否匹配
                    if (char == '{' and last_char == '}') or (char == '[' and last_char == ']'):
                        stack.pop()
                        # 如果栈为空，说明找到了一个完整的结构
                        if not stack:
                            last_complete_pos = last_pos
                    else:
                        # 不匹配，说明结构有问题，停止
                        break
                else:
                    # 栈为空但遇到了开括号，说明结构不完整
                    break
        
        # 如果找到了完整的结构，截断到那里
        if last_complete_pos > start_pos:
            truncated = text[:last_complete_pos + 1].rstrip()
            # 移除尾随逗号
            truncated = truncated.rstrip(', \n\r\t')
            
            # 补全可能缺失的闭合括号
            open_braces = truncated.count('{')
            close_braces = truncated.count('}')
            open_brackets = truncated.count('[')
            close_brackets = truncated.count(']')
            
            while open_braces > close_braces:
                truncated += '}'
                close_braces += 1
            while open_brackets > close_brackets:
                truncated += ']'
                close_brackets += 1
            
            # 验证截断后的JSON是否至少保留了50%的内容
            if len(truncated) >= len(text) * 0.5:
                return truncated
        
        return None
    
    def _fix_truncated_json(self, text: str, json_err: json.JSONDecodeError) -> str:
        """
        修复被截断的JSON，特别是未闭合的字符串、数组或对象
        增强版：使用栈来跟踪括号匹配，更好地处理复杂嵌套结构
        """
        error_pos = getattr(json_err, 'pos', None)
        if not error_pos or error_pos >= len(text):
            return None
        
        # 特殊处理：如果错误是"Unterminated string"，说明字符串在中间被截断
        # 需要找到最后一个完整的字符串属性，移除不完整的属性
        if "Unterminated string" in str(json_err):
            # 从错误位置向前查找，找到最后一个完整的字符串属性 "key": "value"
            # 搜索范围：最多向前查找3000字符
            search_start = max(0, error_pos - 3000)
            search_text = text[search_start:error_pos]
            
            # 查找最后一个完整的属性模式："key": "value"（value必须完整闭合）
            # 使用更严格的模式，确保value是完整的字符串
            attr_pattern = r'"([^"]+)"\s*:\s*"([^"]*)"\s*(?:,|\n|\r|})'
            matches = list(re.finditer(attr_pattern, search_text))
            
            if matches:
                # 找到最后一个完整的属性
                last_match = matches[-1]
                # 找到这个属性在原始文本中的结束位置（包括闭合引号和可能的逗号）
                match_end_in_search = last_match.end()
                element_end = search_start + match_end_in_search
                
                # 截断到属性结束位置
                truncated = text[:element_end].rstrip()
                # 移除尾随的逗号（如果这是最后一个属性）
                truncated = truncated.rstrip(', \n\r\t')
                
                # 补全JSON结构
                open_braces = truncated.count('{')
                close_braces = truncated.count('}')
                open_brackets = truncated.count('[')
                close_brackets = truncated.count(']')
                
                while open_brackets > close_brackets:
                    truncated += ']'
                    close_brackets += 1
                while open_braces > close_braces:
                    truncated += '}'
                    close_braces += 1
                
                # 验证截断后的JSON是否至少保留了50%的内容
                if len(truncated) >= len(text) * 0.5:
                    return truncated
        
        # 方法1：使用栈从错误位置向前查找最后一个完整的结构
        truncated = self._find_last_complete_structure(text, error_pos)
        if truncated:
            return truncated
        
        # 方法2：如果方法1失败，使用原有的正则匹配方法
        # 从错误位置向前查找，找到最后一个完整的值
        # 向前搜索范围（最多2000字符，以处理更复杂的情况）
        search_start = max(0, error_pos - 2000)
        search_text = text[search_start:error_pos]
        
        # 策略1: 检测是否在对象或数组内部
        # 计算括号匹配情况
        open_braces_in_search = search_text.count('{')
        close_braces_in_search = search_text.count('}')
        open_brackets_in_search = search_text.count('[')
        close_brackets_in_search = search_text.count(']')
        
        # 如果对象未闭合（open_braces > close_braces），尝试找到最后一个完整的属性
        if open_braces_in_search > close_braces_in_search:
            # 查找最后一个完整的对象属性 "key": "value"
            # 优先查找字符串属性值，因为这是最常见的截断情况
            
            # 方法1: 查找最后一个完整的字符串属性值 "key": "value"
            # 匹配模式：, "key": "value" 或 { "key": "value" 或 \n "key": "value"
            # 注意：需要匹配到完整的 "value"（包括闭合引号）
            attr_string_pattern = r'"([^"]+)"\s*:\s*"([^"]*)"\s*(?:,|\n|\r|})'
            matches = list(re.finditer(attr_string_pattern, search_text))
            
            if matches:
                # 找到最后一个匹配的属性
                last_match = matches[-1]
                # 找到这个属性在原始文本中的结束位置（包括闭合引号和可能的逗号）
                match_end_in_search = last_match.end()
                element_end = search_start + match_end_in_search
                
                # 截断到属性结束位置
                truncated = text[:element_end].rstrip()
                # 移除尾随的逗号（如果这是最后一个属性）
                truncated = truncated.rstrip(', \n\r\t')
                truncated = truncated.rstrip()
            else:
                # 方法2: 如果没找到字符串属性，尝试找到最后一个完整的 } 或 ,
                # 这表示最后一个完整的属性已经结束
                last_brace = search_text.rfind('}')
                last_comma = search_text.rfind(',')
                last_complete = max(last_brace, last_comma)
                
                if last_complete != -1:
                    if last_complete == last_brace:
                        # 如果最后是 }，截断到它之后
                        truncated = text[:search_start + last_complete + 1].rstrip()
                    else:
                        # 如果最后是 ,，截断到它之前（移除这个逗号，因为后面没有属性了）
                        truncated = text[:search_start + last_comma].rstrip()
                        truncated = truncated.rstrip()
                else:
                    truncated = None
        
        # 如果数组未闭合（open_brackets > close_brackets），尝试找到最后一个完整的数组元素
        elif open_brackets_in_search > close_brackets_in_search:
            # 查找最后一个完整的数组元素（字符串、数字、布尔、null）
            # 注意：需要处理多行格式和带逗号的情况
            
            # 策略：从错误位置向前查找，找到最后一个完整的引号对（字符串值）
            # 或者最后一个完整的非字符串值
            
            # 方法1: 查找最后一个完整的字符串元素 "value"
            # 使用更宽松的模式，匹配可能带逗号的情况
            # 模式：匹配 "value" 后面可能跟着逗号、换行或结束
            # 注意：这个模式会匹配到逗号，所以我们需要在截断后移除逗号
            string_pattern = r'"([^"]*)"\s*(?:,|\n|\r|$)'
            matches = list(re.finditer(string_pattern, search_text))
            
            if matches:
                # 找到最后一个匹配的字符串元素
                last_match = matches[-1]
                # 找到这个元素在原始文本中的结束位置
                # last_match.end() 包含了引号和可能的逗号
                match_end_in_search = last_match.end()
                element_end = search_start + match_end_in_search
                
                # 截断到元素结束位置
                truncated = text[:element_end].rstrip()
                # 移除尾随的逗号（因为这是最后一个元素，不应该有逗号）
                # 注意：正则可能匹配到逗号，所以需要移除
                truncated = truncated.rstrip(', \n\r\t')
                truncated = truncated.rstrip()
            else:
                # 方法2: 如果没有找到字符串元素，尝试查找最后一个数字、布尔或null
                # 模式：匹配数字、true、false、null，后面可能跟着逗号
                value_pattern = r'(-?\d+(?:\.\d+)?|true|false|null)\s*(?:,|\n|\r|$)'
                matches = list(re.finditer(value_pattern, search_text))
                
                if matches:
                    last_match = matches[-1]
                    match_end_in_search = last_match.end()
                    element_end = search_start + match_end_in_search
                    truncated = text[:element_end].rstrip()
                    # 移除尾随的逗号和空白（因为这是最后一个元素）
                    truncated = truncated.rstrip(', \n\r\t')
                    truncated = truncated.rstrip()
                else:
                    # 方法3: 如果都没找到，尝试找到最后一个 [ 的位置
                    # 然后查找它后面的第一个完整元素
                    last_bracket = search_text.rfind('[')
                    if last_bracket != -1:
                        # 在 [ 之后查找第一个元素
                        after_bracket = search_text[last_bracket + 1:]
                        # 查找第一个完整的字符串或值
                        first_elem_pattern = r'["\']([^"\']*)["\']|(-?\d+(?:\.\d+)?|true|false|null)'
                        first_match = re.search(first_elem_pattern, after_bracket)
                        if first_match:
                            # 找到第一个元素，截断到它之后
                            elem_end_in_after = first_match.end()
                            truncated = text[:search_start + last_bracket + 1 + elem_end_in_after].rstrip()
                            # 移除尾随的逗号和空白
                            truncated = truncated.rstrip(', \n\r\t')
                            truncated = truncated.rstrip()
                        else:
                            # 没有找到任何元素，截断到 [ 之后（空数组）
                            truncated = text[:search_start + last_bracket + 1].rstrip()
                    else:
                        truncated = None
            
            # 如果上面的方法都没有找到有效的截断点，使用备用方法：
            # 直接从错误位置向前查找最后一个完整的引号对
            if not truncated:
                # 从错误位置向前查找最后一个完整的 "value" 模式
                # 使用更简单的模式：找到最后一个 "..." 对
                last_quote_start = search_text.rfind('"')
                if last_quote_start != -1:
                    # 向前查找匹配的开始引号
                    # 简单策略：从 last_quote_start 向前查找，找到最近的未转义的开始引号
                    quote_pos = last_quote_start
                    found_start = False
                    i = quote_pos - 1
                    while i >= 0:
                        if search_text[i] == '"' and (i == 0 or search_text[i-1] != '\\'):
                            # 找到匹配的开始引号
                            found_start = True
                            # 截断到结束引号之后
                            truncated = text[:search_start + quote_pos + 1].rstrip()
                            # 移除尾随逗号
                            if truncated.endswith(','):
                                truncated = truncated[:-1].rstrip()
                            break
                        i -= 1
        else:
            # 策略2: 不在数组内部，查找最后一个完整的属性
            # 查找模式：, "key": 或 ,\n"key":
            pattern = r',\s*["\'](\w+)["\']\s*:'
            matches = list(re.finditer(pattern, search_text))
            
            if matches:
                # 找到最后一个匹配的属性开始位置
                last_match = matches[-1]
                # 找到这个属性之前的位置（逗号之前）
                cut_pos = search_start + last_match.start()
                truncated = text[:cut_pos].rstrip()
                
                # 移除末尾可能的尾随逗号
                if truncated.endswith(','):
                    truncated = truncated[:-1].rstrip()
            else:
                # 策略3: 如果没找到属性分隔符，尝试找到最后一个完整的对象或数组结束
                # 查找最后一个 } 或 ]
                last_brace = search_text.rfind('}')
                last_bracket = search_text.rfind(']')
                last_complete = max(last_brace, last_bracket)
                
                if last_complete == -1:
                    return None
                
                # 截断到最后一个完整对象/数组之后
                cut_pos = search_start + last_complete + 1
                truncated = text[:cut_pos].rstrip()
                
                # 移除末尾可能的尾随逗号
                if truncated.endswith(','):
                    truncated = truncated[:-1].rstrip()
        
        if not truncated:
            return None
        
        # 移除末尾可能的尾随逗号（再次检查，确保干净）
        truncated = truncated.rstrip()
        while truncated.endswith(','):
            truncated = truncated[:-1].rstrip()
        
        # 补全JSON结构
        open_braces = truncated.count('{')
        close_braces = truncated.count('}')
        open_brackets = truncated.count('[')
        close_brackets = truncated.count(']')
        
        # 补全缺失的闭合括号（先闭合数组，再闭合对象）
        while open_brackets > close_brackets:
            truncated += ']'
            close_brackets += 1
        while open_braces > close_braces:
            truncated += '}'
            close_braces += 1
        
        # 验证截断后的JSON是否至少保留了50%的内容（降低阈值，因为可能截断较多）
        if len(truncated) < len(text) * 0.5:
            return None
        
        return truncated
    
    def _find_value_end(self, text: str, start: int, max_pos: int) -> int:
        """
        找到JSON值的结束位置（下一个逗号、} 或 ]，在字符串外）
        """
        i = start
        in_string = False
        escape_next = False
        depth_braces = 0
        depth_brackets = 0
        
        while i < min(len(text), max_pos):
            char = text[i]
            
            if escape_next:
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                i += 1
                continue
            
            if char == '"':
                in_string = not in_string
                i += 1
                continue
            
            if not in_string:
                if char == '{':
                    depth_braces += 1
                elif char == '}':
                    depth_braces -= 1
                    if depth_braces < 0:
                        return i  # 对象结束
                elif char == '[':
                    depth_brackets += 1
                elif char == ']':
                    depth_brackets -= 1
                    if depth_brackets < 0:
                        return i  # 数组结束
                elif char in ',}' and depth_braces == 0 and depth_brackets == 0:
                    return i  # 属性分隔符或对象结束
        
        return -1
    
    def _fix_single_quotes(self, text: str) -> str:
        """
        修复单引号字符串，转换为双引号
        处理模式：'value' -> "value"
        特别注意：如果单引号字符串内包含双引号，需要先转义这些双引号
        例如：'业绩描述"项目"过于简略' -> "业绩描述\"项目\"过于简略"
        """
        result = []
        i = 0
        in_single_quote = False
        in_double_quote = False
        escape_next = False
        
        while i < len(text):
            char = text[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                result.append(char)
                i += 1
                continue
            
            if char == "'" and not in_double_quote:
                # 检查是否是字符串的开始或结束
                if not in_single_quote:
                    # 检查前面是否有 : 或 , 或 { 或 [，说明是字符串开始
                    if i > 0:
                        # 跳过空白字符
                        j = i - 1
                        while j >= 0 and text[j].isspace():
                            j -= 1
                        if j >= 0:
                            prev_char = text[j]
                            if prev_char in ':,\n\r\t {[':
                                in_single_quote = True
                                result.append('"')  # 转换为双引号
                                i += 1
                                continue
                    else:
                        # 开头就是单引号，可能是字符串开始
                        in_single_quote = True
                        result.append('"')
                        i += 1
                        continue
                else:
                    # 在单引号字符串内，检查是否是字符串结束
                    if i + 1 < len(text):
                        # 跳过空白字符
                        j = i + 1
                        while j < len(text) and text[j].isspace():
                            j += 1
                        if j < len(text):
                            next_char = text[j]
                            # 如果下一个非空白字符是 : 或 , 或 } 或 ]，说明是字符串结束
                            if next_char in ':,\n\r }]':
                                in_single_quote = False
                                result.append('"')  # 转换为双引号
                                i += 1
                                continue
                        # 否则是字符串内的单引号，需要转义
                        result.append("\\'")
                        i += 1
                        continue
                    else:
                        # 字符串结束（在文本末尾）
                        in_single_quote = False
                        result.append('"')
                        i += 1
                        continue
            
            # 在单引号字符串内，如果遇到双引号，需要转义（因为我们要把外层单引号转换为双引号）
            if char == '"' and in_single_quote:
                result.append('\\"')
                i += 1
                continue
            
            if char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            
            result.append(char)
            i += 1
        
        return ''.join(result)
    
    def _fix_unescaped_quotes(self, text: str) -> str:
        """
        修复JSON字符串值中未转义的引号
        增强版：更准确地判断字符串边界，处理各种情况
        """
        result = []
        i = 0
        in_string = False
        escape_next = False
        string_start = -1
        
        while i < len(text):
            char = text[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                escape_next = True
                result.append(char)
                i += 1
                continue
            
            if char == '"':
                if in_string:
                    # 在字符串内遇到引号，需要判断是否是字符串结束
                    # 向前查找，看是否在属性值的位置
                    # 检查后面的字符
                    if i + 1 < len(text):
                        next_char = text[i + 1]
                        # 如果下一个字符是 : 或 , 或 } 或 ] 或换行，说明是字符串结束
                        if next_char in ':,\n\r\t }]':
                            in_string = False
                            result.append(char)
                            i += 1
                            continue
                        # 如果下一个字符是空白，继续检查
                        elif next_char.isspace():
                            # 检查空白后的字符
                            j = i + 1
                            while j < len(text) and text[j].isspace():
                                j += 1
                            if j < len(text):
                                next_non_space = text[j]
                                if next_non_space in ':,\n\r }]':
                                    in_string = False
                                    result.append(char)
                                    i += 1
                                    continue
                        # 否则是字符串内的未转义引号，需要转义
                        result.append('\\"')
                        i += 1
                        continue
                    else:
                        # 字符串结束（在文本末尾）
                        in_string = False
                        result.append(char)
                        i += 1
                        continue
                else:
                    # 字符串开始
                    # 检查前面是否有 : 或 , 或 { 或 [，说明是属性值或数组元素
                    if i > 0:
                        prev_char = text[i - 1]
                        # 跳过空白字符
                        if prev_char.isspace():
                            j = i - 1
                            while j >= 0 and text[j].isspace():
                                j -= 1
                            if j >= 0:
                                prev_char = text[j]
                        
                        if prev_char in ':,\n\r\t {[':
                            in_string = True
                            string_start = i
                            result.append(char)
                            i += 1
                            continue
                    else:
                        # 开头就是引号，可能是JSON对象的开始
                        in_string = True
                        string_start = i
                        result.append(char)
                        i += 1
                        continue
            
            result.append(char)
            i += 1
        
        return ''.join(result)

    async def enhance_resume_data(self, base_data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        """
        基于工具提取的基础数据，使用LLM进行增强优化。
        当工作经历较多时，自动切分为多个小批次并发增强，缩短单次提示长度。
        """
        work_count = len(base_data.get("work_experiences", []))
        if work_count > self.work_chunk_threshold:
            return await self._enhance_resume_in_chunks(base_data, raw_text)
        return await self._run_full_enhancement(base_data, raw_text)

    async def _run_full_enhancement(self, base_data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        import time
        import json
        start_time = time.time()

        logger.info(
            f"[LLM增强] 全量模式，基础字段: {len(base_data.get('basic_info', {}))}, "
            f"工作经历: {len(base_data.get('work_experiences', []))}条"
        )

        system_prompt = """你是资深的简历内容优化专家。你的任务是基于已提取的基础结构化数据，进行内容增强和优化。

核心任务：
1. **补全和验证基础数据**：检查工具提取的基础字段是否完整、准确，从原始文本中补全缺失字段。
2. **内容优化**：为职责、成就、描述等字段生成优化版本（raw + optimized）。
3. **隐含信息提取**：从文本中推断团队规模、业务领域、技术栈等隐含信息。
4. **关联关系挖掘**：建立工作经历与项目、技能之间的关联关系。

重要约束：
- basic_info 和 education 只需精确提取，不需要优化或推断。
- 所有增强内容必须基于原始文本，不能编造。
- 必须提供来源标注（source_paragraphs、inference_basis等）。
"""

        base_data_json = json.dumps(base_data, ensure_ascii=False, indent=2)

        MAX_CONTEXT_LENGTH = 15000
        if len(raw_text) > MAX_CONTEXT_LENGTH:
            raw_text = self._smart_truncate_text(raw_text, MAX_CONTEXT_LENGTH)

        schema_definition = """
输出 JSON，包含以下增强字段结构（仅对基础模型做内容增强，不做职业摘要和质量评分）：

{
  "work_experiences": [{
    "company": "string",
    "position": "string",
    "start_date": "YYYY-MM",
    "end_date": "YYYY-MM或空",
    "is_current": true/false,
    "location": "string?",
    "responsibilities": { "raw": ["string"], "optimized": ["string"], "source_paragraphs": ["string"] },
    "achievements": { "raw": ["string"], "optimized": ["string"], "source_paragraphs": ["string"] },
    "skills_used": { "explicit": ["string"], "implicit": ["string"], "application_context": "string?" },
    "implicit_info": {
      "team_size": "string?",
      "team_size_basis": "string?",
      "business_domain": "string?",
      "domain_basis": "string?",
      "tech_stack": ["string"],
      "tech_stack_basis": "string?"
    },
    "related_projects": [{ "project_name": "string", "relation_type": "string", "relation_basis": "string" }],
    "report_to": "string?",
    "reason_for_leaving": "string?"
  }],
  "education": [{ 
    "school": "string", 
    "major": "string",
    "education_level": "string（学历层次：本科、专科、高中等，不是学位）",
    "degree": "string（学位：学士、硕士、博士等，不是学历）",
    "start_date": "YYYY-MM|null",
    "graduation_date": "YYYY-MM|null（毕业时间）"
  }],
  "skills": {
    "technical": { "explicit": ["string"], "inferred": ["string"], "application_context": "string?" },
    "soft": ["string"],
    "languages": ["string"]
  },
  "projects": [{
    "name": "string",
    "description": { "raw": "string", "optimized": "string", "source": "string" },
    "role": "string?",
    "achievements": { "raw": "string", "optimized": "string", "source": "string" },
    "related_work": "string?",
    "related_work_basis": "string?"
  }]
}
"""

        user_prompt = f"""{schema_definition}

**已提取的基础数据（工具提取）：**
{base_data_json}

**原始简历文本（用于上下文和补全）：**
---
{raw_text}
---

**增强任务：**

**步骤1：补全和验证基础数据**
- 检查基础数据中的字段是否完整、准确
- 从原始文本中补全缺失的字段（如公司名称、职位、时间等）
- **教育背景应尽量提取起止时间**：start_date（入学时间）和毕业时间；毕业时间统一使用 graduation_date 字段。如果只有毕业时间，可以只填写 graduation_date，start_date 为空或null。
- **教育背景字段区分（重要）**：
  - education_level（学历层次）：指教育层次，如"本科"、"专科"、"高中"、"中专"等。**注意："硕士"、"博士"不是学历层次，而是学位！**
  - degree（学位）：指学术学位，如"学士"、"硕士"、"博士"等。
  - 区分规则：
    - 如果简历中写"本科"，应填入 education_level="本科"，degree 可为空或推断为"学士"
    - 如果简历中写"硕士"，应填入 education_level="本科"（如果明确提到本科阶段）或为空，degree="硕士"
    - 如果简历中写"博士"，应填入 education_level="本科"或"硕士"（如果明确提到）或为空，degree="博士"
    - **关键：绝对不要把"硕士"、"博士"填入 education_level 字段！**
- basic_info 和 education 只需精确提取，不需要优化

**步骤2：内容优化**
- 为 responsibilities、achievements、description 等字段生成 optimized 版本
- optimized 仅改善表达，不能改变事实
- 必须同时保留 raw 和 optimized
- **重要：如果工作职责中包含派遣经历，优化时必须保留时间信息：**
  - 格式：`"【YYYY.MM-YYYY.MM】派遣到XX公司/单位，具体工作内容..."`
  - 例如：`"【2019.09-2019.12】派遣到钜芯集成电路测试SMIC新0.13 BCD工艺，完成Motor Driver和Test Chip十余个版本..."`
  - **绝对不要在优化时删除或忽略派遣经历中的时间信息**

**步骤3：隐含信息提取**
- 从文本中推断团队规模、业务领域、技术栈等
- 必须提供推断依据（inference_basis）

**步骤4：关联关系挖掘**
- 建立工作经历与项目、技能之间的关联
- 说明关联类型和依据（relation_basis）

**重要提示：**
1. 优先使用基础数据中已有的字段，只补全缺失的字段
2. raw 与 optimized 必须同时存在（basic_info、education 除外）
3. 所有推断必须提供依据，不能编造内容
4. 如果基础数据中已有字段，直接使用，不要重复提取
5. 输出纯 JSON 格式

现在开始增强，直接输出JSON结果："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            api_start = time.time()
            response = await self.chat_completion(messages, temperature=0.1, max_tokens=8192)
            api_elapsed = time.time() - api_start

            enhanced_data = self._parse_json_response(response)
            total_elapsed = time.time() - start_time

            logger.info(
                f"[LLM增强] 完成: 总耗时{total_elapsed:.2f}秒 (API: {api_elapsed:.2f}秒), "
                f"工作经历: {len(enhanced_data.get('work_experiences', []))}条, "
                f"教育背景: {len(enhanced_data.get('education', []))}条"
            )

            return enhanced_data
        except Exception as e:
            total_elapsed = time.time() - start_time
            logger.error(f"[LLM增强] 失败: 总耗时{total_elapsed:.2f}秒, 错误: {e}")
            logger.warning("[LLM增强] 增强失败，返回基础数据")
            # 标记为不完整，添加错误信息
            base_data["_parsing_status"] = {
                "status": "partial",
                "enhancement_failed": True,
                "error": str(e),
                "message": "LLM增强失败，仅返回基础提取数据，部分字段可能缺失或未优化"
            }
            return base_data

    async def _enhance_resume_in_chunks(self, base_data: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        contexts = self._split_context_sections(raw_text)
        work_context = contexts.get("WORK") or raw_text
        general_context = self._compose_context(contexts, ["SUMMARY", "SKILLS", "PROJECTS", "BASIC"]) or raw_text

        general_base = copy.deepcopy(base_data)
        general_base["work_experiences"] = []

        general_task = self._run_full_enhancement(general_base, general_context)
        work_chunks = self._chunk_list(base_data.get("work_experiences", []), self.work_chunk_size)
        work_tasks = [
            self._enhance_work_chunk(chunk, work_context, idx)
            for idx, chunk in enumerate(work_chunks)
        ]

        results = await asyncio.gather(general_task, *work_tasks)
        combined = results[0]
        combined["work_experiences"] = []
        for chunk_result in results[1:]:
            combined["work_experiences"].extend(chunk_result.get("work_experiences", []))
        return combined

    async def _enhance_work_chunk(self, chunk: List[Dict[str, Any]], context_text: str, chunk_index: int) -> Dict[str, Any]:
        import time
        import json
        start_time = time.time()

        chunk_json = json.dumps({"work_experiences": chunk}, ensure_ascii=False, indent=2)
        MAX_CONTEXT_LENGTH = 8000
        if len(context_text) > MAX_CONTEXT_LENGTH:
            context_text = self._smart_truncate_text(context_text, MAX_CONTEXT_LENGTH)

        system_prompt = """你是一位资深的简历内容优化专家。现在只关注提供的工作经历分片，
每次最多包含3段经历。请在保持事实的前提下，补全缺失字段、优化职责与成就、提取隐含信息并标注来源。
输出格式只需包含 work_experiences。"""

        schema_definition = """
输出 JSON：
{
  "work_experiences": [{
    "company": "string",
    "position": "string",
    "start_date": "YYYY-MM",
    "end_date": "YYYY-MM或空",
    "is_current": true/false,
    "location": "string?",
    "responsibilities": { "raw": ["string"], "optimized": ["string"], "source_paragraphs": ["string"] },
    "achievements": { "raw": ["string"], "optimized": ["string"], "source_paragraphs": ["string"] },
    "implicit_info": {
      "team_size": "string?",
      "team_size_basis": "string?",
      "business_domain": "string?",
      "domain_basis": "string?"
    },
    "skills_used": { "explicit": ["string"], "implicit": ["string"], "application_context": "string?" },
    "related_projects": [{ "project_name": "string", "relation_basis": "string" }]
  }]
}
"""

        user_prompt = f"""{schema_definition}

**待增强的工作经历分片（chunk #{chunk_index + 1}）：**
{chunk_json}

**对应的原始文本：**
---
{context_text}
---

请直接输出JSON："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            api_start = time.time()
            response = await self.chat_completion(messages, temperature=0.1, max_tokens=8192)
            api_elapsed = time.time() - api_start
            parsed = self._parse_json_response(response)
            total_elapsed = time.time() - start_time
            logger.info(f"[LLM增强-分片] chunk#{chunk_index + 1} 完成，耗时{total_elapsed:.2f}秒 (API: {api_elapsed:.2f}秒)")
            return parsed
        except Exception as e:
            logger.error(f"[LLM增强-分片] chunk#{chunk_index + 1} 失败: {e}")
            return {"work_experiences": chunk}

    def _split_context_sections(self, raw_text: str) -> Dict[str, str]:
        sections: Dict[str, List[str]] = {}
        current = "GLOBAL"
        for line in raw_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("[SECTION:") and stripped.endswith("]"):
                current = stripped[len("[SECTION:"):-1] or "GLOBAL"
                continue
            sections.setdefault(current, []).append(line)
        return {key: "\n".join(lines).strip() for key, lines in sections.items()}

    def _compose_context(self, contexts: Dict[str, str], preferred: List[str]) -> str:
        collected = [contexts.get(tag, "") for tag in preferred if contexts.get(tag)]
        if collected:
            return "\n\n".join(collected)
        return contexts.get("GLOBAL", "")

    def _chunk_list(self, data: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
        if not data:
            return []
        return [data[i:i + size] for i in range(0, len(data), size)]

    async def analyze_resume_quality(
        self, 
        resume_data: Dict[str, Any], 
        target_position: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析简历质量并提供优化建议
        """
        system_prompt = """你是一位资深的HR专家、职业规划师和简历优化顾问，拥有15年以上的招聘和简历分析经验。你熟悉各个行业（IT、金融、教育、制造业、服务业等）的招聘标准和简历要求。

你的核心能力：
1. **问题识别**：快速识别简历中的问题和不完善之处
2. **专业评估**：从HR和招聘官的角度评估简历质量
3. **优化建议**：提供具体、可执行的优化建议
4. **行业洞察**：结合行业特点和目标职位要求，提供针对性建议

分析维度：
1. **内容完整性**：检查关键信息是否完整（姓名、联系方式、工作经历、教育背景等）
2. **专业技能匹配度**：评估技能与目标职位的匹配程度
3. **成就表述**：评估工作成就的量化程度和说服力
4. **关键词优化**：识别缺失的关键词和可以优化的关键词
5. **结构逻辑**：评估简历的逻辑性和条理性
6. **表达专业性**：评估表达的规范性和专业性

输出格式要求：
- 必须使用JSON格式输出
- 包含问题识别、评分、具体建议等结构化信息"""
        
        resume_json = json.dumps(resume_data, ensure_ascii=False, indent=2)
        
        user_prompt = f"""请对以下简历进行深度分析，主动识别问题并提供优化建议。

**目标职位：** {target_position or "未指定（请提供通用建议）"}

**简历数据：**
{resume_json}

**分析任务（思维链）：**

**第一步：问题识别**
请主动识别以下问题：
1. **缺失信息**：
   - 基本信息是否完整（姓名、电话、邮箱等）
   - 工作经历是否完整（公司、职位、时间、职责、成就）
   - 教育背景是否完整（学校、专业、学位、时间）
   - 技能是否完整（技术技能、软技能、语言能力）
   - 项目经验是否完整（项目名称、描述、角色、成果）

2. **数据质量问题**：
   - 时间逻辑是否合理（工作经历时间是否重叠、是否合理）
   - 工作年限是否与经历匹配
   - 职位晋升是否合理
   - 技能与工作经历是否匹配

3. **表达问题**：
   - 工作职责是否过于简单或模糊
   - 工作成就是否缺少量化数据
   - 描述是否过于口语化
   - 关键词是否缺失

4. **匹配度问题**：
   - 技能与目标职位是否匹配
   - 工作经历与目标职位是否相关
   - 教育背景是否符合要求

**第二步：评分评估**
对以下维度进行评分（1-10分）：
- 内容完整性（10分）：信息是否完整
- 专业技能匹配度（10分）：技能与目标职位匹配程度
- 成就表述质量（10分）：成就描述是否量化、有说服力
- 关键词优化度（10分）：关键词是否充分、相关
- 整体质量（10分）：简历整体质量

**第三步：具体建议**
针对识别的问题，提供：
1. **立即改进项**（高优先级）：必须立即修改的问题
2. **优化建议**（中优先级）：可以提升简历质量的建议
3. **加分项**（低优先级）：可以增加亮点的建议

每个建议应包含：
- 问题描述：具体指出什么问题
- 改进方向：应该怎么改
- 示例：提供改进后的示例（可选）

**输出格式（JSON）：**
{{
    "overall_score": 8.5,
    "scores": {{
        "completeness": 9,
        "skill_match": 8,
        "achievement_quality": 7,
        "keyword_optimization": 8,
        "overall_quality": 8.5
    }},
    "issues": [
        {{
            "type": "缺失信息|数据质量|表达问题|匹配度问题",
            "severity": "high|medium|low",
            "category": "基本信息|工作经历|教育背景|技能|项目经验",
            "description": "具体问题描述",
            "suggestion": "改进建议",
            "example": "改进示例（可选）"
        }}
    ],
    "suggestions": {{
        "high_priority": [
            {{
                "title": "建议标题",
                "description": "详细描述",
                "action": "具体行动建议",
                "example": "改进示例（可选）"
            }}
        ],
        "medium_priority": [...],
        "low_priority": [...]
    }},
    "keyword_suggestions": [
        {{
            "keyword": "关键词",
            "reason": "为什么需要这个关键词",
            "where_to_add": "应该添加在哪里"
        }}
    ],
    "summary": "总体评价和核心建议（2-3句话）"
}}

现在开始分析，直接输出JSON结果："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.chat_completion(messages, temperature=0.7)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"简历质量分析失败: {e}")
            return {"error": "分析服务暂时不可用"}

    async def generate_professional_evaluation(
        self,
        resume_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成职业摘要和核心能力（从职业摘要角度对候选人进行评估）
        定位：告诉用人单位候选人的能力（招聘视角）
        """
        system_prompt = """你是一位资深的HR专家和猎头顾问，拥有丰富的候选人评估经验。你的任务是基于简历内容，从职业摘要角度对候选人进行评估，帮助用人单位快速了解候选人的能力。

核心能力：
1. **职业定位提炼**：基于工作经历、项目经验、技能等，提炼候选人的职业定位和专长领域
2. **能力总结**：总结候选人的核心技能和能力点
3. **亮点识别**：识别候选人的突出成就和亮点
4. **发展路径评估**：评估候选人的职业发展轨迹和延续性

评估视角：
- 从用人单位/招聘官的角度进行评估
- 帮助用人单位快速了解候选人的职业定位和能力
- 突出候选人的核心优势和亮点

输出格式要求：
- 必须使用JSON格式输出
- 包含职业摘要和核心能力两个字段"""
        
        resume_json = json.dumps(resume_data, ensure_ascii=False, indent=2)
        
        user_prompt = f"""请基于以下简历内容，从职业摘要角度对候选人进行评估，生成职业摘要和核心能力。

**简历数据：**
{resume_json}

**生成任务：**

**第一步：职业摘要（professional_summary）**
基于简历内容，生成精简的职业摘要，包括：
1. **职业定位**：候选人的职业身份和专长领域（一句话概括）
2. **核心亮点**：最突出的1-2个成就或能力（一句话概括）

要求：
- 长度：1-2段，60-100字（必须精简，不要冗长）
- 内容：基于简历事实，只提炼最核心的信息
- 风格：专业、简洁、精炼，避免重复简历中的详细描述
- 重点：突出职业定位和核心亮点，不要展开描述

**第二步：核心能力（core_competencies）**
提炼候选人的关键技能和能力点，每个能力点用一句话概括，包括：
1. **技术技能**：核心技术栈（如"熟练掌握Java、Spring Boot、微服务架构"）
2. **管理能力**：管理经验（如"具备团队管理经验，管理过10人团队"）
3. **行业经验**：行业背景（如"5年金融行业开发经验"）
4. **特殊资质**：证书、资质等（如"持有PMP项目管理证书"）

要求：
- 长度：3-5个要点，每个要点10-20字，总计30-60字（必须精简）
- 内容：只列出最核心的能力点，每个能力点一句话，不要展开描述
- 风格：简洁、要点式，用分号或换行分隔
- 格式：每个能力点独立一行，格式如"技术技能：XXX；管理能力：XXX；行业经验：XXX"

**输出格式（JSON）：**
{{
    "professional_summary": "职业摘要内容（1-2段，60-100字，必须精简）",
    "core_competencies": "核心能力内容（3-5个要点，30-60字，必须精简，每个要点用分号或换行分隔）"
}}

**重要提醒：**
- 职业摘要和核心能力都必须精简，不要冗长
- 只提炼最核心的信息，避免重复简历中的详细描述
- 核心能力每个要点用分号（；）或换行（\n）分隔，便于后续分段显示

现在开始生成，直接输出JSON结果："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = await self.chat_completion(messages, temperature=0.7, max_tokens=1000)
            evaluation_data = self._parse_json_response(response)
            
            # 验证返回数据格式
            if not isinstance(evaluation_data, dict):
                raise ValueError("返回数据格式不正确")
            
            # 确保包含必需字段
            result = {
                "professional_summary": evaluation_data.get("professional_summary", ""),
                "core_competencies": evaluation_data.get("core_competencies", "")
            }
            
            logger.info(f"[职业摘要生成] 完成: professional_summary长度={len(result.get('professional_summary', ''))}, core_competencies长度={len(result.get('core_competencies', ''))}")
            return result
        except Exception as e:
            logger.error(f"职业摘要生成失败: {e}")
            return {
                "professional_summary": "",
                "core_competencies": ""
            }

    async def _generate_evaluation_if_needed(
        self,
        filled_template: Dict[str, Any],
        parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        检查模板中是否有evaluation组件，如果需要则生成职业摘要和核心能力
        """
        # 检查模板中是否有evaluation组件
        has_evaluation_component = False
        evaluation_comp_index = None
        
        for idx, comp in enumerate(filled_template.get("components", [])):
            if comp.get("type") == "evaluation":
                has_evaluation_component = True
                evaluation_comp_index = idx
                break
        
        if not has_evaluation_component:
            return filled_template
        
        # 检查parsed_data中是否已有evaluation数据
        if "evaluation" in parsed_data and parsed_data["evaluation"]:
            evaluation_data = parsed_data["evaluation"]
            # 检查是否包含职业摘要和核心能力
            if evaluation_data.get("professional_summary") or evaluation_data.get("core_competencies"):
                logger.info("[职业摘要生成] 使用已有的evaluation数据")
                if evaluation_comp_index is not None:
                    filled_template["components"][evaluation_comp_index]["data"] = evaluation_data
                return filled_template
        
        # 需要生成职业摘要和核心能力
        logger.info("[职业摘要生成] 开始生成职业摘要和核心能力")
        try:
            evaluation_data = await self.generate_professional_evaluation(parsed_data)
            
            # 填充到evaluation组件
            if evaluation_comp_index is not None:
                filled_template["components"][evaluation_comp_index]["data"] = evaluation_data
            
            logger.info("[职业摘要生成] 生成完成并填充到模板")
        except Exception as e:
            logger.error(f"[职业摘要生成] 生成失败: {e}")
            # 生成失败时，保持空数据，不影响其他组件
        
        return filled_template

    async def analyze_template_structure(
        self,
        template_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析模板结构，生成字段映射规则
        在模板保存时调用，生成预分析的映射规则，避免每次填充时重复分析
        """
        system_prompt = """你是一位资深的简历模板分析专家。你的任务是分析模板结构，生成字段映射规则，用于将解析后的简历数据填充到模板中。

核心任务：
1. **分析模板结构**：理解每个组件的类型、字段列表、字段含义
2. **生成映射规则**：为每个字段生成数据源路径和转换规则
3. **识别复杂字段**：标记哪些字段需要特殊处理（如组合、提取、转换）

输出格式要求：
- 必须使用JSON格式输出
- 包含每个组件的字段映射规则
- 标记需要AI处理的复杂字段"""

        # 提取模板结构信息（精简版，只发送必要信息）
        components_info = []
        for comp in template_structure.get("components", []):
            comp_type = comp.get("type", "")
            comp_title = comp.get("title", "")
            fields = comp.get("fields", [])
            config = comp.get("config", {})
            
            field_mappings = []
            for field in fields:
                field_id = field.get("id", "")
                field_label = field.get("label", "")
                field_desc = field.get("description", "")
                field_data_source = field.get("dataSource", "")
                field_synonyms = field.get("synonyms", [])
                field_format = field.get("format", "")
                field_type = field.get("type", "")

                needs_ai = False
                # 如果没有明确的数据源，认为需要AI处理
                if not field_data_source:
                    needs_ai = True
                # 复杂类型（textarea、richtext等）默认需要AI辅助
                if field_type in ["textarea", "richtext", "markdown"] and not field_data_source:
                    needs_ai = True
                
                field_mapping = {
                    "field_id": field_id,
                    "label": field_label,
                    "description": field_desc,
                    "data_source": field_data_source,
                    "synonyms": field_synonyms,
                    "format": field_format,
                    "field_type": field_type,
                    "needs_ai_extraction": needs_ai
                }
                field_mappings.append(field_mapping)
            
            comp_info = {
                "type": comp_type,
                "title": comp_title,
                "fields": field_mappings,
                "config": config
            }
            components_info.append(comp_info)
        
        template_summary = json.dumps(components_info, ensure_ascii=False, indent=2)
        
        user_prompt = f"""请分析以下模板结构，生成字段映射规则。

**模板结构：**
{template_summary}

**分析任务：**

1. **基本信息组件（basic_info）**：
   - 字段如 name、phone、email、current_location 等
   - 数据源：parsed_data.basic_info
   - 映射规则：field_id → parsed_data.basic_info.field_id

2. **工作经历组件（work_experience）**：
   - 基础字段：period（需要组合 start_date 和 end_date）、company、position
   - 详细字段：report_to、team_size、location、responsibilities、achievements、reason_for_leaving
   - 数据源：parsed_data.work_experiences[]
   - 映射规则：field_id → parsed_data.work_experiences[].field_id
   - 特殊处理：period 需要组合 start_date 和 end_date

3. **教育背景组件（education）**：
   - 字段：period、school、major、education_level、degree、remark
   - 数据源：parsed_data.education[]
   - 映射规则：field_id → parsed_data.education[].field_id
   - 注意：education_level 和 degree 是不同的字段

4. **技能组件（skills）**：
   - 字段：technical、soft、languages
   - 数据源：parsed_data.skills
   - 映射规则：field_id → parsed_data.skills.field_id

5. **项目组件（projects）**：
   - 字段：project_name、project_description（兼容 project_content）、project_role、project_achievements
   - 数据源：parsed_data.projects[]
   - 映射规则：field_id → parsed_data.projects[].field_id

**输出格式（JSON）：**
{{
    "field_mapping": {{
        "basic_info": {{
            "name": {{
                "data_source": "parsed_data.basic_info.name",
                "type": "direct",
                "transform": null
            }},
            "phone": {{
                "data_source": "parsed_data.basic_info.phone",
                "type": "direct",
                "transform": null
            }},
            "current_location": {{
                "data_source": "parsed_data.basic_info.location || parsed_data.basic_info.work_location",
                "type": "fallback",
                "transform": null
            }}
        }},
        "work_experience": {{
            "company": {{
                "data_source": "parsed_data.work_experiences[].company",
                "type": "direct",
                "transform": null
            }},
            "position": {{
                "data_source": "parsed_data.work_experiences[].position",
                "type": "direct",
                "transform": null
            }},
            "period": {{
                "data_source": "parsed_data.work_experiences[]",
                "type": "combine",
                "transform": "combine(start_date, end_date, format='YYYY-MM - YYYY-MM')"
            }},
            "responsibilities": {{
                "data_source": "parsed_data.work_experiences[].responsibilities",
                "type": "direct",
                "transform": null
            }},
            "achievements": {{
                "data_source": "parsed_data.work_experiences[].achievements",
                "type": "direct",
                "transform": null
            }}
        }},
        "education": {{
            "school": {{
                "data_source": "parsed_data.education[].school",
                "type": "direct",
                "transform": null
            }},
            "education_level": {{
                "data_source": "parsed_data.education[].education_level || parsed_data.education[].degree_level",
                "type": "fallback",
                "transform": null
            }},
            "degree": {{
                "data_source": "parsed_data.education[].degree",
                "type": "direct",
                "transform": null
            }}
        }},
        "skills": {{
            "technical": {{
                "data_source": "parsed_data.skills.technical",
                "type": "direct",
                "transform": null
            }},
            "soft": {{
                "data_source": "parsed_data.skills.soft",
                "type": "direct",
                "transform": null
            }},
            "languages": {{
                "data_source": "parsed_data.skills.languages",
                "type": "direct",
                "transform": null
            }}
        }},
        "projects": {{
            "project_name": {{
                "data_source": "parsed_data.projects[].name || parsed_data.projects[].project_name",
                "type": "fallback",
                "transform": null
            }},
            "project_description": {{
                "data_source": "parsed_data.projects[].description || parsed_data.projects[].project_content",
                "type": "fallback",
                "transform": null
            }},
            "project_role": {{
                "data_source": "parsed_data.projects[].responsibilities",
                "type": "direct",
                "transform": null
            }},
            "project_achievements": {{
                "data_source": "parsed_data.projects[].achievements || parsed_data.projects[].outcome",
                "type": "fallback",
                "transform": null
            }}
        }}
    }},
    "complex_fields": [
        {{
            "component_type": "work_experience",
            "field_id": "responsibilities",
            "needs_ai_extraction": false,
            "reason": "可以直接从parsed_data中提取"
        }}
    ]
}}

**重要提示：**
1. 如果字段有 dataSource 元数据，优先使用该数据源
2. 如果字段有 synonyms，考虑同义词匹配
3. period 字段需要组合 start_date 和 end_date
4. current_location 可能需要从 location 或 work_location 获取
5. education_level 和 degree 是不同的字段，需要分别映射
6. 标记需要AI处理的复杂字段（如需要从文本中提取的字段）

现在开始分析，直接输出JSON结果："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        complex_fields: List[Dict[str, Any]] = []

        try:
            logger.info(f"[模板分析] 开始分析模板结构，组件数: {len(template_structure.get('components', []))}")
            
            response = await self.chat_completion(messages, temperature=0.1, max_tokens=2000)
            
            mapping_rules = self._parse_json_response(response)

            # 如果AI未返回复杂字段列表，则根据 needs_ai_extraction 自动生成
            if mapping_rules.get("field_mapping"):
                generated_complex_fields = []
                for comp_type, fields_map in mapping_rules["field_mapping"].items():
                    for field_id, info in fields_map.items():
                        if isinstance(info, dict) and info.get("needs_ai_extraction"):
                            generated_complex_fields.append({
                                "component_type": comp_type,
                                "field_id": field_id,
                                "field_type": info.get("field_type"),
                                "label": info.get("label"),
                                "description": info.get("description", "")
                            })
                if not mapping_rules.get("complex_fields"):
                    mapping_rules["complex_fields"] = generated_complex_fields
                else:
                    # 合并去重
                    existing = {(item.get("component_type"), item.get("field_id")) for item in mapping_rules["complex_fields"]}
                    for item in generated_complex_fields:
                        key = (item.get("component_type"), item.get("field_id"))
                        if key not in existing:
                            mapping_rules["complex_fields"].append(item)

            logger.info(f"[模板分析] 分析完成，生成映射规则")
            
            return mapping_rules
            
        except Exception as e:
            logger.warning(f"[模板分析] AI分析失败: {e}，使用默认映射规则")
            # 如果AI分析失败，返回空映射规则，后续使用直接映射
            return {
                "field_mapping": {},
                "complex_fields": []
            }

    def _fill_template_with_mapping_rules(
        self,
        template_structure: Dict[str, Any],
        parsed_data: Dict[str, Any],
        field_mapping: Dict[str, Any]
    ) -> (Dict[str, Any], List[Dict[str, Any]]):
        """
        使用预分析的映射规则填充模板（快速、准确）
        这是优化后的方法：直接使用映射规则，不需要AI生成
        """
        filled_template = template_structure.copy()
        filled_template["components"] = []
        
        mapping_rules = field_mapping.get("field_mapping", {})
        complex_tasks: List[Dict[str, Any]] = []

        def is_empty(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, str):
                return value.strip() == ""
            if isinstance(value, (list, tuple, set, dict)):
                return len(value) == 0
            return False
        
        for comp_index, comp in enumerate(template_structure.get("components", [])):
            filled_comp = comp.copy()
            comp_type = comp.get("type", "")
            comp_mapping = mapping_rules.get(comp_type, {})
            
            # 根据组件类型填充数据
            if comp_type == "basic_info":
                basic_info = parsed_data.get("basic_info", {})
                filled_comp["data"] = {}
                for field in comp.get("fields", []):
                    field_id = field.get("id") or field.get("field") or field.get("name")
                    if not field_id:
                        continue
                    
                    # 使用映射规则
                    field_rule = comp_mapping.get(field_id, {})
                    data_source = field_rule.get("data_source", "")
                    transform_type = field_rule.get("type", "direct")
                    needs_ai = field_rule.get("needs_ai_extraction", False)
                    
                    value = None
                    if data_source:
                        # 解析数据源路径（简化版，支持基本路径）
                        if data_source.startswith("parsed_data.basic_info."):
                            source_field = data_source.split(".")[-1]
                            if "||" in data_source:
                                # 支持 fallback：parsed_data.basic_info.location || parsed_data.basic_info.work_location
                                sources = [s.strip().split(".")[-1] for s in data_source.split("||")]
                                for src in sources:
                                    if src in basic_info and basic_info[src]:
                                        value = basic_info[src]
                                        break
                            else:
                                value = basic_info.get(source_field)
                    
                    # 如果映射规则没有找到值，尝试多种匹配方式
                    if not value:
                        # 1. 直接匹配
                        if field_id in basic_info:
                            value = basic_info[field_id]
                        else:
                            # 2. 尝试标准化匹配
                            normalized_id = normalize_field_name(field_id)
                            if normalized_id != field_id and normalized_id in basic_info:
                                value = basic_info[normalized_id]
                            else:
                                # 3. 尝试同义词匹配
                                synonyms = get_field_synonyms(field_id)
                                for synonym in synonyms:
                                    if synonym in basic_info and basic_info[synonym]:
                                        value = basic_info[synonym]
                                        logger.debug(f"[基本信息填充] 字段 {field_id} 通过同义词 {synonym} 匹配到值: {value}")
                                        break
                                
                                # 4. 特殊字段映射（在同义词匹配失败后）
                                if not value:
                                    if field_id == "current_location":
                                        value = basic_info.get("location", "") or basic_info.get("work_location", "")
                                    elif field_id in ["website", "website_url"]:
                                        value = basic_info.get("website") or basic_info.get("website_url", "")
                                    elif field_id in ["linkedin", "linkedin_url"]:
                                        value = basic_info.get("linkedin") or basic_info.get("linkedin_url", "")
                                    elif field_id in ["birthday", "birth_date"]:
                                        # 生日字段可能有多种命名
                                        value = basic_info.get("birthday", "") or basic_info.get("birth_date", "") or basic_info.get("出生日期", "") or basic_info.get("出生年月", "")
                                        if value:
                                            logger.debug(f"[基本信息填充] 字段 {field_id} 通过特殊映射匹配到生日值: {value}")
                                    elif field_id == "gender":
                                        # 性别字段可能有多种命名
                                        value = basic_info.get("gender", "") or basic_info.get("性别", "") or basic_info.get("性", "")
                                        if value:
                                            logger.debug(f"[基本信息填充] 字段 {field_id} 通过特殊映射匹配到性别值: {value}")
                                    elif field_id in ["birthday", "birth_date"]:
                                        # 生日字段可能有多种命名
                                        value = basic_info.get("birthday", "") or basic_info.get("birth_date", "") or basic_info.get("出生日期", "") or basic_info.get("出生年月", "")
                                    elif field_id == "gender":
                                        # 性别字段可能有多种命名
                                        value = basic_info.get("gender", "") or basic_info.get("性别", "") or basic_info.get("性", "")
                    
                    filled_comp["data"][field_id] = value if value is not None else ""

                    if needs_ai and is_empty(filled_comp["data"].get(field_id)):
                        complex_tasks.append({
                            "component_type": comp_type,
                            "component_index": comp_index,
                            "field_id": field_id,
                            "row_index": None,
                            "field_rule": field_rule,
                            "context": basic_info
                        })
            
            elif comp_type == "work_experience":
                work_exps = parsed_data.get("work_experiences", [])
                # 使用统一的排序方法：按时间由近及远排序（当前工作优先，然后按start_date降序）
                work_exps_sorted = self._sort_work_experiences(work_exps)
                comp_mapping = mapping_rules.get("work_experience", {})
                
                rows = []
                for row_index, exp in enumerate(work_exps_sorted):
                    row = {}
                    for field in comp.get("fields", []):
                        field_id = field.get("id") or field.get("field") or field.get("name")
                        if not field_id:
                            continue
                        
                        # 使用映射规则
                        field_rule = comp_mapping.get(field_id, {})
                        data_source = field_rule.get("data_source", "")
                        transform_type = field_rule.get("type", "direct")
                        transform = field_rule.get("transform")
                        needs_ai = field_rule.get("needs_ai_extraction", False)
                        
                        if field_id == "period" and transform_type == "combine":
                            # 组合 start_date 和 end_date
                            start_date = self._format_date(exp.get("start_date", ""))
                            end_date = self._format_date(exp.get("end_date", ""))
                            is_current = exp.get("is_current", False)
                            if is_current or not end_date:
                                period = f"{start_date} - 至今" if start_date else ""
                            else:
                                period = f"{start_date} - {end_date}" if start_date else ""
                            row[field_id] = period
                        elif data_source and data_source.startswith("parsed_data.work_experiences[]"):
                            # 从工作经历中提取字段
                            source_field = data_source.split(".")[-1] if "." in data_source else field_id
                            value = exp.get(source_field, "")
                            if isinstance(value, list):
                                row[field_id] = value
                            else:
                                row[field_id] = value
                        else:
                            # 直接匹配
                            row[field_id] = exp.get(field_id, "")
                    
                        if needs_ai and is_empty(row.get(field_id)):
                            complex_tasks.append({
                                "component_type": comp_type,
                                "component_index": comp_index,
                                "field_id": field_id,
                                "row_index": row_index,
                                "field_rule": field_rule,
                                "context": exp
                            })

                    rows.append(row)
                
                filled_comp["data"] = {"rows": rows}
            
            elif comp_type == "education":
                educations = parsed_data.get("education", [])
                comp_mapping = mapping_rules.get("education", {})
                
                rows = []
                for edu in educations:
                    row = {}
                    for field in comp.get("fields", []):
                        field_id = field.get("id") or field.get("field") or field.get("name")
                        if not field_id:
                            continue
                        
                        # 使用映射规则
                        field_rule = comp_mapping.get(field_id, {})
                        data_source = field_rule.get("data_source", "")
                        needs_ai = field_rule.get("needs_ai_extraction", False)
                        
                        if data_source and "||" in data_source:
                            # 支持 fallback
                            sources = [s.strip().split(".")[-1] for s in data_source.split("||")]
                            value = None
                            for src in sources:
                                if src in edu and edu[src]:
                                    value = edu[src]
                                    break
                            row[field_id] = value or ""
                        elif data_source and data_source.startswith("parsed_data.education[]"):
                            source_field = data_source.split(".")[-1] if "." in data_source else field_id
                            row[field_id] = edu.get(source_field, "")
                        else:
                            # 直接匹配
                            row[field_id] = edu.get(field_id, "")
                    
                    rows.append(row)
                
                filled_comp["data"] = {"rows": rows}
            
            elif comp_type == "skills":
                skills = parsed_data.get("skills", {})
                comp_mapping = mapping_rules.get("skills", {})
                
                # 记录日志：检查实际数据
                logger.info(f"[映射规则填充] skills组件 - parsed_data中的skills字段: {list(skills.keys())}")
                logger.info(f"[映射规则填充] skills组件 - 模板中的fields: {[f.get('id') or f.get('field') or f.get('name') for f in comp.get('fields', [])]}")
                logger.info(f"[映射规则填充] skills组件 - 映射规则: {comp_mapping}")
                
                filled_comp["data"] = {}
                for field in comp.get("fields", []):
                    field_id = field.get("id") or field.get("field") or field.get("name")
                    if not field_id:
                        continue
                    
                    # 使用映射规则
                    field_rule = comp_mapping.get(field_id, {})
                    data_source = field_rule.get("data_source", "")
                    needs_ai = field_rule.get("needs_ai_extraction", False)
                    
                    if data_source and data_source.startswith("parsed_data.skills."):
                        source_field = data_source.split(".")[-1]
                        filled_comp["data"][field_id] = skills.get(source_field, [])
                        logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 使用data_source {source_field}，值: {skills.get(source_field, [])}")
                    else:
                        # 尝试多种可能的字段名匹配
                        # 1. 直接匹配
                        if field_id in skills:
                            filled_comp["data"][field_id] = skills[field_id]
                            logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 直接匹配成功，值: {skills[field_id]}")
                        # 2. 尝试标准字段名映射
                        elif field_id == "technical_ability" and "technical" in skills:
                            filled_comp["data"][field_id] = skills["technical"]
                            logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 映射到 technical，值: {skills['technical']}")
                        elif field_id == "soft_skills" and "soft" in skills:
                            filled_comp["data"][field_id] = skills["soft"]
                            logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 映射到 soft，值: {skills['soft']}")
                        elif field_id == "language_ability" and "languages" in skills:
                            filled_comp["data"][field_id] = skills["languages"]
                            logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 映射到 languages，值: {skills['languages']}")
                        # 3. 反向映射
                        elif field_id == "technical" and "technical_ability" in skills:
                            filled_comp["data"][field_id] = skills["technical_ability"]
                            logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 映射到 technical_ability，值: {skills['technical_ability']}")
                        elif field_id == "soft" and "soft_skills" in skills:
                            filled_comp["data"][field_id] = skills["soft_skills"]
                            logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 映射到 soft_skills，值: {skills['soft_skills']}")
                        elif field_id == "languages" and "language_ability" in skills:
                            filled_comp["data"][field_id] = skills["language_ability"]
                            logger.info(f"[映射规则填充] skills组件 - 字段 {field_id}: 映射到 language_ability，值: {skills['language_ability']}")
                        else:
                            filled_comp["data"][field_id] = []
                            logger.warning(f"[映射规则填充] skills组件 - 字段 {field_id}: 未找到匹配的数据源")
                
                logger.info(f"[映射规则填充] skills组件 - 最终填充的数据: {filled_comp['data']}")
            
            elif comp_type == "projects":
                projects = parsed_data.get("projects", [])
                comp_mapping = mapping_rules.get("projects", {})
                
                logger.info(f"[映射规则填充] projects组件 - 解析数据中的项目数量: {len(projects)}")
                logger.info(f"[映射规则填充] projects组件 - 解析数据中的项目示例: {projects[0] if projects else '无'}")
                logger.info(f"[映射规则填充] projects组件 - 映射规则: {comp_mapping}")
                
                fields = comp.get("fields", [])
                table_columns = comp.get("config", {}).get("tableColumns", [])
                logger.info(f"[映射规则填充] projects组件 - 模板fields配置: {[f.get('id') or f.get('field') or f.get('name') for f in fields] if fields else '无'}")
                logger.info(f"[映射规则填充] projects组件 - 模板tableColumns配置: {[c.get('field') or c.get('id') or c.get('name') for c in table_columns] if table_columns else '无'}")
                
                # 确定要填充的字段列表
                fields_to_fill = []
                if fields:
                    fields_to_fill = fields
                elif table_columns:
                    # 如果只有tableColumns，将其转换为fields格式
                    fields_to_fill = [{"id": col.get("field") or col.get("id") or col.get("name"), "field": col.get("field") or col.get("id") or col.get("name"), "name": col.get("field") or col.get("id") or col.get("name")} for col in table_columns if col.get("field") or col.get("id") or col.get("name")]
                
                logger.info(f"[映射规则填充] projects组件 - 要填充的字段列表: {[f.get('id') or f.get('field') or f.get('name') for f in fields_to_fill] if fields_to_fill else '无'}")
                
                rows = []
                for proj in projects:
                    row = {}
                    for field in fields_to_fill:
                        field_id = field.get("id") or field.get("field") or field.get("name")
                        if not field_id:
                            continue
                        
                        # 使用映射规则
                        field_rule = comp_mapping.get(field_id, {})
                        data_source = field_rule.get("data_source", "")
                        needs_ai = field_rule.get("needs_ai_extraction", False)
                        
                        if data_source and "||" in data_source:
                            # 支持 fallback
                            sources = [s.strip().split(".")[-1] for s in data_source.split("||")]
                            value = None
                            for src in sources:
                                if src in proj and proj[src]:
                                    value = proj[src]
                                    break
                            row[field_id] = value or ""
                        elif data_source and data_source.startswith("parsed_data.projects[]"):
                            source_field = data_source.split(".")[-1] if "." in data_source else field_id
                            row[field_id] = proj.get(source_field, "")
                        else:
                            # 直接匹配，但也要考虑字段名映射
                            if field_id == "project_name" or field_id == "name":
                                row[field_id] = proj.get("name", "") or proj.get("project_name", "")
                            elif field_id == "project_description" or field_id == "description":
                                # 统一规范化description字段
                                desc_value = proj.get("description", "") or proj.get("content", "") or proj.get("project_description", "")
                                desc_value = self._normalize_description_field(desc_value)
                                # 清理特殊字符
                                if desc_value:
                                    desc_value = self._clean_text_for_fill(desc_value)
                                row[field_id] = desc_value
                            elif field_id == "project_content" or field_id == "content":
                                # 统一规范化description字段
                                desc_value = proj.get("description", "") or proj.get("content", "") or proj.get("project_content", "")
                                desc_value = self._normalize_description_field(desc_value)
                                # 清理特殊字符
                                if desc_value:
                                    desc_value = self._clean_text_for_fill(desc_value)
                                row[field_id] = desc_value
                            elif field_id == "project_role":
                                # project_role 在模板中表示"项目职责"，应该从 responsibilities 获取，不是 role
                                resp_value = proj.get("responsibilities", [])
                                if isinstance(resp_value, list):
                                    # 如果是数组，合并成字符串（用换行或分号分隔）
                                    row[field_id] = "；".join([str(r).strip() for r in resp_value if r and str(r).strip()]) if resp_value else ""
                                else:
                                    row[field_id] = str(resp_value) if resp_value else ""
                            elif field_id == "role":
                                # role 字段表示项目角色（如"KAM"、"项目经理"等），不是职责
                                row[field_id] = proj.get("role", "") or proj.get("project_role", "")
                            elif field_id == "project_achievements" or field_id == "achievements":
                                row[field_id] = proj.get("achievements", "") or proj.get("outcome", "") or proj.get("project_achievements", "")
                            elif field_id == "project_outcome" or field_id == "outcome":
                                row[field_id] = proj.get("outcome", "") or proj.get("project_outcome", "")
                            else:
                                row[field_id] = proj.get(field_id, "")
                    
                    rows.append(row)
                
                logger.info(f"[映射规则填充] projects组件 - 填充后的rows数量: {len(rows)}")
                logger.info(f"[映射规则填充] projects组件 - 填充后的rows示例: {rows[0] if rows else '无'}")
                filled_comp["data"] = {"rows": rows}
            else:
                # 其他组件类型，使用直接映射
                filled_comp["data"] = {}
            
            filled_template["components"].append(filled_comp)
        
        return filled_template, complex_tasks

    async def _fill_complex_fields_with_ai(
        self,
        filled_template: Dict[str, Any],
        parsed_data: Dict[str, Any],
        complex_tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        对需要AI处理的字段，调用DeepSeek生成内容。
        每次仅发送相关的数据片段，减少Token消耗。
        """
        if not complex_tasks:
            return filled_template

        system_prompt = """你是一位资深的简历数据生成助手，擅长根据已有信息补全缺失的简历字段。
输出要求：
1. 只输出JSON，不要包含其他文字。
2. JSON中只包含一个键值对，键为字段ID，值为生成的内容。
3. 若无法生成，请返回空字符串或空数组。"""

        for task in complex_tasks:
            component_index = task.get("component_index")
            field_id = task.get("field_id")
            component_type = task.get("component_type")
            row_index = task.get("row_index")
            field_rule = task.get("field_rule") or {}
            context = task.get("context") or {}

            label = field_rule.get("label") or field_id
            description = field_rule.get("description") or ""
            field_type = field_rule.get("field_type") or ""

            try:
                # 准备最小化上下文，仅发送与该字段相关的数据
                context_json = json.dumps(context, ensure_ascii=False, indent=2)
                user_prompt = f"""请补全简历字段。

字段ID：{field_id}
字段名称：{label}
组件类型：{component_type}
字段说明：{description or "无"}
预期字段类型：{field_type or "text"}

相关数据：
{context_json}

请输出JSON：{{"{field_id}": 值 }}"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

                response = await self.chat_completion(messages, temperature=0.2, max_tokens=600)
                ai_result = self._parse_json_response(response)
                value = ai_result.get(field_id)

                if value is None:
                    continue

                # 根据字段类型做简单归一化
                if field_type in ["textarea", "richtext", "markdown"]:
                    if isinstance(value, list):
                        value = "\n".join(str(item) for item in value)
                    else:
                        value = str(value)
                elif isinstance(value, str) and field_type in ["list", "tags"]:
                    # 期望列表，但AI返回字符串时，按换行或逗号拆分
                    value = [item.strip() for item in value.replace("；", ";").replace("，", ",").split(",") if item.strip()]

                # 写入结果
                component = filled_template["components"][component_index]
                if row_index is not None:
                    if "data" not in component:
                        component["data"] = {"rows": []}
                    if "rows" not in component["data"]:
                        component["data"]["rows"] = []
                    rows = component["data"]["rows"]
                    while len(rows) <= row_index:
                        rows.append({})
                    rows[row_index][field_id] = value
                else:
                    if "data" not in component:
                        component["data"] = {}
                    component["data"][field_id] = value

            except Exception as e:
                logger.warning(f"[复杂字段填充] 字段 {field_id} 生成失败: {e}")
                continue

        return filled_template

    async def fill_template_with_resume_data(
        self,
        template_structure: Dict[str, Any],
        parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据模板结构，将简历数据填充到模板中，生成规范化简历
        优化策略：
        1. 优先使用预分析的映射规则（最快、最准确）
        2. 如果没有映射规则，先使用直接映射快速填充（不依赖AI）
        3. 如果直接映射效果不理想，再使用AI填充（最慢但最智能）
        """
        # 预处理：对工作经历按时间由近及远排序（确保所有填充路径都使用排序后的数据）
        if "work_experiences" in parsed_data and isinstance(parsed_data["work_experiences"], list):
            parsed_data["work_experiences"] = self._sort_work_experiences(parsed_data["work_experiences"])
            logger.info(f"[模板填充] 工作经历已排序，共{len(parsed_data['work_experiences'])}条")
        
        # 检查是否有预分析的映射规则
        field_mapping = template_structure.get("field_mapping")
        logger.info(f"[模板填充] 检查映射规则 - field_mapping存在: {field_mapping is not None}, 类型: {type(field_mapping)}, isinstance(dict): {isinstance(field_mapping, dict) if field_mapping else False}")
        
        # 验证映射规则的有效性
        # 兼容旧数据：如果 field_mapping 是空字典 {}，说明是旧格式，需要转换为新格式
        has_valid_mapping = False
        if field_mapping is None:
            logger.info(f"[模板填充] field_mapping 为 None，使用直接映射")
        elif isinstance(field_mapping, dict):
            # 检查是否是旧格式（空字典或没有 "field_mapping" 键）
            if len(field_mapping) == 0 or "field_mapping" not in field_mapping:
                logger.info(f"[模板填充] 检测到旧格式 field_mapping，转换为新格式")
                field_mapping = {
                    "field_mapping": {},
                    "complex_fields": []
                }
            
            inner_mapping = field_mapping.get("field_mapping", {})
            logger.info(f"[模板填充] inner_mapping存在: {inner_mapping is not None}, 类型: {type(inner_mapping)}, 长度: {len(inner_mapping) if isinstance(inner_mapping, dict) else 'N/A'}")
            if inner_mapping and isinstance(inner_mapping, dict) and len(inner_mapping) > 0:
                has_valid_mapping = True
                logger.info(f"[模板填充] ✅ 发现有效映射规则，组件类型: {list(inner_mapping.keys())}")
            else:
                logger.info(f"[模板填充] ⚠️ 映射规则为空，将使用直接映射: inner_mapping={inner_mapping is not None}, 类型={type(inner_mapping) if inner_mapping else 'None'}, 长度={len(inner_mapping) if isinstance(inner_mapping, dict) else 'N/A'}")
        else:
            logger.warning(f"[模板填充] ⚠️ field_mapping不是有效字典: 值={field_mapping}, 类型={type(field_mapping)}, isinstance(dict)={isinstance(field_mapping, dict) if field_mapping else False}")
        
        # 检查是否有有效的映射规则
        if has_valid_mapping:
            # 使用预分析的映射规则（快速、准确）
            logger.info(f"[模板填充] ✅ 使用预分析的映射规则填充模板（快速路径）")
            try:
                filled_template, complex_tasks = self._fill_template_with_mapping_rules(
                    template_structure, parsed_data, field_mapping
                )

                if complex_tasks:
                    logger.info(f"[模板填充] 检测到 {len(complex_tasks)} 个复杂字段，调用AI补全")
                    filled_template = await self._fill_complex_fields_with_ai(
                        filled_template, parsed_data, complex_tasks
                    )

                # 检查是否需要生成职业摘要和核心能力
                filled_template = await self._generate_evaluation_if_needed(filled_template, parsed_data)

                logger.info(f"[模板填充] 映射规则填充完成")
                return filled_template
            except Exception as e:
                logger.warning(f"[模板填充] 映射规则填充失败: {e}，回退到直接映射")
                # 如果映射规则填充失败，回退到直接映射
                pass
        
        # 如果没有映射规则或映射规则填充失败，先使用直接映射快速填充
        logger.warning(f"[模板填充] ⚠️ 没有映射规则，使用直接映射快速填充模板（不依赖AI，但比映射规则慢）")
        try:
            filled_template = self._direct_fill_template(template_structure, parsed_data)
            logger.info(f"[模板填充] 直接映射填充完成，组件数: {len(filled_template.get('components', []))}")
            
            # 检查是否需要生成职业摘要和核心能力
            filled_template = await self._generate_evaluation_if_needed(filled_template, parsed_data)
            
            return filled_template
        except Exception as e:
            logger.warning(f"[模板填充] 直接映射填充失败: {e}，回退到AI填充")
            # 如果直接映射也失败，回退到AI填充
            pass
        
        # 如果直接映射也失败，使用AI填充（最后的后备方案）
        logger.warning(f"[模板填充] 使用AI填充模板（后备方案）- 注意：这比直接映射慢很多，请检查为什么直接映射失败")
        
        system_prompt = """你是一位资深的简历规范化专家和HR顾问，拥有丰富的简历模板设计和数据匹配经验。你的任务是根据模板结构，将解析后的简历数据智能填充到模板中，生成规范化简历。

核心能力：
1. **深度理解模板结构**：理解每个组件的类型、字段含义、配置选项
2. **智能数据匹配**：识别同义词、理解字段语义、处理数据格式差异
3. **上下文理解**：结合整个简历的上下文，做出最合理的匹配决策
4. **数据完整性**：确保所有可用数据都被正确填充，不遗漏关键信息

模板组件类型详解：
- **basic_info（基本信息）**：包含姓名、电话、邮箱、地址等个人联系信息
  - 字段示例：name（姓名）、phone（电话）、email（邮箱）、location（所在地）
  - 数据来源：parsed_data.basic_info 对象
  - 输出格式：data = {"name": "...", "phone": "...", "email": "...", ...}

- **work_experience（工作经历）**：支持表格概览和详细卡片两种展示模式，通过 displayMode 配置控制
  - 基础字段（用于表格显示）：period（起止时间）、company（公司名称）、position（职位）
  - 详细字段（用于详细卡片显示）：report_to（汇报对象）、team_size（下属团队）、location（工作地点）、responsibilities（工作职责）、achievements（工作业绩）、reason_for_leaving（离职原因）、project_experience（项目经历）
  - 数据来源：parsed_data.work_experiences 数组
  - 输出格式：data = {"rows": [{"period": "2020-01 - 2023-06", "company": "...", "position": "...", "report_to": "...", "team_size": "...", "location": "...", "responsibilities": [...], "achievements": [...], ...}, ...]}
  - 注意：
    - period 需要从 start_date 和 end_date 组合，格式为"YYYY-MM - YYYY-MM"或"YYYY-MM - 至今"
    - 所有字段（基础字段和详细字段）都应该填充到同一个 work_experience 组件中
    - displayMode 配置：summary（仅表格）、detailed（仅详细卡片）、both（表格+详细卡片）

- **education（教育背景）**：学历和教育经历
  - 字段示例：period（时间）、school（学校）、major（专业）、degree（学位）、education_level（学历层次）
  - **重要区分**：
    - education_level（学历层次）：指教育层次，如"本科"、"专科"、"高中"等
    - degree（学位）：指学术学位，如"学士"、"硕士"、"博士"等
    - 两者不同！学历是教育层次，学位是学术学位
  - 数据来源：parsed_data.education 数组
  - 输出格式：data = {"rows": [{"period": "2020-06", "school": "...", "major": "...", "education_level": "...", "degree": "..."}, ...]}

- **skills（技能专长）**：技术技能、软技能、语言能力
  - 字段示例：technical（技术技能）、soft（软技能）、languages（语言能力）
  - 数据来源：parsed_data.skills 对象
  - 输出格式：data = {"technical": [...], "soft": [...], "languages": [...]}

- **projects（项目经历）**：项目经验和成果
  - 字段示例：name（项目名称）、description（项目描述）、role（担任角色）、achievements（项目业绩/成果）
  - 数据来源：parsed_data.projects 数组
  - 输出格式：data = {"rows": [...]} 或 data = {"items": [...]}

字段匹配策略（思维链）：
1. **第一步：理解字段含义**
   - 分析字段ID和标签，理解字段的真实含义
   - 识别同义词和变体（如"职位"、"岗位"、"工作名称"都表示 position）
   - 考虑字段的上下文（如"工作地点"在 work_experience 中表示工作地点，在 basic_info 中表示居住地）

2. **第二步：定位数据源**
   - 根据组件类型，确定数据来源（basic_info、work_experiences、education等）
   - 对于数组类型，确定取哪个元素（通常取第一个，或根据时间排序取最新的）

3. **第三步：数据转换**
   - 格式转换（如时间格式统一、数据格式调整）
   - 数据合并（如将 start_date 和 end_date 合并为 period）
   - 数据提取（如从 responsibilities 数组中提取职责描述）

4. **第四步：填充数据**
   - 按照模板要求的格式填充数据
   - 保持数据完整性和准确性
   - 处理缺失数据（留空或使用默认值）

常见字段映射（同义词识别）：
- **姓名类**：name、姓名、名字、全名 → basic_info.name
- **电话类**：phone、电话、手机、手机号、联系电话 → basic_info.phone
- **邮箱类**：email、邮箱、电子邮件、E-mail → basic_info.email
- **职位类**：position、职位、岗位、工作名称、职务 → work_experiences[].position
- **公司类**：company、公司、公司名称、企业、单位 → work_experiences[].company
- **学校类**：school、学校、学校名称、院校、毕业院校 → education[].school
- **专业类**：major、专业、专业名称、所学专业 → education[].major
- **职责类**：responsibilities、工作职责、职责、工作内容 → work_experiences[].responsibilities
- **成就类**：achievements、工作成就、业绩、工作成果 → work_experiences[].achievements

输出要求：
- 返回填充后的完整模板结构（JSON格式）
- 必须保持原模板的 components 数组顺序和结构完全不变
- 每个组件必须包含 data 字段
- 只输出JSON，不要有任何其他文字说明
"""

        template_json = json.dumps(template_structure, ensure_ascii=False, indent=2)
        resume_json = json.dumps(parsed_data, ensure_ascii=False, indent=2)
        
        # 分析模板结构，提取字段信息和元数据用于增强上下文
        components_info = []
        for comp in template_structure.get("components", []):
            comp_type = comp.get("type", "")
            comp_title = comp.get("title", "")
            comp_description = comp.get("componentDescription", "")
            comp_data_format = comp.get("dataFormat", "")
            fields = comp.get("fields", [])
            config = comp.get("config", {})
            
            field_descriptions = []
            for field in fields:
                field_id = field.get("id", "")
                field_label = field.get("label", "")
                field_type = field.get("type", "")
                field_desc = field.get("description", "")
                field_example = field.get("example", "")
                field_data_source = field.get("dataSource", "")
                field_synonyms = field.get("synonyms", [])
                field_format = field.get("format", "")
                
                field_info = f"  - {field_id}"
                if field_label:
                    field_info += f"（标签：{field_label}）"
                if field_type:
                    field_info += f"，类型：{field_type}"
                if field_desc:
                    field_info += f"\n    说明：{field_desc}"
                if field_example:
                    field_info += f"\n    示例：{field_example}"
                if field_data_source:
                    field_info += f"\n    数据来源：{field_data_source}"
                if field_synonyms:
                    field_info += f"\n    同义词：{', '.join(field_synonyms)}"
                if field_format:
                    field_info += f"\n    格式要求：{field_format}"
                field_descriptions.append(field_info)
            
            comp_info = f"- {comp_type}（{comp_title}）"
            if comp_description:
                comp_info += f"\n  组件说明：{comp_description}"
            if comp_data_format:
                comp_info += f"\n  数据格式：{comp_data_format}"
            if field_descriptions:
                comp_info += f"\n  字段列表：\n" + "\n".join(field_descriptions)
            if config:
                comp_info += f"\n  配置：{json.dumps(config, ensure_ascii=False)}"
            components_info.append(comp_info)
        
        components_summary = "\n".join(components_info) if components_info else "（无组件）"

        user_prompt = f"""请根据以下模板结构，将简历数据填充到模板中，生成规范化简历。

**模板结构分析：**
{components_summary}

**完整模板结构（JSON）：**
{template_json}

**简历数据（已解析）：**
{resume_json}

**填充步骤（思维链）：**

步骤1：分析模板结构
- 识别每个组件的类型和字段
- 理解字段的含义和用途
- 注意组件的配置选项（如表格列配置）

步骤2：匹配数据源（支持增强数据）
- basic_info 组件 → 从 parsed_data.basic_info 提取
- work_experience 组件 → 从 parsed_data.work_experiences 提取所有字段（基础字段和详细字段）
  - **重要：工作经历必须按时间由近及远排序（最新的在前）**
  - 排序规则：当前工作（is_current=true）排在最前面，然后按start_date降序排列
  - 如果responsibilities/achievements是对象格式（包含raw和optimized），优先使用optimized字段
  - 如果存在_work_experiences_enhanced，可以使用增强信息
- education 组件 → 从 parsed_data.education 提取
- skills 组件 → 从 parsed_data.skills 提取
  - 如果technical是对象格式（包含explicit和inferred），合并使用
  - 如果存在_skills_enhanced，可以使用增强信息
- projects 组件 → 从 parsed_data.projects 提取
  - 如果description/achievements是对象格式（包含raw和optimized），优先使用optimized字段
  - 如果存在_projects_enhanced，可以使用增强信息

步骤3：字段匹配（使用模板元数据和增强数据）
- **优先使用字段元数据**：
  - 如果字段有 dataSource，直接使用指定的数据源路径
  - 如果字段有 synonyms，使用同义词列表进行匹配
  - 如果字段有 description 和 example，参考这些信息理解字段含义
  - 如果字段有 format，按照格式要求转换数据
- **智能选择增强数据**：
  - 对于描述性字段（如responsibilities、achievements、description），优先使用optimized版本
  - 对于数据字段（如company、position），使用raw版本（保证准确性）
  - 对于列表字段，可以融合raw和optimized，去除重复
- **智能匹配**：
  - 识别同义词和变体表达
  - 理解字段语义（如"起止时间"需要从 start_date 和 end_date 组合）
  - 处理数据格式（如时间格式统一、数组格式转换）
  - 从增强信息中提取隐含信息（如implicit_info中的team_size、business_domain）

步骤4：数据填充
- 按照模板要求的格式填充数据
- 保持数据完整性和准确性
- 处理缺失数据（留空或使用默认值）

**重要提示：**
1. **必须保持原模板的 components 数组顺序和结构完全不变**
2. **每个组件必须包含 data 字段**，格式如下：
   - work_experience 类型：data = {{"rows": [{{"period": "2020-01 - 2023-06", "company": "...", "position": "..."}}, ...]}}
   - education 类型：data = {{"rows": [{{"period": "2020-06", "school": "...", "major": "...", "education_level": "...", "degree": "..."}}, ...]}}
   - basic_info 类型：data = {{"name": "...", "phone": "...", "email": "...", "current_location": "...", ...}}
   - skills 类型：data = {{"technical": [...], "soft": [...], "languages": [...]}}
   - projects 类型：data = {{"rows": [...]}} 或 data = {{"items": [...]}}
   - 其他类型：data = {{"字段id": "字段值", ...}}
3. **字段匹配规则（支持增强数据）**：
   - **必须填充所有可用数据**：仔细检查 parsed_data 中的所有字段，确保不遗漏任何可用信息
   - **智能选择数据版本**：
     - responsibilities/achievements：如果是对象格式（包含raw和optimized），优先使用optimized版本
     - description（项目描述）：如果是对象格式，优先使用optimized版本
     - skills.technical：如果是对象格式（包含explicit和inferred），合并使用
     - 从implicit_info中提取隐含信息（如team_size、business_domain）
   - 识别同义词和变体表达
   - 基本信息字段从 basic_info 中提取（包括 name、phone、email、current_location、gender、birth_date 等所有字段）
   - 工作经历从 work_experiences 数组中提取（注意：period 需要组合 start_date 和 end_date）
   - **重要：工作经历必须按时间由近及远排序（最新的在前）**
     - 排序规则：当前工作（is_current=true）排在最前面，然后按start_date降序排列
   - 工作详情从 work_experiences 数组中提取详细字段（responsibilities、achievements、location 等）
     - 如果responsibilities是对象，使用optimized版本
     - 如果achievements是对象，使用optimized版本
     - 从implicit_info中提取team_size、business_domain等隐含信息
   - 教育背景从 education 数组中提取（**注意区分 education_level 和 degree**）
   - 技能从 skills 对象中提取（technical、soft、languages）
     - 如果technical是对象格式，合并explicit和inferred
   - **项目从 projects 数组中提取**（如果 parsed_data 中有 projects，必须填充到 projects 组件）
     - 如果description是对象格式，使用optimized版本
     - 如果achievements是对象格式，使用optimized版本
4. **数据格式要求**：
   - period 格式："YYYY-MM - YYYY-MM" 或 "YYYY-MM - 至今"
   - 如果是当前工作，end_date 为空，is_current 为 true
   - 数组字段保持数组格式
5. **教育背景字段区分**：
   - education_level（学历层次）：教育层次，如"本科"、"专科"、"高中"等
   - degree（学位）：学术学位，如"学士"、"硕士"、"博士"等
   - 两者不同，必须分别填充，不能混淆
6. **如果某个字段在简历数据中找不到，该字段留空或使用空字符串/空数组**
7. **输出格式必须与输入的模板结构完全相同**，只是每个组件增加了 data 字段
8. **完整性检查**：填充完成后，检查是否所有可用数据都已填充，特别是：
   - basic_info 中的所有字段（phone、email、current_location 等）
   - work_experiences 中的所有详细字段（responsibilities、achievements 等）
   - projects 数组中的所有项目
   - skills 对象中的所有技能类型

现在开始填充，直接输出填充后的完整模板结构（JSON格式），不要有任何其他文字说明："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            import time
            import asyncio
            match_start = time.time()
            logger.info(f"[DeepSeek填充] 开始，模板组件数: {len(template_structure.get('components', []))}")
            
            # 添加超时保护：最多等待180秒（3分钟）
            try:
                response = await asyncio.wait_for(
                    self.chat_completion(messages, temperature=0.1, max_tokens=4000),
                    timeout=180.0
                )
            except asyncio.TimeoutError:
                logger.error(f"[DeepSeek填充] AI调用超时（180秒），回退到直接映射")
                # 超时后回退到直接映射
                return self._direct_fill_template(template_structure, parsed_data)
            
            match_elapsed = time.time() - match_start
            logger.info(f"[DeepSeek填充] API调用成功，耗时: {match_elapsed:.2f}秒")
            logger.info(f"[DeepSeek填充] 响应长度: {len(response)}字符")
            
            filled_template = self._parse_json_response(response)
            logger.info(f"[DeepSeek填充] 解析成功，组件数: {len(filled_template.get('components', []))}")
            
            # 验证并合并回原始模板结构（保留 layout, config 等）
            final_template = template_structure.copy()
            final_template["components"] = []
            
            original_components = template_structure.get("components", [])
            filled_components = filled_template.get("components", [])
            
            # 按顺序合并：保留原始组件的所有属性，只更新 data 字段
            for i, orig_comp in enumerate(original_components):
                filled_comp = filled_components[i] if i < len(filled_components) else {}
                
                merged_comp = orig_comp.copy()
                # 如果 DeepSeek 返回了 data，使用它；否则保持原样
                if "data" in filled_comp:
                    # 清理data中的description字段，确保是字符串而不是数组
                    filled_data = filled_comp.get("data", {})
                    if isinstance(filled_data, dict):
                        # 如果是rows格式（如projects、work_experience）
                        if "rows" in filled_data and isinstance(filled_data["rows"], list):
                            for row in filled_data["rows"]:
                                if isinstance(row, dict):
                                    # 清理description相关字段
                                    for desc_key in ["description", "project_description", "project_content", "content"]:
                                        if desc_key in row:
                                            desc_value = row[desc_key]
                                            if isinstance(desc_value, list):
                                                row[desc_key] = ' '.join([str(d).strip() for d in desc_value if d and str(d).strip()])
                                            elif isinstance(desc_value, str):
                                                row[desc_key] = self._clean_text_for_fill(desc_value)
                                            else:
                                                row[desc_key] = self._clean_text_for_fill(str(desc_value)) if desc_value else ""
                        # 如果是items格式
                        elif "items" in filled_data and isinstance(filled_data["items"], list):
                            for item in filled_data["items"]:
                                if isinstance(item, dict) and "description" in item:
                                    desc_value = item["description"]
                                    # 统一规范化description字段
                                    desc_value = self._normalize_description_field(desc_value)
                                    # 清理特殊字符
                                    if desc_value:
                                        desc_value = self._clean_text_for_fill(desc_value)
                                    item["description"] = desc_value
                        # 如果是普通对象格式
                        else:
                            for desc_key in ["description", "project_description", "project_content", "content"]:
                                if desc_key in filled_data:
                                    desc_value = filled_data[desc_key]
                                    # 统一规范化description字段
                                    desc_value = self._normalize_description_field(desc_value)
                                    # 清理特殊字符
                                    if desc_value:
                                        desc_value = self._clean_text_for_fill(desc_value)
                                    filled_data[desc_key] = desc_value
                    merged_comp["data"] = filled_comp["data"]
                elif "data" not in merged_comp:
                    # 如果没有 data，根据类型初始化
                    if merged_comp.get("type") in ["work_experience", "education"]:
                        merged_comp["data"] = {"rows": []}
                    else:
                        merged_comp["data"] = {}
                
                final_template["components"].append(merged_comp)
            
            logger.info(f"[DeepSeek填充] 合并完成，最终组件数: {len(final_template.get('components', []))}")
            
            # 检查是否需要生成职业摘要和核心能力
            final_template = await self._generate_evaluation_if_needed(final_template, parsed_data)
            
            return final_template
            
        except Exception as e:
            logger.warning(f"[DeepSeek填充] DeepSeek填充失败: {e}，使用直接映射作为后备方案")
            # DeepSeek失败时，使用直接映射作为后备
            filled_template = self._direct_fill_template(template_structure, parsed_data)
            # 检查是否需要生成职业摘要和核心能力
            filled_template = await self._generate_evaluation_if_needed(filled_template, parsed_data)
            return filled_template

    async def match_template_fields(
        self, 
        parsed_data: Dict[str, Any], 
        template_fields: List[str]
    ) -> Dict[str, Any]:
        """
        将解析的数据智能匹配到模板字段
        返回格式: {"matches": {"field_name": "matched_value", ...}}
        """
        system_prompt = """你是一个专业的简历数据匹配专家。你的任务是将解析后的简历数据智能匹配到模板字段。

重要：你需要识别同义词！不同的表达方式但含义相同的字段应该匹配到同一个数据源。

匹配规则：
1. **同义词识别**：根据字段名称的语义相似度进行匹配，识别同义词
   - 例如："职位"、"岗位"、"工作名称"、"职务" 都表示 position
   - 例如："电话"、"手机"、"手机号"、"联系电话" 都表示 phone
   - 例如："公司"、"公司名称"、"企业"、"单位" 都表示 company
   - 例如："学校"、"学校名称"、"院校"、"毕业院校" 都表示 school
   - 例如："专业"、"专业名称"、"所学专业" 都表示 major
   - 例如："工作职责"、"职责"、"工作内容"、"主要工作" 都表示 responsibilities
   - 例如："工作业绩"、"业绩"、"工作成果"、"成就" 都表示 achievements

2. **数据提取**：从解析数据中提取对应的值
   - 基本信息字段从 basic_info 中提取（如 basic_info.name, basic_info.phone）
   - 工作经历字段从 work_experiences 数组中提取（如 work_experiences[0].company、work_experiences[0].position、work_experiences[0].responsibilities 等）
   - **重要：工作经历必须按时间由近及远排序（最新的在前）**
     - 排序规则：当前工作（is_current=true）排在最前面，然后按start_date降序排列
   - 所有工作经历相关字段（基础字段和详细字段）都应该填充到 work_experience 组件中
   - 教育背景字段从 education 数组中提取（如 education[0].school）
   - 技能字段从 skills 对象中提取
   - 项目字段从 projects 数组中提取

3. **匹配策略**：
   - 优先进行语义匹配（识别同义词）
   - 如果找不到匹配值，该字段留空
   - 对于嵌套字段（如basic_info.name），需要从正确的路径提取
   - 数组类型字段（如work_experiences）保持原样，不需要匹配

4. **常见字段映射**：
   - 姓名类：name, 姓名, 名字 → basic_info.name
   - 电话类：phone, 电话, 手机, 手机号 → basic_info.phone
   - 邮箱类：email, 邮箱, 电子邮件 → basic_info.email
   - 职位类：position, 职位, 岗位, 工作名称 → work_experiences[].position
   - 公司类：company, 公司, 公司名称, 企业 → work_experiences[].company
   - 学校类：school, 学校, 学校名称, 院校 → education[].school
   - 专业类：major, 专业, 专业名称 → education[].major

输出要求：
- 必须返回有效的JSON格式
- 格式为：{"matches": {"字段名": "匹配值", ...}}
- 只输出JSON，不要有任何其他文字说明
- 匹配值应该是从简历数据中提取的实际值，不是字段名本身
"""

        # 构建简历数据摘要（避免token过多）
        # 注意：摘要只用于智能匹配字段名，不影响最终数据填充
        # 最终填充时，前端会直接从完整的 parsed_data 中提取所有数据
        resume_summary = {
            "basic_info": parsed_data.get("basic_info", {}),
            "work_experiences_count": len(parsed_data.get("work_experiences", [])),
            "education_count": len(parsed_data.get("education", [])),
            "skills": parsed_data.get("skills", {}),
            "projects_count": len(parsed_data.get("projects", [])),
        }
        
        # 对于匹配字段，我们只需要知道有哪些字段，不需要完整数据
        # 但如果数量少，包含完整数据有助于更准确的匹配
        if resume_summary["work_experiences_count"] <= 5:
            resume_summary["work_experiences"] = parsed_data.get("work_experiences", [])
        if resume_summary["education_count"] <= 5:
            resume_summary["education"] = parsed_data.get("education", [])
        
        parsed_json = json.dumps(resume_summary, ensure_ascii=False, indent=2)
        fields_json = json.dumps(template_fields, ensure_ascii=False, indent=2)
        
        # 解析字段格式：可能是 "field_id (label)" 或直接是字段名
        parsed_fields = []
        field_id_to_label = {}
        for field in template_fields:
            # 处理格式：field_id (label)
            if ' (' in field and field.endswith(')'):
                parts = field.rsplit(' (', 1)
                field_id = parts[0]
                label = parts[1].rstrip(')')
                parsed_fields.append(field_id)
                field_id_to_label[field_id] = label
            else:
                parsed_fields.append(field)
        
        # 为每个字段提供同义词提示，帮助AI识别
        field_hints = []
        for field in parsed_fields:
            label = field_id_to_label.get(field, field)
            synonyms = get_field_synonyms(field) + get_field_synonyms(label)
            # 去重
            synonyms = list(dict.fromkeys(synonyms))
            if len(synonyms) > 1:
                field_hints.append(f"- 字段 '{field}' (标签: '{label}') 的同义词包括: {', '.join(synonyms[:6])}")
        
        hints_text = "\n".join(field_hints) if field_hints else "（所有字段都是标准字段名）"
        
        # 使用解析后的字段列表
        fields_json = json.dumps(parsed_fields, ensure_ascii=False, indent=2)
        
        user_prompt = f"""请将以下简历数据匹配到模板字段。

简历数据（已解析）:
{parsed_json}

需要匹配的模板字段列表（字段ID）:
{fields_json}

字段标签映射（帮助你理解字段含义）:
{json.dumps(field_id_to_label, ensure_ascii=False, indent=2) if field_id_to_label else "（无标签映射）"}

字段同义词提示（帮助你识别不同表达）:
{hints_text}

匹配要求：
1. **识别同义词**：即使字段名不同，只要含义相同，就应该匹配到同一个数据源
   - 例如：模板字段是"职位"，应该匹配到 work_experiences[].position
   - 例如：模板字段是"岗位"，也应该匹配到 work_experiences[].position（与"职位"相同）
   - 例如：模板字段是"工作名称"，也应该匹配到 work_experiences[].position（与"职位"相同）

2. **数据提取路径**：
   - 基本信息字段：从 basic_info 对象中提取
   - 工作经历字段：从 work_experiences 数组中提取（通常取第一个，除非有特殊说明）
   - **重要：工作经历必须按时间由近及远排序（最新的在前）**
     - 排序规则：当前工作（is_current=true）排在最前面，然后按start_date降序排列
   - 教育背景字段：从 education 数组中提取（通常取第一个，除非有特殊说明）
   - 技能字段：从 skills 对象中提取
   - 项目字段：从 projects 数组中提取

3. **输出格式**（必须是有效的JSON）:
{{
  "matches": {{
    "字段名1": "从简历数据中提取的实际值1",
    "字段名2": "从简历数据中提取的实际值2",
    ...
  }}
}}

示例：
- 模板字段 "name" 或 "姓名" → 从 basic_info.name 提取 → 输出实际姓名（如"张三"）
- 模板字段 "phone" 或 "电话" 或 "手机" → 从 basic_info.phone 提取 → 输出实际电话（如"138-1234-5678"）
- 模板字段 "position" 或 "职位" 或 "岗位" → 从 work_experiences[0].position 提取 → 输出实际职位（如"高级工程师"）
- 模板字段 "company" 或 "公司" 或 "公司名称" → 从 work_experiences[0].company 提取 → 输出实际公司名（如"某科技有限公司"）
- 模板字段 "school" 或 "学校" 或 "院校" → 从 education[0].school 提取 → 输出实际学校名（如"清华大学"）

现在请开始匹配，只输出JSON结果（不要有任何其他文字）："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            import time
            match_start = time.time()
            logger.info(f"[DeepSeek匹配] 开始，模板字段数: {len(template_fields)}, 消息数: {len(messages)}")
            logger.info(f"[DeepSeek匹配] 调用chat_completion，超时设置: {self.timeout}秒")
            
            response = await self.chat_completion(messages, temperature=0.1, max_tokens=2000)
            
            match_elapsed = time.time() - match_start
            logger.info(f"[DeepSeek匹配] API调用成功，耗时: {match_elapsed:.2f}秒")
            logger.info(f"[DeepSeek匹配] 响应长度: {len(response)}字符，前200字符: {response[:200]}...")
            
            result = self._parse_json_response(response)
            
            # 确保返回格式正确，并处理字段ID映射
            matches_dict = {}
            if isinstance(result, dict) and "matches" in result:
                matches_dict = result.get("matches", {})
            elif isinstance(result, dict):
                matches_dict = result
            
            # 将匹配结果中的字段名映射回原始字段ID
            # 因为AI可能返回字段标签或同义词，需要映射回ID
            normalized_matches = {}
            for field_id in parsed_fields:
                label = field_id_to_label.get(field_id, field_id)
                # 尝试多种可能的key
                possible_keys = [field_id, label, f"{field_id} ({label})"]
                for key in possible_keys:
                    if key in matches_dict:
                        normalized_matches[field_id] = matches_dict[key]
                        break
                # 如果都没找到，尝试通过同义词匹配
                if field_id not in normalized_matches:
                    synonyms = get_field_synonyms(field_id) + get_field_synonyms(label)
                    for syn in synonyms:
                        if syn in matches_dict:
                            normalized_matches[field_id] = matches_dict[syn]
                            break
            
            logger.info(f"匹配成功，原始匹配数: {len(matches_dict)}, 标准化后: {len(normalized_matches)}")
            return {"matches": normalized_matches}
                
        except Exception as e:
            logger.error(f"字段匹配失败: {e}", exc_info=True)
            return {"matches": {}}

    def _normalize_description_field(self, desc_value: Any) -> str:
        """
        统一规范化description字段：确保返回字符串格式
        处理各种可能的输入格式：字符串、数组、对象、None等
        """
        if desc_value is None:
            return ''
        
        # 如果是数组，合并成字符串
        if isinstance(desc_value, list):
            # 过滤空值并合并
            parts = [str(d).strip() for d in desc_value if d and str(d).strip()]
            return ' '.join(parts) if parts else ''
        
        # 如果是对象格式（包含raw和optimized）
        if isinstance(desc_value, dict):
            # 优先使用optimized，如果没有则使用raw
            return desc_value.get('optimized', desc_value.get('raw', ''))
        
        # 如果是字符串，直接返回
        if isinstance(desc_value, str):
            return desc_value
        
        # 其他类型，转换为字符串
        return str(desc_value) if desc_value else ''
    
    def _clean_text_for_fill(self, text: str) -> str:
        """
        清理文本中的特殊字符，避免在填充时导致文本被不合理拆分
        移除：↓、↩、以及其他可能导致格式问题的特殊字符
        处理换行符：将句子中间的单个换行符替换为空格，只保留段落分隔
        """
        if not text or not isinstance(text, str):
            return text if text else ''
        
        # 移除特殊字符：↓、↩、以及其他格式标记字符
        special_chars = [
            '\u2193',  # ↓
            '\u21A9',  # ↩
            '\u21B2',  # ↲
            '\u21B3',  # ↳
            '\u2191',  # ↑
            '\u2192',  # →
            '\u2190',  # ←
            '\u21E8',  # ⇨
            '\u21E6',  # ⇦
            '\u21E7',  # ⇧
            '\u21E9',  # ⇩
        ]
        
        cleaned = text
        for char in special_chars:
            cleaned = cleaned.replace(char, ' ')
        
        # 处理换行符：将句子中间的单个换行符替换为空格
        # 1. 先处理多个连续换行（段落分隔），保留为双换行
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
        # 2. 将单个换行符（前后不是换行符的）替换为空格
        # 但保留项目符号后的换行（如 "● " 或 "• " 后的换行）
        # 先标记项目符号后的换行
        cleaned = re.sub(r'([●•·])\s*\n\s*', r'\1 ', cleaned)
        # 将剩余的单个换行符替换为空格
        cleaned = re.sub(r'(?<!\n)\n(?!\n)', ' ', cleaned)
        # 3. 移除多余的连续空格
        cleaned = re.sub(r' +', ' ', cleaned)
        # 4. 移除行尾的空格
        cleaned = re.sub(r' +$', '', cleaned, flags=re.MULTILINE)
        # 5. 清理段落分隔周围的空格
        cleaned = re.sub(r' \n\n ', '\n\n', cleaned)
        cleaned = re.sub(r'\n\n +', '\n\n', cleaned)
        cleaned = re.sub(r' +\n\n', '\n\n', cleaned)
        
        return cleaned.strip()

    def _direct_fill_template(
        self, 
        template_structure: Dict[str, Any], 
        parsed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        直接映射填充模板（不依赖DeepSeek，作为后备方案）
        根据组件类型和字段ID，直接从parsed_data中提取数据
        """
        filled_template = template_structure.copy()
        filled_template["components"] = []
        
        for comp in template_structure.get("components", []):
            filled_comp = comp.copy()
            comp_type = comp.get("type")
            
            # 根据组件类型填充数据
            if comp_type == "basic_info":
                basic_info = parsed_data.get("basic_info", {})
                filled_comp["data"] = {}
                for field in comp.get("fields", []):
                    field_id = field.get("id") or field.get("field") or field.get("name")
                    if not field_id:
                        continue
                    
                    # 尝试直接匹配
                    if field_id in basic_info:
                        filled_comp["data"][field_id] = basic_info[field_id]
                    else:
                        # 尝试标准化匹配
                        normalized_id = normalize_field_name(field_id)
                        if normalized_id != field_id and normalized_id in basic_info:
                            filled_comp["data"][field_id] = basic_info[normalized_id]
                        else:
                            # 尝试同义词匹配
                            synonyms = get_field_synonyms(field_id)
                            matched = False
                            for synonym in synonyms:
                                if synonym in basic_info:
                                    filled_comp["data"][field_id] = basic_info[synonym]
                                    matched = True
                                    break
                            if not matched:
                                # 特殊字段映射
                                if field_id == "current_location":
                                    # 尝试从 location 或 work_location 获取
                                    filled_comp["data"][field_id] = basic_info.get("location", "") or basic_info.get("work_location", "")
                                elif field_id in ["website", "website_url"]:
                                    # 网站字段可能有多种命名
                                    filled_comp["data"][field_id] = basic_info.get("website", "") or basic_info.get("website_url", "")
                                elif field_id in ["linkedin", "linkedin_url"]:
                                    # LinkedIn字段可能有多种命名
                                    filled_comp["data"][field_id] = basic_info.get("linkedin", "") or basic_info.get("linkedin_url", "")
                                elif field_id in ["work_location", "current_work_location"]:
                                    # 工作地点字段
                                    filled_comp["data"][field_id] = basic_info.get("work_location", "") or basic_info.get("location", "")
                                elif field_id in ["birthday", "birth_date"]:
                                    # 生日字段可能有多种命名
                                    filled_comp["data"][field_id] = basic_info.get("birthday", "") or basic_info.get("birth_date", "") or basic_info.get("出生日期", "") or basic_info.get("出生年月", "")
                                elif field_id == "gender":
                                    # 性别字段可能有多种命名
                                    filled_comp["data"][field_id] = basic_info.get("gender", "") or basic_info.get("性别", "") or basic_info.get("性", "")
                                else:
                                    filled_comp["data"][field_id] = ""
            
            elif comp_type == "work_experience":
                # 合并后的工作经历组件：包含所有字段（基础字段和详细字段）
                work_exps = parsed_data.get("work_experiences", [])
                # 使用统一的排序方法：按时间由近及远排序（当前工作优先，然后按start_date降序）
                work_exps_sorted = self._sort_work_experiences(work_exps)
                work_enhanced = parsed_data.get("_work_experiences_enhanced", {})
                
                rows = []
                for idx, exp in enumerate(work_exps_sorted):
                    # 确保返回完整数据，包含所有字段（基础字段和详细字段）
                    row = {
                        # 基础字段（用于表格显示）
                        "period": f"{self._format_date(exp.get('start_date', ''))} - {'至今' if exp.get('is_current') else (self._format_date(exp.get('end_date', '')) or '')}",
                        "company": exp.get("company", ""),
                        "position": exp.get("position", ""),
                        # 详细字段（用于详细卡片显示）
                        "report_to": exp.get("report_to", ""),
                        "team_size": exp.get("team_size", "") or exp.get("implicit_info", {}).get("team_size", ""),
                        "location": exp.get("location", "") or exp.get("work_location", ""),
                        "reason_for_leaving": exp.get("reason_for_leaving", ""),
                        "project_experience": exp.get("project_experience", ""),
                        # 确保所有时间字段都存在
                        "start_date": self._format_date(exp.get("start_date", "")),
                        "end_date": self._format_date(exp.get("end_date", "")),
                        "is_current": exp.get("is_current", False),
                    }
                    
                    # 处理responsibilities：优先使用optimized，如果没有则使用raw或数组
                    if idx in work_enhanced and "responsibilities" in work_enhanced[idx]:
                        resp_obj = work_enhanced[idx]["responsibilities"]
                        row["responsibilities"] = resp_obj.get("optimized", resp_obj.get("raw", []))
                    elif isinstance(exp.get("responsibilities"), dict):
                        resp_obj = exp["responsibilities"]
                        row["responsibilities"] = resp_obj.get("optimized", resp_obj.get("raw", []))
                    else:
                        row["responsibilities"] = exp.get("responsibilities", []) if isinstance(exp.get("responsibilities"), list) else []
                    
                    # 处理achievements：优先使用optimized，如果没有则使用raw或数组
                    if idx in work_enhanced and "achievements" in work_enhanced[idx]:
                        ach_obj = work_enhanced[idx]["achievements"]
                        row["achievements"] = ach_obj.get("optimized", ach_obj.get("raw", []))
                    elif isinstance(exp.get("achievements"), dict):
                        ach_obj = exp["achievements"]
                        row["achievements"] = ach_obj.get("optimized", ach_obj.get("raw", []))
                    else:
                        row["achievements"] = exp.get("achievements", []) if isinstance(exp.get("achievements"), list) else []
                    
                    # 处理skills_used：合并explicit和implicit
                    if idx in work_enhanced and "skills_used" in work_enhanced[idx]:
                        skills_obj = work_enhanced[idx]["skills_used"]
                        row["skills_used"] = (skills_obj.get("explicit", []) + skills_obj.get("implicit", []))
                    elif isinstance(exp.get("skills_used"), dict):
                        skills_obj = exp["skills_used"]
                        row["skills_used"] = (skills_obj.get("explicit", []) + skills_obj.get("implicit", []))
                    else:
                        row["skills_used"] = exp.get("skills_used", []) if isinstance(exp.get("skills_used"), list) else []
                    
                    # 保留原始数据的所有字段
                    row.update(exp)
                    rows.append(row)
                
                filled_comp["data"] = {"rows": rows}
            
            elif comp_type == "education":
                educations = parsed_data.get("education", [])

                def _build_edu_period(entry: Dict[str, Any]) -> str:
                    start = self._format_date(entry.get("start_date") or "")
                    end = self._format_date(entry.get("end_date") or entry.get("graduation_date") or "")
                    if start and end:
                        return f"{start} - {end if end else '至今'}"
                    if start and not end and entry.get("is_current"):
                        return f"{start} - 至今"
                    if start:
                        return start
                    if end:
                        return end
                    # 如果period已存在，也需要格式化
                    period = entry.get("period", "")
                    if period and '-' in period:
                        # 处理格式如 "2020-01 - 2023-06"
                        if ' - ' in period:
                            parts = period.split(' - ')
                            return f"{self._format_date(parts[0].strip())} - {parts[1].strip() if parts[1].strip() != '至今' else '至今'}"
                        else:
                            return self._format_date(period)
                    return period

                filled_comp["data"] = {
                    "rows": [{
                        "period": _build_edu_period(edu),
                        "start_date": self._format_date(edu.get("start_date", "")),
                        "end_date": self._format_date(edu.get("end_date", "") or edu.get("graduation_date", "")),
                        "school": edu.get("school", ""),
                        "major": edu.get("major", ""),
                        # 明确区分：education_level 是学历层次，degree 是学位
                        "education_level": edu.get("education_level", "") or edu.get("degree_level", ""),
                        "degree": edu.get("degree", ""),
                        "remark": edu.get("remark", ""),
                        **edu
                    } for edu in educations]
                }
            
            elif comp_type == "skills":
                skills = parsed_data.get("skills", {})
                skills_enhanced = parsed_data.get("_skills_enhanced", {})
                filled_comp["data"] = {}
                fields = comp.get("fields", [])
                
                # 记录日志：检查实际数据
                logger.info(f"[直接填充] skills组件 - parsed_data中的skills字段: {list(skills.keys())}")
                logger.info(f"[直接填充] skills组件 - 模板中的fields: {[f.get('id') or f.get('field') or f.get('name') for f in fields]}")
                
                # 如果模板有fields配置，按fields填充
                if fields:
                    for field in fields:
                        field_id = field.get("id") or field.get("field") or field.get("name")
                        if not field_id:
                            continue
                        
                        # 处理technical技能：合并explicit和inferred
                        if field_id in ["technical", "technical_ability"]:
                            if "technical" in skills_enhanced:
                                tech_obj = skills_enhanced["technical"]
                                filled_comp["data"][field_id] = (tech_obj.get("explicit", []) + tech_obj.get("inferred", []))
                            elif isinstance(skills.get("technical"), dict):
                                tech_obj = skills["technical"]
                                filled_comp["data"][field_id] = (tech_obj.get("explicit", []) + tech_obj.get("inferred", []))
                            elif "technical" in skills:
                                filled_comp["data"][field_id] = skills["technical"]
                            elif "technical_ability" in skills:
                                filled_comp["data"][field_id] = skills["technical_ability"]
                            else:
                                filled_comp["data"][field_id] = []
                            logger.info(f"[直接填充] skills组件 - 字段 {field_id}: 值: {filled_comp['data'][field_id]}")
                        # 处理soft技能
                        elif field_id in ["soft", "soft_skills"]:
                            if "soft" in skills:
                                filled_comp["data"][field_id] = skills["soft"]
                            elif "soft_skills" in skills:
                                filled_comp["data"][field_id] = skills["soft_skills"]
                            else:
                                filled_comp["data"][field_id] = []
                            logger.info(f"[直接填充] skills组件 - 字段 {field_id}: 值: {filled_comp['data'][field_id]}")
                        # 处理languages技能
                        elif field_id in ["languages", "language_ability"]:
                            if "languages" in skills:
                                filled_comp["data"][field_id] = skills["languages"]
                            elif "language_ability" in skills:
                                filled_comp["data"][field_id] = skills["language_ability"]
                            else:
                                filled_comp["data"][field_id] = []
                            logger.info(f"[直接填充] skills组件 - 字段 {field_id}: 值: {filled_comp['data'][field_id]}")
                        # 其他字段直接匹配
                        elif field_id in skills:
                            filled_comp["data"][field_id] = skills[field_id]
                            logger.info(f"[直接填充] skills组件 - 字段 {field_id}: 直接匹配成功，值: {skills[field_id]}")
                        else:
                            filled_comp["data"][field_id] = []
                            logger.warning(f"[直接填充] skills组件 - 字段 {field_id}: 未找到匹配的数据源")
                else:
                    # 如果模板没有fields配置，填充所有可用的skills字段
                    logger.info(f"[直接填充] skills组件 - 模板没有fields配置，填充所有可用字段: {list(skills.keys())}")
                    for key, value in skills.items():
                        # 如果是technical且是对象格式，合并explicit和inferred
                        if key == "technical" and isinstance(value, dict):
                            filled_comp["data"][key] = (value.get("explicit", []) + value.get("inferred", []))
                        else:
                            filled_comp["data"][key] = value
                
                logger.info(f"[直接填充] skills组件 - 最终填充的数据: {filled_comp['data']}")
            
            elif comp_type == "projects":
                projects = parsed_data.get("projects", [])
                projects_enhanced = parsed_data.get("_projects_enhanced", {})
                if not isinstance(projects, list):
                    projects = []
                
                logger.info(f"[直接填充] projects组件 - 解析数据中的项目数量: {len(projects)}")
                logger.info(f"[直接填充] projects组件 - 解析数据中的项目示例: {projects[0] if projects else '无'}")
                
                fields = comp.get("fields", [])
                table_columns = comp.get("config", {}).get("tableColumns", [])
                logger.info(f"[直接填充] projects组件 - 模板fields配置: {[f.get('id') or f.get('field') or f.get('name') for f in fields] if fields else '无'}")
                logger.info(f"[直接填充] projects组件 - 模板tableColumns配置: {[c.get('field') or c.get('id') or c.get('name') for c in table_columns] if table_columns else '无'}")
                
                # 检查模板配置，确定使用 rows 还是 items
                if comp.get("config", {}).get("showTable") or (fields and len(fields) > 0) or (table_columns and len(table_columns) > 0):
                    # 表格模式，使用 rows
                    rows = []
                    for idx, p in enumerate(projects):
                        row = {}
                        if fields:
                            # 如果模板有fields配置，按fields填充
                            for field in fields:
                                field_id = field.get("id") or field.get("field") or field.get("name")
                                if not field_id:
                                    continue
                                # 字段映射，优先使用optimized版本
                                if field_id == "project_name":
                                    row[field_id] = p.get("name", "") or p.get("project_name", "")
                                elif field_id == "project_description":
                                    # 优先使用optimized版本
                                    desc_value = ""
                                    if idx in projects_enhanced and "description" in projects_enhanced[idx]:
                                        desc_obj = projects_enhanced[idx]["description"]
                                        desc_value = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    elif isinstance(p.get("description"), dict):
                                        desc_obj = p["description"]
                                        desc_value = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    else:
                                        desc_value = p.get("description", "") or p.get("content", "") or p.get("project_description", "")
                                    
                                    # 确保description是字符串，如果是数组则合并
                                    if isinstance(desc_value, list):
                                        desc_value = ' '.join([str(d).strip() for d in desc_value if d and str(d).strip()])
                                    elif not isinstance(desc_value, str):
                                        desc_value = str(desc_value) if desc_value else ""
                                    # 清理特殊字符
                                    if desc_value:
                                        desc_value = self._clean_text_for_fill(desc_value)
                                    row[field_id] = desc_value
                                elif field_id == "project_content":
                                    # 优先使用optimized版本
                                    if idx in projects_enhanced and "description" in projects_enhanced[idx]:
                                        desc_obj = projects_enhanced[idx]["description"]
                                        row[field_id] = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    elif isinstance(p.get("description"), dict):
                                        desc_obj = p["description"]
                                        row[field_id] = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    else:
                                        row[field_id] = p.get("description", "") or p.get("content", "") or p.get("project_content", "")
                                elif field_id == "project_role":
                                    # project_role 在模板中表示"项目职责"，应该从 responsibilities 获取，不是 role
                                    resp_value = p.get("responsibilities", [])
                                    if isinstance(resp_value, list):
                                        row[field_id] = "；".join([str(r).strip() for r in resp_value if r and str(r).strip()]) if resp_value else ""
                                    else:
                                        row[field_id] = str(resp_value) if resp_value else ""
                                elif field_id == "project_achievements":
                                    # 优先使用optimized版本
                                    if idx in projects_enhanced and "achievements" in projects_enhanced[idx]:
                                        ach_obj = projects_enhanced[idx]["achievements"]
                                        row[field_id] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    elif isinstance(p.get("achievements"), dict):
                                        ach_obj = p["achievements"]
                                        row[field_id] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    else:
                                        row[field_id] = p.get("achievements", "") or p.get("outcome", "") or p.get("project_achievements", "")
                                elif field_id == "project_outcome":
                                    # 优先使用optimized版本
                                    if idx in projects_enhanced and "achievements" in projects_enhanced[idx]:
                                        ach_obj = projects_enhanced[idx]["achievements"]
                                        row[field_id] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    elif isinstance(p.get("achievements"), dict):
                                        ach_obj = p["achievements"]
                                        row[field_id] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    else:
                                        row[field_id] = p.get("outcome", "") or p.get("project_outcome", "")
                                else:
                                    # 直接匹配
                                    row[field_id] = p.get(field_id, "")
                        elif table_columns:
                            # 如果模板只有tableColumns配置，按tableColumns的field填充
                            for col in table_columns:
                                col_field = col.get("field") or col.get("id") or col.get("name")
                                if not col_field:
                                    continue
                                # 字段映射，优先使用optimized版本
                                if col_field == "project_name" or col_field == "name":
                                    row[col_field] = p.get("name", "") or p.get("project_name", "")
                                elif col_field == "project_description" or col_field == "description":
                                    desc_value = ""
                                    if idx in projects_enhanced and "description" in projects_enhanced[idx]:
                                        desc_obj = projects_enhanced[idx]["description"]
                                        desc_value = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    elif isinstance(p.get("description"), dict):
                                        desc_obj = p["description"]
                                        desc_value = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    else:
                                        desc_value = p.get("description", "") or p.get("content", "") or p.get("project_description", "")
                                    
                                    # 确保description是字符串，如果是数组则合并
                                    if isinstance(desc_value, list):
                                        desc_value = ' '.join([str(d).strip() for d in desc_value if d and str(d).strip()])
                                    elif not isinstance(desc_value, str):
                                        desc_value = str(desc_value) if desc_value else ""
                                    # 清理特殊字符
                                    if desc_value:
                                        desc_value = self._clean_text_for_fill(desc_value)
                                    row[col_field] = desc_value
                                elif col_field == "project_content" or col_field == "content":
                                    if idx in projects_enhanced and "description" in projects_enhanced[idx]:
                                        desc_obj = projects_enhanced[idx]["description"]
                                        row[col_field] = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    elif isinstance(p.get("description"), dict):
                                        desc_obj = p["description"]
                                        row[col_field] = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                    else:
                                        desc_value = p.get("description", "") or p.get("content", "") or p.get("project_content", "")
                                    
                                    # 确保description是字符串，如果是数组则合并
                                    if isinstance(desc_value, list):
                                        desc_value = ' '.join([str(d).strip() for d in desc_value if d and str(d).strip()])
                                    elif not isinstance(desc_value, str):
                                        desc_value = str(desc_value) if desc_value else ""
                                    # 清理特殊字符
                                    if desc_value:
                                        desc_value = self._clean_text_for_fill(desc_value)
                                    row[col_field] = desc_value
                                elif col_field == "project_role":
                                    # project_role 在模板中表示"项目职责"，应该从 responsibilities 获取，不是 role
                                    resp_value = p.get("responsibilities", [])
                                    if isinstance(resp_value, list):
                                        row[col_field] = "；".join([str(r).strip() for r in resp_value if r and str(r).strip()]) if resp_value else ""
                                    else:
                                        row[col_field] = str(resp_value) if resp_value else ""
                                elif col_field == "role":
                                    # role 字段表示项目角色（如"KAM"、"项目经理"等），不是职责
                                    row[col_field] = p.get("role", "") or p.get("project_role", "")
                                elif col_field == "project_achievements" or col_field == "achievements":
                                    if idx in projects_enhanced and "achievements" in projects_enhanced[idx]:
                                        ach_obj = projects_enhanced[idx]["achievements"]
                                        row[col_field] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    elif isinstance(p.get("achievements"), dict):
                                        ach_obj = p["achievements"]
                                        row[col_field] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    else:
                                        row[col_field] = p.get("achievements", "") or p.get("outcome", "") or p.get("project_achievements", "")
                                elif col_field == "project_outcome" or col_field == "outcome":
                                    if idx in projects_enhanced and "achievements" in projects_enhanced[idx]:
                                        ach_obj = projects_enhanced[idx]["achievements"]
                                        row[col_field] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    elif isinstance(p.get("achievements"), dict):
                                        ach_obj = p["achievements"]
                                        row[col_field] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                                    else:
                                        row[col_field] = p.get("outcome", "") or p.get("project_outcome", "")
                                else:
                                    # 直接匹配
                                    row[col_field] = p.get(col_field, "")
                        else:
                            # 如果模板没有fields和tableColumns配置，使用默认字段
                            # 优先使用optimized版本
                            description = ""
                            if idx in projects_enhanced and "description" in projects_enhanced[idx]:
                                desc_obj = projects_enhanced[idx]["description"]
                                description = desc_obj.get("optimized", desc_obj.get("raw", ""))
                            elif isinstance(p.get("description"), dict):
                                desc_obj = p["description"]
                                description = desc_obj.get("optimized", desc_obj.get("raw", ""))
                            else:
                                description = p.get("description", "") or p.get("content", "")
                            
                            # 统一规范化description字段
                            description = self._normalize_description_field(description)
                            # 清理特殊字符
                            if description:
                                description = self._clean_text_for_fill(description)
                            
                            achievements = ""
                            if idx in projects_enhanced and "achievements" in projects_enhanced[idx]:
                                ach_obj = projects_enhanced[idx]["achievements"]
                                achievements = ach_obj.get("optimized", ach_obj.get("raw", ""))
                            elif isinstance(p.get("achievements"), dict):
                                ach_obj = p["achievements"]
                                achievements = ach_obj.get("optimized", ach_obj.get("raw", ""))
                            else:
                                achievements = p.get("achievements", "") or p.get("outcome", "")
                            
                            # project_role 在模板中表示"项目职责"，应该从 responsibilities 获取，不是 role
                            resp_value = p.get("responsibilities", [])
                            if isinstance(resp_value, list):
                                project_role_str = "；".join([str(r).strip() for r in resp_value if r and str(r).strip()]) if resp_value else ""
                            else:
                                project_role_str = str(resp_value) if resp_value else ""
                            
                            row = {
                                "project_name": p.get("name", ""),
                                "project_description": description,
                                "project_content": description,
                                "project_role": project_role_str,  # 项目职责，从 responsibilities 获取
                                "project_achievements": achievements,
                                "project_outcome": achievements,
                                **p
                            }
                        rows.append(row)
                    logger.info(f"[直接填充] projects组件 - 填充后的rows数量: {len(rows)}")
                    logger.info(f"[直接填充] projects组件 - 填充后的rows示例: {rows[0] if rows else '无'}")
                    filled_comp["data"] = {"rows": rows}
                else:
                    # 列表模式，使用 items（也需要处理optimized）
                    normalized_items = []
                    for idx, p in enumerate(projects):
                        item = p.copy()
                        # 处理description和achievements的optimized版本
                        if idx in projects_enhanced:
                            if "description" in projects_enhanced[idx]:
                                desc_obj = projects_enhanced[idx]["description"]
                                desc_value = desc_obj.get("optimized", desc_obj.get("raw", ""))
                                # 统一规范化description字段
                                desc_value = self._normalize_description_field(desc_value)
                                # 清理特殊字符
                                if desc_value:
                                    desc_value = self._clean_text_for_fill(desc_value)
                                item["description"] = desc_value
                            if "achievements" in projects_enhanced[idx]:
                                ach_obj = projects_enhanced[idx]["achievements"]
                                item["achievements"] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                        elif isinstance(p.get("description"), dict):
                            desc_obj = p["description"]
                            desc_value = desc_obj.get("optimized", desc_obj.get("raw", ""))
                            # 统一规范化description字段
                            desc_value = self._normalize_description_field(desc_value)
                            # 清理特殊字符
                            if desc_value:
                                desc_value = self._clean_text_for_fill(desc_value)
                            item["description"] = desc_value
                        elif isinstance(p.get("achievements"), dict):
                            ach_obj = p["achievements"]
                            item["achievements"] = ach_obj.get("optimized", ach_obj.get("raw", ""))
                        else:
                            # 如果description不是对象，也需要规范化
                            if "description" in p:
                                desc_value = self._normalize_description_field(p["description"])
                                if desc_value:
                                    desc_value = self._clean_text_for_fill(desc_value)
                                item["description"] = desc_value
                        normalized_items.append(item)
                    logger.info(f"[直接填充] projects组件 - 使用列表模式，items数量: {len(normalized_items)}")
                    filled_comp["data"] = {"items": normalized_items}
            
            elif comp_type in ["recommended_jobs", "evaluation", "salary"]:
                data_key = comp_type
                if data_key in parsed_data:
                    filled_comp["data"] = parsed_data[data_key]
                else:
                    filled_comp["data"] = {}
            else:
                filled_comp["data"] = {}
            
            filled_template["components"].append(filled_comp)
        
        logger.info(f"[直接映射] 填充完成，组件数: {len(filled_template.get('components', []))}")
        return filled_template

# 全局服务实例（不传入db_session，使用环境变量，兼容开发环境）
# 在生产环境中，API端点会创建带db_session的实例
llm_service = LLMService()

# 向后兼容：保留旧的实例名
deepseek_service = llm_service
DeepSeekService = LLMService  # 类别名