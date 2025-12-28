from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base

class UserRegistrationRequest(Base):
    """用户注册申请表"""
    __tablename__ = "user_registration_requests"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    company = Column(String(255), nullable=True)  # 公司名称
    phone = Column(String(50), nullable=True)  # 联系电话
    application_reason = Column(Text, nullable=True)  # 申请理由
    
    # 审核状态
    status = Column(String(50), default="pending", index=True)  # pending, approved, rejected
    
    # 审核信息
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)  # 审核备注
    
    # 关联用户（如果审核通过，会创建用户）
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    user = relationship("User", foreign_keys=[user_id])

