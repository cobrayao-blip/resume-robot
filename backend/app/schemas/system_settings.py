"""
系统配置相关的Pydantic模式
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SystemSettingResponse(BaseModel):
    """系统配置响应"""
    key: str
    value: str  # 脱敏后的值
    category: str
    description: Optional[str] = None
    is_encrypted: bool
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SystemSettingUpdate(BaseModel):
    """系统配置更新请求"""
    value: str = Field(..., description="配置值")
    description: Optional[str] = Field(None, description="配置说明")

class SystemSettingCreate(BaseModel):
    """系统配置创建请求"""
    key: str = Field(..., description="配置键")
    value: str = Field(..., description="配置值")
    category: str = Field(default="system", description="配置分类")
    description: Optional[str] = Field(None, description="配置说明")
    is_encrypted: bool = Field(default=False, description="是否加密存储")

class LLMConfigTestRequest(BaseModel):
    """LLM配置测试请求"""
    provider: str = Field(default="deepseek", description="服务商名称")
    api_key: str = Field(..., description="API密钥")
    base_url: Optional[str] = Field(None, description="API基础URL")
    model_name: Optional[str] = Field(None, description="模型名称")

class LLMConfigTestResponse(BaseModel):
    """LLM配置测试响应"""
    success: bool
    message: str
    provider: str

