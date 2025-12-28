"""
用户注册申请相关的Schema
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class RegistrationRequestCreate(BaseModel):
    """创建注册申请"""
    email: EmailStr
    full_name: str
    password: str
    company: Optional[str] = None
    phone: Optional[str] = None
    application_reason: Optional[str] = None

class RegistrationRequestResponse(BaseModel):
    """注册申请响应"""
    id: int
    email: str
    full_name: str
    company: Optional[str] = None
    phone: Optional[str] = None
    application_reason: Optional[str] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class RegistrationRequestReview(BaseModel):
    """审核注册申请"""
    status: str  # approved, rejected
    review_notes: Optional[str] = None

