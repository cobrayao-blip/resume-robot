"""
配置服务测试
"""
import pytest
from app.services.config_service import ConfigService
from app.models.system_settings import SystemSetting


class TestConfigService:
    """配置服务测试"""
    
    def test_set_and_get_setting(self, db_session):
        """测试设置和获取配置"""
        # 设置配置
        setting = ConfigService.set_setting(
            db=db_session,
            key="test.key",
            value="test_value",
            category="test"
        )
        
        assert setting.key == "test.key"
        assert setting.value == "test_value"
        
        # 获取配置
        value = ConfigService.get_setting(db_session, "test.key")
        assert value == "test_value"
    
    def test_get_setting_not_exists(self, db_session):
        """测试获取不存在的配置"""
        value = ConfigService.get_setting(db_session, "non.existent.key", default="default_value")
        assert value == "default_value"
    
    def test_encrypt_and_decrypt(self, db_session):
        """测试加密和解密"""
        # 设置加密配置
        setting = ConfigService.set_setting(
            db=db_session,
            key="test.encrypted",
            value="sensitive_data",
            category="test",
            is_encrypted=True
        )
        
        # 获取配置（应该自动解密）
        value = ConfigService.get_setting(db_session, "test.encrypted")
        assert value == "sensitive_data"
        
        # 验证数据库中存储的是加密值
        db_setting = db_session.query(SystemSetting).filter(
            SystemSetting.key == "test.encrypted"
        ).first()
        assert db_setting.value != "sensitive_data"  # 应该是加密后的值
    
    def test_clear_cache(self, db_session):
        """测试清除缓存"""
        # 设置配置
        ConfigService.set_setting(
            db=db_session,
            key="test.cache",
            value="cached_value",
            category="test"
        )
        
        # 获取配置（会缓存）
        value1 = ConfigService.get_setting(db_session, "test.cache")
        assert value1 == "cached_value"
        
        # 清除缓存
        ConfigService.clear_cache("test.cache")
        
        # 更新配置
        ConfigService.set_setting(
            db=db_session,
            key="test.cache",
            value="new_value",
            category="test"
        )
        
        # 获取配置（应该获取新值）
        value2 = ConfigService.get_setting(db_session, "test.cache")
        assert value2 == "new_value"

