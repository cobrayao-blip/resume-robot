"""
岗位管理相关的Schema定义
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


# ========== 岗位相关Schema ==========

class JobPositionBase(BaseModel):
    """岗位基础信息"""
    title: str = Field(..., description="岗位名称", max_length=255)
    department: Optional[str] = Field(None, description="部门", max_length=100)
    description: Optional[str] = Field(None, description="岗位描述")
    requirements: Optional[str] = Field(None, description="岗位要求")


class JobPositionCreate(JobPositionBase):
    """创建岗位请求"""
    status: Optional[str] = Field("draft", description="岗位状态: draft, published, closed")
    department_id: Optional[int] = Field(None, description="部门ID（关联Department表）")


class JobPositionUpdate(BaseModel):
    """更新岗位请求"""
    title: Optional[str] = Field(None, description="岗位名称", max_length=255)
    department: Optional[str] = Field(None, description="部门", max_length=100)
    description: Optional[str] = Field(None, description="岗位描述")
    requirements: Optional[str] = Field(None, description="岗位要求")
    status: Optional[str] = Field(None, description="岗位状态: draft, published, closed")


class JobPositionResponse(JobPositionBase):
    """岗位响应"""
    id: int
    status: str
    mongodb_id: Optional[str] = None
    vector_id: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class JobPositionListResponse(BaseModel):
    """岗位列表响应"""
    items: List[JobPositionResponse]
    total: int
    page: int
    page_size: int


class JobPositionWithProfile(JobPositionResponse):
    """岗位详情（包含画像）"""
    profile: Optional[Dict[str, Any]] = Field(None, description="岗位画像数据（从MongoDB）")


# ========== 筛选规则相关Schema ==========

class FilterRuleBase(BaseModel):
    """筛选规则基础信息"""
    name: str = Field(..., description="规则名称", max_length=255)
    description: Optional[str] = Field(None, description="规则描述")
    rule_type: str = Field(..., description="规则类型: education, experience, skill, age, location等", max_length=50)
    rule_config: Dict[str, Any] = Field(..., description="规则配置（JSON格式）")
    logic_operator: Optional[str] = Field("AND", description="逻辑运算符: AND, OR")
    priority: Optional[int] = Field(0, description="优先级（数字越大优先级越高）")
    is_active: Optional[bool] = Field(True, description="是否激活")


class FilterRuleCreate(FilterRuleBase):
    """创建筛选规则请求"""
    pass


class FilterRuleUpdate(BaseModel):
    """更新筛选规则请求"""
    name: Optional[str] = Field(None, description="规则名称", max_length=255)
    description: Optional[str] = Field(None, description="规则描述")
    rule_config: Optional[Dict[str, Any]] = Field(None, description="规则配置")
    logic_operator: Optional[str] = Field(None, description="逻辑运算符")
    priority: Optional[int] = Field(None, description="优先级")
    is_active: Optional[bool] = Field(None, description="是否激活")


class FilterRuleResponse(FilterRuleBase):
    """筛选规则响应"""
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== 匹配相关Schema ==========

class ResumeJobMatchBase(BaseModel):
    """简历岗位匹配基础信息"""
    resume_id: int = Field(..., description="简历ID")
    job_id: int = Field(..., description="岗位ID")
    match_score: float = Field(..., description="匹配度分数（0-10）", ge=0, le=10)
    match_label: str = Field(..., description="匹配标签: 强烈推荐/推荐/谨慎推荐/不推荐", max_length=50)
    status: Optional[str] = Field("pending", description="匹配状态: pending, reviewed, rejected, accepted")


class ResumeJobMatchCreate(ResumeJobMatchBase):
    """创建匹配记录请求"""
    mongodb_detail_id: Optional[str] = Field(None, description="匹配详情文档ID（MongoDB）")


class ResumeJobMatchResponse(ResumeJobMatchBase):
    """匹配记录响应"""
    id: int
    mongodb_detail_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ResumeJobMatchWithDetail(ResumeJobMatchResponse):
    """匹配记录详情（包含匹配详情）"""
    match_detail: Optional[Dict[str, Any]] = Field(None, description="匹配详情（从MongoDB）")


class MatchListResponse(BaseModel):
    """匹配列表响应"""
    items: List[ResumeJobMatchResponse]
    total: int
    page: int
    page_size: int
    
    class Config:
        from_attributes = True


# ========== 公司信息相关Schema ==========

class CompanyInfoBase(BaseModel):
    """公司信息基础"""
    name: str = Field(..., description="公司名称", max_length=255)
    industry: Optional[str] = Field(None, description="行业", max_length=100)
    products: Optional[str] = Field(None, description="产品/服务")
    application_scenarios: Optional[str] = Field(None, description="应用场景")
    company_culture: Optional[str] = Field(None, description="公司文化")
    preferences: Optional[str] = Field(None, description="偏好（如：对可靠性、安全的偏好）")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="其他信息（JSON格式）")


class CompanyInfoCreate(CompanyInfoBase):
    """创建公司信息请求"""
    pass


class CompanyInfoUpdate(BaseModel):
    """更新公司信息请求"""
    name: Optional[str] = Field(None, description="公司名称", max_length=255)
    industry: Optional[str] = Field(None, description="行业", max_length=100)
    products: Optional[str] = Field(None, description="产品/服务")
    application_scenarios: Optional[str] = Field(None, description="应用场景")
    company_culture: Optional[str] = Field(None, description="公司文化")
    preferences: Optional[str] = Field(None, description="偏好")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="其他信息")


class CompanyInfoResponse(CompanyInfoBase):
    """公司信息响应"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ========== 匹配模型相关Schema ==========

class MatchModelBase(BaseModel):
    """匹配模型基础信息"""
    name: str
    description: Optional[str] = None
    model_type: str
    model_config: Dict[str, Any]
    is_default: bool = False
    is_active: bool = True


class MatchModelCreate(MatchModelBase):
    """创建匹配模型请求"""
    pass


class MatchModelUpdate(BaseModel):
    """更新匹配模型请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    model_config: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class MatchModelResponse(MatchModelBase):
    """匹配模型响应"""
    id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

