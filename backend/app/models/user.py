from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID（平台管理员为None）
    tenant = relationship("Tenant", back_populates="users")
    
    email = Column(String(255), index=True, nullable=False)  # 移除unique，改为tenant_id+email唯一
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100))
    
    # 用户类型: platform_admin（平台管理员）, tenant_admin（租户管理员）, hr_user（HR用户）
    user_type = Column(String(50), default="hr_user")
    
    # 角色（用于权限控制，与user_type配合使用）
    role = Column(String(50), default="hr_user")  # platform_admin/tenant_admin/hr_user
    
    # 会员信息
    subscription_plan = Column(String(50), default="trial")
    subscription_end = Column(DateTime)
    
    # 使用统计
    resume_generated_count = Column(Integer, default=0)
    last_login = Column(DateTime)
    
    # 账户状态
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # 注册审核相关
    registration_status = Column(String(50), default="pending")  # pending, approved, rejected
    reviewed_by = Column(Integer, nullable=True)  # 审核人ID
    reviewed_at = Column(DateTime, nullable=True)  # 审核时间
    review_notes = Column(Text, nullable=True)  # 审核备注
    
    # 使用限制（必须由管理员设置，不能为None）
    monthly_usage_limit = Column(Integer, nullable=True)  # 每月使用次数限制（由管理员设置）
    current_month_usage = Column(Integer, default=0)  # 当前月已使用次数
    usage_reset_date = Column(DateTime, nullable=True)  # 使用次数重置日期
    
    # LLM配置关系
    llm_config = relationship("UserLLMConfig", uselist=False, back_populates="user")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 唯一约束：同一租户内email唯一（平台管理员tenant_id为None，email全局唯一）
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email'),
    )