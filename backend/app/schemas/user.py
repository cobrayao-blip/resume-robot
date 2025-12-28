from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# 用户基础模式
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    user_type: Optional[str] = "trial_user"

# 用户创建模式 (注册)
class UserCreate(UserBase):
    password: str
    role: Optional[str] = "hr_user"  # 角色：tenant_admin/hr_user

# 用户更新模式
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    subscription_plan: Optional[str] = None
    password: Optional[str] = None  # 管理员可以重置用户密码
    email: Optional[EmailStr] = None  # 允许修改邮箱
    role: Optional[str] = None  # 允许修改角色
    is_active: Optional[bool] = None  # 允许修改启用状态

# 密码修改模式
class PasswordChange(BaseModel):
    old_password: str
    new_password: str

# 用户响应模式 (返回给前端)
class UserResponse(UserBase):
    id: int
    tenant_id: Optional[int] = None  # 租户ID（平台管理员为None）
    role: Optional[str] = None  # 角色：platform_admin/tenant_admin/hr_user
    is_active: bool
    is_verified: bool
    resume_generated_count: int
    subscription_plan: Optional[str] = None
    subscription_end: Optional[datetime] = None
    user_type: Optional[str] = None
    registration_status: Optional[str] = None
    monthly_usage_limit: Optional[int] = None
    current_month_usage: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# 登录相关模式
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class TokenData(BaseModel):
    email: Optional[str] = None

# LLM配置相关模式
class LLMConfigBase(BaseModel):
    provider: str = "deepseek"  # deepseek, doubao等
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

class LLMConfigUpdate(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None

class LLMConfigResponse(BaseModel):
    provider: str
    api_key: Optional[str] = None  # 返回时脱敏
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    
    class Config:
        from_attributes = True