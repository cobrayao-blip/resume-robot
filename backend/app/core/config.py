from pydantic_settings import BaseSettings
from typing import Optional, List, Union
from pydantic import field_validator, Field
import secrets
import os
import warnings
import logging
from .constants import DEFAULT_TOKEN_EXPIRE_MINUTES, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

def _get_or_create_secret_key() -> str:
    """获取或创建SECRET_KEY（优先环境变量，其次持久化文件）"""
    # 1. 优先从环境变量读取（生产环境推荐方式）
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        return env_key
    
    # 2. 尝试从持久化文件读取（避免重启后密钥变化）
    # 文件路径：backend/.secret_key（相对于backend目录）
    secret_file = os.path.join(os.path.dirname(__file__), "..", ".secret_key")
    secret_file = os.path.abspath(secret_file)
    try:
        if os.path.exists(secret_file):
            with open(secret_file, 'r', encoding='utf-8') as f:
                stored_key = f.read().strip()
                if stored_key:
                    logger.info(f"从持久化文件读取SECRET_KEY: {secret_file}")
                    return stored_key
    except Exception as e:
        logger.warning(f"读取持久化密钥文件失败: {e}")
    
    # 3. 生成新密钥并保存（仅开发环境）
    new_key = secrets.token_urlsafe(32)
    try:
        os.makedirs(os.path.dirname(secret_file), exist_ok=True)
        with open(secret_file, 'w', encoding='utf-8') as f:
            f.write(new_key)
        # 设置文件权限（仅所有者可读写）
        os.chmod(secret_file, 0o600)
        logger.info(f"已生成新的SECRET_KEY并保存到 {secret_file}（仅开发环境）")
    except Exception as e:
        logger.warning(f"保存SECRET_KEY到文件失败: {e}，将使用临时密钥（重启后会变化）")
    
    return new_key

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://resume_user:password@localhost:5432/resume_db"
    
    # DeepSeek AI - 已移除环境变量配置，所有API密钥统一从数据库读取
    # 不再保留 deepseek_api_key 字段，所有LLM配置（DeepSeek、豆包等）都通过数据库管理
    
    # Security
    # SECRET_KEY 用于JWT签名和配置加密
    # 优先从环境变量读取，如果没有设置，尝试从持久化文件读取
    # 如果都没有，生成新的密钥并保存到文件（仅开发环境）
    secret_key: str = Field(
        default_factory=_get_or_create_secret_key,
        description="JWT 密钥和加密密钥"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(
        default=DEFAULT_TOKEN_EXPIRE_MINUTES,
        description="JWT Token过期时间（分钟）"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 如果使用默认生成的密钥（既没有环境变量也没有持久化文件），在非调试模式下发出警告
        if not os.getenv("SECRET_KEY") and not self.debug:
            secret_file = os.path.join(os.path.dirname(__file__), "..", ".secret_key")
            secret_file = os.path.abspath(secret_file)
            if not os.path.exists(secret_file):
                warnings.warn(
                    "SECRET_KEY 未设置！生产环境建议设置环境变量 SECRET_KEY 或使用持久化文件。"
                    "当前使用临时生成的密钥，重启后会导致所有 token 和加密配置失效。",
                    UserWarning
                )
    
    # Redis
    redis_url: str = "redis://redis:6379"  # Docker环境默认值，可通过REDIS_URL环境变量覆盖
    
    # MongoDB
    mongodb_url: str = Field(
        default="mongodb://resume_user:password@mongodb:27017/resume_robot?authSource=admin",
        description="MongoDB连接URL"
    )
    
    # Milvus
    milvus_host: str = Field(
        default="milvus",
        description="Milvus服务地址"
    )
    milvus_port: int = Field(
        default=19530,
        description="Milvus服务端口"
    )
    
    # Application
    debug: bool = Field(
        default=False,
        description="调试模式，生产环境必须设为False"
    )
    project_name: str = "ResumeAI Platform"
    version: str = "1.0.0"
    
    # CORS - 使用字符串类型，然后在验证器中转换为列表
    cors_origins: Union[str, List[str]] = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        description="CORS允许的来源，逗号分隔的字符串或列表"
    )
    
    # Export
    export_dir: str = "temp"

    # Upload
    upload_max_mb: int = Field(
        default=MAX_FILE_SIZE_MB,
        description="文件上传最大大小（MB）"
    )

    # 兼容从环境变量以逗号分隔字符串传入CORS
    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if v is None:
            return ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"]
        if isinstance(v, str):
            # 允许以逗号分隔的字符串
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins if origins else ["http://localhost:5173"]
        if isinstance(v, list):
            return v
        return v
    
    def get_cors_origins_list(self) -> List[str]:
        """获取 CORS 来源列表"""
        if isinstance(self.cors_origins, list):
            return self.cors_origins
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return ["http://localhost:5173"]
    
    class Config:
        env_file = ".env"

settings = Settings()