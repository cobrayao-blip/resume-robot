from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base

class UserLLMConfig(Base):
    """用户LLM配置表"""
    __tablename__ = "user_llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # deepseek, doubao, openai等
    api_key = Column(Text, nullable=True)  # API密钥（加密存储）
    base_url = Column(String(255), nullable=True)  # API基础URL
    model_name = Column(String(100), nullable=True)  # 模型名称
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    user = relationship("User", back_populates="llm_config")

