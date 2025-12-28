"""
租户模型
用于SaaS多租户架构
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base


class Tenant(Base):
    """租户表"""
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)  # 租户名称（公司名称）
    domain = Column(String(255), unique=True, index=True, nullable=True)  # 租户域名（可选）
    contact_email = Column(String(255))  # 联系人邮箱
    contact_phone = Column(String(50))  # 联系人电话
    
    # 订阅信息
    subscription_plan = Column(String(50), default="trial")  # 订阅套餐：trial/basic/professional/enterprise
    subscription_start = Column(DateTime)  # 订阅开始时间
    subscription_end = Column(DateTime)  # 订阅结束时间
    
    # 租户状态
    status = Column(String(50), default="active", index=True)  # active/suspended/expired
    
    # 使用限制
    max_users = Column(Integer, default=5)  # 最大用户数
    max_jobs = Column(Integer, default=10)  # 最大岗位数
    max_resumes_per_month = Column(Integer, default=100)  # 每月最大简历处理数
    current_month_resume_count = Column(Integer, default=0)  # 当前月已处理简历数
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联关系
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")


class SubscriptionPlan(Base):
    """订阅套餐表"""
    __tablename__ = "subscription_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)  # 套餐名称：trial/basic/professional/enterprise
    display_name = Column(String(255))  # 显示名称：试用版/基础版/专业版/企业版
    description = Column(Text)  # 套餐描述
    
    # 价格信息
    monthly_price = Column(Integer, default=0)  # 月价格（分）
    yearly_price = Column(Integer, default=0)  # 年价格（分）
    
    # 功能限制
    max_users = Column(Integer)  # 最大用户数（None表示无限制）
    max_jobs = Column(Integer)  # 最大岗位数（None表示无限制）
    max_resumes_per_month = Column(Integer)  # 每月最大简历处理数（None表示无限制）
    
    # 功能开关
    enable_batch_operations = Column(Boolean, default=False)  # 是否启用批量操作
    enable_advanced_matching = Column(Boolean, default=False)  # 是否启用高级匹配
    enable_custom_reports = Column(Boolean, default=False)  # 是否启用自定义报告
    enable_api_access = Column(Boolean, default=False)  # 是否启用API访问
    
    # 状态
    is_active = Column(Boolean, default=True)  # 是否激活
    is_visible = Column(Boolean, default=True)  # 是否在前端显示
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

