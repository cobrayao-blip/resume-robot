"""
租户相关Schema
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class TenantBase(BaseModel):
    """租户基础信息"""
    name: str
    domain: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None


class TenantCreate(TenantBase):
    """创建租户请求"""
    subscription_plan: Optional[str] = "trial"
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    status: Optional[str] = "active"
    max_users: Optional[int] = 5
    max_jobs: Optional[int] = 10
    max_resumes_per_month: Optional[int] = 100
    admin_email: Optional[EmailStr] = None  # 租户管理员邮箱
    admin_password: Optional[str] = None  # 租户管理员初始密码
    admin_name: Optional[str] = None  # 租户管理员姓名


class TenantUpdate(BaseModel):
    """更新租户请求"""
    name: Optional[str] = None
    domain: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    subscription_plan: Optional[str] = None
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    status: Optional[str] = None
    max_users: Optional[int] = None
    max_jobs: Optional[int] = None
    max_resumes_per_month: Optional[int] = None


class TenantResponse(TenantBase):
    """租户响应"""
    id: int
    subscription_plan: str
    subscription_start: Optional[datetime]
    subscription_end: Optional[datetime]
    status: str
    max_users: int
    max_jobs: int
    max_resumes_per_month: int
    current_month_resume_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SubscriptionPlanBase(BaseModel):
    """订阅套餐基础信息"""
    name: str
    display_name: str
    description: Optional[str] = None


class SubscriptionPlanCreate(SubscriptionPlanBase):
    """创建订阅套餐请求"""
    monthly_price: int = 0  # 月价格（分）
    yearly_price: int = 0  # 年价格（分）
    max_users: Optional[int] = None
    max_jobs: Optional[int] = None
    max_resumes_per_month: Optional[int] = None
    enable_batch_operations: bool = False
    enable_advanced_matching: bool = False
    enable_custom_reports: bool = False
    enable_api_access: bool = False
    is_active: bool = True
    is_visible: bool = True


class SubscriptionPlanUpdate(BaseModel):
    """更新订阅套餐请求"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    monthly_price: Optional[int] = None
    yearly_price: Optional[int] = None
    max_users: Optional[int] = None
    max_jobs: Optional[int] = None
    max_resumes_per_month: Optional[int] = None
    enable_batch_operations: Optional[bool] = None
    enable_advanced_matching: Optional[bool] = None
    enable_custom_reports: Optional[bool] = None
    enable_api_access: Optional[bool] = None
    is_active: Optional[bool] = None
    is_visible: Optional[bool] = None


class SubscriptionPlanResponse(SubscriptionPlanBase):
    """订阅套餐响应"""
    id: int
    monthly_price: int
    yearly_price: int
    max_users: Optional[int]
    max_jobs: Optional[int]
    max_resumes_per_month: Optional[int]
    enable_batch_operations: bool
    enable_advanced_matching: bool
    enable_custom_reports: bool
    enable_api_access: bool
    is_active: bool
    is_visible: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

