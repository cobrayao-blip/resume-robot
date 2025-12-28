"""
LLM 服务测试
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.llm_service import LLMService


class TestLLMService:
    """LLM 服务测试"""
    
    def test_is_provider_enabled_default(self):
        """测试 provider 启用状态（默认启用）"""
        service = LLMService()
        # 没有数据库会话时，默认启用
        assert service._is_provider_enabled("deepseek", None) is True
    
    @pytest.mark.asyncio
    async def test_chat_completion_with_mock(self):
        """测试 chat_completion（使用 mock）"""
        service = LLMService()
        
        # Mock httpx 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Test response"
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            # 设置 API key（避免认证错误）
            service.api_key = "test_key"
            service.base_url = "https://api.test.com/v1"
            service.model_name = "test-model"
            
            messages = [{"role": "user", "content": "Hello"}]
            result = await service.chat_completion(messages)
            
            assert result == "Test response"
            mock_post.assert_called_once()
    
    def test_provider_fallback_logic(self, db_session):
        """测试 provider fallback 逻辑"""
        service = LLMService(db_session=db_session)
        
        # 测试 deepseek 关闭，豆包开启的情况
        from app.services.config_service import ConfigService
        
        # 设置 deepseek 关闭
        ConfigService.set_setting(
            db=db_session,
            key="llm.deepseek.enabled",
            value="false",
            category="llm"
        )
        
        # 设置豆包开启
        ConfigService.set_setting(
            db=db_session,
            key="llm.doubao.enabled",
            value="true",
            category="llm"
        )
        ConfigService.set_setting(
            db=db_session,
            key="llm.doubao.api_key",
            value="test_doubao_key",
            category="llm",
            is_encrypted=True
        )
        
        # 检查启用状态
        assert service._is_provider_enabled("deepseek", db_session) is False
        assert service._is_provider_enabled("doubao", db_session) is True

