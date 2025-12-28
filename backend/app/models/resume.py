from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base

class ResumeTemplate(Base):
    __tablename__ = "resume_templates"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID（None表示平台公共模板）
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # 模板设计数据 (JSON格式存储模板结构)
    template_schema = Column(JSON, nullable=False)
    style_config = Column(JSON)
    
    # 模板权限
    is_public = Column(Boolean, default=False, index=True)  # 添加索引，用于查询公开模板
    is_active = Column(Boolean, default=True, index=True)  # 添加索引，用于查询活跃模板
    
    # 版本管理
    version = Column(String(50), default="1.0.0")
    parent_template_id = Column(Integer, ForeignKey("resume_templates.id"), nullable=True)  # 父模板ID（用于版本关联）
    
    # 使用统计
    usage_count = Column(Integer, default=0)  # 模板被使用次数
    
    # 创建者信息
    created_by = Column(Integer, ForeignKey("users.id"), index=True)  # 添加索引，用于查询用户创建的模板
    creator = relationship("User")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 版本历史关系
    versions = relationship("TemplateVersion", back_populates="template", cascade="all, delete-orphan")
    
    # 添加复合索引，优化常用查询
    __table_args__ = (
        Index('idx_template_public_active', 'is_public', 'is_active'),  # 查询公开且活跃的模板
        Index('idx_template_created_by_active', 'created_by', 'is_active'),  # 查询用户创建的活跃模板
    )

class TemplateVersion(Base):
    """模板版本历史表"""
    __tablename__ = "template_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("resume_templates.id"), nullable=False, index=True)  # 添加索引，用于查询模板的所有版本
    template = relationship("ResumeTemplate", back_populates="versions")
    
    # 版本信息
    version = Column(String(50), nullable=False)  # 版本号，如 "1.0.0", "1.1.0"
    version_name = Column(String(255))  # 版本名称/描述，如 "初始版本", "添加工作详情组件"
    
    # 模板快照（保存完整模板数据）
    template_schema = Column(JSON, nullable=False)
    style_config = Column(JSON)
    
    # 创建信息
    created_by = Column(Integer, ForeignKey("users.id"))
    creator = relationship("User")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)  # 添加索引，用于按时间排序

class SourceFile(Base):
    """原始简历文件表"""
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, index=True)
    
    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User")
    
    # 文件信息
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(100))  # PDF, Word等
    file_path = Column(String(500), nullable=False)  # 文件存储路径
    file_size = Column(Integer)  # 文件大小（字节）
    file_hash = Column(String(64), index=True)  # 文件内容的MD5 hash，用于去重
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 添加复合索引，优化常用查询
    __table_args__ = (
        Index('idx_source_file_user_created', 'user_id', 'created_at'),  # 查询用户的文件列表（按时间排序）
    )

class CandidateResume(Base):
    """候选人推荐报告表（原UserResume）"""
    __tablename__ = "candidate_resumes"

    id = Column(Integer, primary_key=True, index=True)
    
    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # 添加索引，用于查询用户的简历列表
    user = relationship("User")
    
    # 解析结果关联
    parsed_resume_id = Column(Integer, ForeignKey("parsed_resumes.id"), nullable=True, index=True)  # 关联解析结果
    parsed_resume = relationship("ParsedResume", foreign_keys=[parsed_resume_id])
    
    # 模板关联
    template_id = Column(Integer, ForeignKey("resume_templates.id"), index=True)  # 添加索引，用于查询使用特定模板的简历
    template = relationship("ResumeTemplate")
    
    # 简历数据 (JSON格式存储填充后的简历内容)
    resume_data = Column(JSON, nullable=False)
    
    # 候选人信息
    candidate_name = Column(String(255))  # 候选人姓名（便于快速识别）
    
    # 源文件信息（保留，便于快速查看）
    source_file_name = Column(String(255))
    source_file_type = Column(String(100))  # 增加长度以支持完整的MIME类型
    source_file_path = Column(String(500))  # 源文件存储路径（相对于存储目录）
    
    # 状态信息
    title = Column(String(255), default="我的简历")
    version = Column(String(50), default="1.0")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)  # 添加索引，用于按时间排序
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 添加复合索引，优化常用查询
    __table_args__ = (
        Index('idx_candidate_resume_user_created', 'user_id', 'created_at'),  # 查询用户的简历列表（按时间排序）
    )

class ParsedResume(Base):
    """简历解析结果表"""
    __tablename__ = "parsed_resumes"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID
    
    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # 添加索引，用于查询用户的解析结果
    user = relationship("User")
    
    # 解析结果信息
    name = Column(String(255), nullable=False)  # 解析结果名称，如"李国雄详细解析结果"
    parsed_data = Column(JSON, nullable=False)  # 解析后的结构化数据
    raw_text = Column(Text)  # 原始文本内容（可选，用于调试）
    
    # 候选人信息
    candidate_name = Column(String(255))  # 候选人姓名（从解析数据中提取）
    
    # 源文件信息
    source_file_name = Column(String(255))
    source_file_type = Column(String(100))
    source_file_path = Column(String(500))  # 直接关联原始文件路径
    file_hash = Column(String(64), index=True)  # 文件内容的MD5 hash，用于去重，添加索引
    
    # 解析元数据
    validation = Column(JSON)  # 验证结果
    correction = Column(JSON)  # 纠错结果
    quality_analysis = Column(JSON)  # 质量分析结果
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)  # 添加索引，用于按时间排序
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 添加复合索引，优化常用查询
    __table_args__ = (
        Index('idx_parsed_user_created', 'user_id', 'created_at'),  # 查询用户的解析结果列表（按时间排序）
        Index('idx_parsed_file_hash', 'file_hash'),  # 查询相同文件的解析结果（去重）
    )