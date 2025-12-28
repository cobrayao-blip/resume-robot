"""
系统配置服务
提供配置的加密存储、读取和缓存功能
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
import base64
import hashlib
from ..models.system_settings import SystemSetting
from ..core.config import settings

logger = logging.getLogger(__name__)

class ConfigService:
    """系统配置服务"""
    
    _cache: Dict[str, Any] = {}
    _encryption_key: Optional[bytes] = None
    
    @classmethod
    def _get_encryption_key(cls) -> bytes:
        """获取加密密钥"""
        if cls._encryption_key is None:
            # 使用SECRET_KEY生成加密密钥
            secret_key = settings.secret_key.encode('utf-8')
            # 使用SHA256生成32字节密钥，然后base64编码
            key = hashlib.sha256(secret_key).digest()
            cls._encryption_key = base64.urlsafe_b64encode(key)
        return cls._encryption_key
    
    @classmethod
    def _encrypt(cls, value: str) -> str:
        """加密配置值"""
        if not value:
            return value
        try:
            f = Fernet(cls._get_encryption_key())
            encrypted = f.encrypt(value.encode('utf-8'))
            return encrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"加密配置值失败: {e}")
            raise
    
    @classmethod
    def _decrypt(cls, encrypted_value: str) -> str:
        """解密配置值"""
        if not encrypted_value:
            return encrypted_value
        try:
            f = Fernet(cls._get_encryption_key())
            decrypted = f.decrypt(encrypted_value.encode('utf-8'))
            return decrypted.decode('utf-8')
        except Exception as e:
            error_msg = str(e) if e else "未知错误"
            logger.error(f"解密配置值失败: {error_msg}, 类型: {type(e).__name__}")
            # 记录更多调试信息
            logger.error(f"加密值长度: {len(encrypted_value)}, 前20字符: {encrypted_value[:20] if len(encrypted_value) > 20 else encrypted_value}")
            raise ValueError(f"解密失败: {error_msg}")
    
    @classmethod
    def get_setting(cls, db: Session, key: str, default: Optional[str] = None) -> Optional[str]:
        """获取配置值（带缓存）"""
        # 先检查缓存
        if key in cls._cache:
            return cls._cache[key]
        
        # 从数据库读取
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        
        if not setting:
            # 数据库中没有配置，返回默认值（不再从环境变量读取）
            return default
        
        value = setting.value
        # 如果加密了，需要解密
        if setting.is_encrypted and value:
            try:
                value = cls._decrypt(value)
            except Exception as e:
                error_msg = str(e) if e else "未知错误"
                logger.error(f"解密配置 {key} 失败: {error_msg}, 类型: {type(e).__name__}")
                # 记录更多调试信息
                logger.error(f"配置值长度: {len(setting.value) if setting.value else 0}, is_encrypted: {setting.is_encrypted}")
                return default
        
        # 更新缓存
        cls._cache[key] = value
        return value
    
    @classmethod
    def set_setting(
        cls, 
        db: Session, 
        key: str, 
        value: str, 
        category: str = "system",
        description: Optional[str] = None,
        is_encrypted: bool = False,
        updated_by: Optional[int] = None
    ) -> SystemSetting:
        """设置配置值"""
        # 如果加密，先加密
        encrypted_value = cls._encrypt(value) if is_encrypted and value else value
        
        # 查找或创建配置
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        
        if setting:
            # 更新现有配置
            setting.value = encrypted_value
            setting.category = category
            if description:
                setting.description = description
            setting.is_encrypted = is_encrypted
            if updated_by:
                setting.updated_by = updated_by
        else:
            # 创建新配置
            setting = SystemSetting(
                key=key,
                value=encrypted_value,
                category=category,
                description=description,
                is_encrypted=is_encrypted,
                updated_by=updated_by
            )
            db.add(setting)
        
        db.commit()
        db.refresh(setting)
        
        # 清除缓存，确保下次读取时获取最新值
        if key in cls._cache:
            del cls._cache[key]
            logger.info(f"已清除配置缓存: {key}")
        
        logger.info(f"配置 {key} 已更新")
        return setting
    
    @classmethod
    def get_all_settings(cls, db: Session, category: Optional[str] = None) -> Dict[str, Any]:
        """获取所有配置（脱敏显示）"""
        query = db.query(SystemSetting)
        if category:
            query = query.filter(SystemSetting.category == category)
        
        settings_list = query.all()
        result = {}
        
        for setting in settings_list:
            value = setting.value
            # 如果是加密的，脱敏显示
            if setting.is_encrypted and value:
                try:
                    decrypted = cls._decrypt(value)
                    # 脱敏：只显示前4位和后4位
                    if len(decrypted) > 8:
                        value = decrypted[:4] + "****" + decrypted[-4:]
                    else:
                        value = "****"
                except Exception as e:
                    # 解密失败，记录日志但不抛出异常，返回脱敏值
                    logger.warning(f"解密配置 {setting.key} 失败: {e}，返回脱敏值")
                    value = "****"
            
            result[setting.key] = {
                "value": value,
                "category": setting.category,
                "description": setting.description,
                "is_encrypted": setting.is_encrypted,
                "updated_by": setting.updated_by,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
            }
        
        return result
    
    @classmethod
    def clear_cache(cls, key: Optional[str] = None):
        """清除缓存"""
        if key:
            cls._cache.pop(key, None)
        else:
            cls._cache.clear()
        logger.info(f"配置缓存已清除: {key or '全部'}")

# 创建全局实例
config_service = ConfigService()

