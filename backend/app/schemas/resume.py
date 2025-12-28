from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

# 模板基础模式
class TemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = False

# 模板创建模式
class TemplateCreate(TemplateBase):
    template_schema: Dict[str, Any]
    style_config: Optional[Dict[str, Any]] = None

# 模板响应模式
class TemplateResponse(TemplateBase):
    id: int
    template_schema: Dict[str, Any]
    style_config: Optional[Dict[str, Any]] = None
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    version: Optional[str] = "1.0.0"
    
    class Config:
        from_attributes = True

# 简历数据模式
class ResumeData(BaseModel):
    basic_info: Dict[str, Any]
    work_experiences: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    skills: Dict[str, Any]
    projects: List[Dict[str, Any]]
    # 可选扩展：推荐岗位、评价、薪资
    recommended_jobs: Optional[List[Dict[str, Any]]] = None
    evaluation: Optional[Dict[str, Any]] = None
    salary: Optional[Dict[str, Any]] = None

# 兼容新的导出负载：以 template_sections 为主
class ExportPayload(BaseModel):
    template_name: Optional[str] = None
    template_sections: Optional[List[Dict[str, Any]]] = None
    # 兼容旧结构（可选，不强制）
    basic_info: Optional[Dict[str, Any]] = None
    work_experiences: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[Dict[str, Any]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    recommended_jobs: Optional[List[Dict[str, Any]]] = None
    evaluation: Optional[Dict[str, Any]] = None
    salary: Optional[Dict[str, Any]] = None

# 简历创建模式
class ResumeCreate(BaseModel):
    template_id: int
    resume_data: ResumeData
    title: Optional[str] = "我的简历"
    parsed_resume_id: Optional[int] = None  # 关联解析结果ID
    candidate_name: Optional[str] = None  # 候选人姓名（可选，如果不提供则从 resume_data.basic_info.name 提取）
    source_file_name: Optional[str] = None
    source_file_type: Optional[str] = None
    source_file_path: Optional[str] = None

# 简历响应模式
class ResumeResponse(BaseModel):
    id: int
    user_id: int
    template_id: int
    title: str
    resume_data: ResumeData
    created_at: datetime
    
    class Config:
        from_attributes = True

# 智能匹配请求模式
class MatchFieldsRequest(BaseModel):
    parsed_data: Dict[str, Any]
    template_fields: Optional[List] = None
    template_structure: Optional[Dict[str, Any]] = None

# 简历列表响应模式（简化版，用于列表展示）
class ResumeListResponse(BaseModel):
    id: int
    user_id: int
    template_id: Optional[int] = None
    parsed_resume_id: Optional[int] = None  # 关联解析结果ID
    candidate_name: Optional[str] = None  # 候选人姓名
    title: str
    source_file_name: Optional[str] = None
    source_file_type: Optional[str] = None
    source_file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # 模板名称（关联查询）
    template_name: Optional[str] = None
    # 解析结果名称（关联查询）
    parsed_resume_name: Optional[str] = None
    
    class Config:
        from_attributes = True

# 解析结果创建模式
class ParsedResumeCreate(BaseModel):
    name: str
    parsed_data: Dict[str, Any]
    raw_text: Optional[str] = None
    candidate_name: Optional[str] = None  # 候选人姓名（可选，如果不提供则从 parsed_data.basic_info.name 提取）
    source_file_name: Optional[str] = None
    source_file_type: Optional[str] = None
    source_file_path: Optional[str] = None  # 直接关联原始文件路径
    file_hash: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None
    correction: Optional[Dict[str, Any]] = None
    quality_analysis: Optional[Dict[str, Any]] = None

# 解析结果响应模式
class ParsedResumeResponse(BaseModel):
    id: int
    user_id: int
    name: str
    parsed_data: Dict[str, Any]
    raw_text: Optional[str] = None
    candidate_name: Optional[str] = None  # 候选人姓名
    source_file_name: Optional[str] = None
    source_file_type: Optional[str] = None
    source_file_path: Optional[str] = None  # 直接关联原始文件路径
    file_hash: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None
    correction: Optional[Dict[str, Any]] = None
    quality_analysis: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 解析结果列表响应模式
class ParsedResumeListResponse(BaseModel):
    id: int
    name: str
    candidate_name: Optional[str] = None  # 候选人姓名
    source_file_name: Optional[str] = None
    source_file_type: Optional[str] = None
    source_file_path: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# 原始简历文件响应模式
class SourceFileResponse(BaseModel):
    id: int
    user_id: int
    file_name: str
    file_type: Optional[str] = None
    file_path: str
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 原始简历文件列表响应模式
class SourceFileListResponse(BaseModel):
    id: int
    file_name: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True