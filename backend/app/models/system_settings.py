from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Index
from sqlalchemy.sql import func
from ..core.database import Base

class SystemSetting(Base):
    """系统配置表"""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False, index=True, comment="配置键，如: llm.deepseek.api_key")
    value = Column(Text, nullable=True, comment="配置值（加密存储）")
    category = Column(String(50), nullable=False, default="system", comment="配置分类: llm, system, email等")
    description = Column(Text, nullable=True, comment="配置说明")
    is_encrypted = Column(Boolean, default=False, comment="是否加密存储")
    updated_by = Column(Integer, nullable=True, comment="最后更新人ID")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    # 创建复合索引
    __table_args__ = (
        Index('idx_category_key', 'category', 'key'),
    )

