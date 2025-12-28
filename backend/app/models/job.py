"""
岗位管理相关数据模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Float, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base


class JobPosition(Base):
    """岗位表"""
    __tablename__ = "job_positions"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID
    
    # 岗位基本信息
    title = Column(String(255), nullable=False, index=True)  # 岗位名称
    department = Column(String(100))  # 部门（保留字段，用于兼容性，建议使用department_id）
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)  # 部门ID（关联Department表）
    description = Column(Text)  # 岗位描述
    requirements = Column(Text)  # 岗位要求
    
    # 岗位状态
    status = Column(String(20), default="draft", index=True)  # draft, published, closed
    
    # 外部存储关联
    mongodb_id = Column(String(255))  # MongoDB文档ID（存储岗位画像数据）
    vector_id = Column(String(255))  # Milvus向量ID（存储岗位向量）
    
    # 创建者信息
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    creator = relationship("User")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关系
    matches = relationship("ResumeJobMatch", back_populates="job", cascade="all, delete-orphan")
    department_obj = relationship("Department", back_populates="jobs")  # 关联部门对象
    
    # 索引
    __table_args__ = (
        Index('idx_job_status_created', 'status', 'created_at'),  # 查询特定状态的岗位（按时间排序）
        Index('idx_job_created_by_status', 'created_by', 'status'),  # 查询用户创建的岗位
    )


class FilterRule(Base):
    """筛选规则表"""
    __tablename__ = "filter_rules"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID
    
    # 规则基本信息
    name = Column(String(255), nullable=False)  # 规则名称
    description = Column(Text)  # 规则描述
    
    # 规则类型和配置
    rule_type = Column(String(50), nullable=False, index=True)  # education, experience, skill, age, location等
    rule_config = Column(JSON, nullable=False)  # 规则配置（JSON格式）
    # 示例配置：
    # {
    #   "field": "education.degree",
    #   "operator": ">=",  # >=, <=, ==, !=, in, not_in
    #   "value": "本科",
    #   "required": true  # 是否必须满足
    # }
    
    # 规则组合逻辑
    logic_operator = Column(String(10), default="AND")  # AND, OR（与其他规则的关系）
    priority = Column(Integer, default=0)  # 优先级（数字越大优先级越高）
    
    # 规则状态
    is_active = Column(Boolean, default=True, index=True)
    
    # 创建者信息
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    creator = relationship("User")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_filter_rule_type_active', 'rule_type', 'is_active'),  # 查询特定类型的活跃规则
    )


class ResumeJobMatch(Base):
    """简历岗位匹配表"""
    __tablename__ = "resume_job_matches"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID
    
    # 关联信息
    resume_id = Column(Integer, ForeignKey("candidate_resumes.id"), nullable=False, index=True)
    resume = relationship("CandidateResume")
    
    job_id = Column(Integer, ForeignKey("job_positions.id"), nullable=False, index=True)
    job = relationship("JobPosition", back_populates="matches")
    
    # 匹配结果
    match_score = Column(Float, nullable=False, index=True)  # 匹配度分数（0-10）
    match_label = Column(String(50), index=True)  # 强烈推荐/推荐/谨慎推荐/不推荐
    
    # 匹配详情（存储在MongoDB）
    mongodb_detail_id = Column(String(255))  # MongoDB文档ID（存储匹配详情）
    
    # 匹配状态
    status = Column(String(20), default="pending", index=True)  # pending, reviewed, rejected, accepted
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 唯一约束：同一简历和岗位只能有一条匹配记录
    __table_args__ = (
        Index('idx_match_resume_job', 'resume_id', 'job_id', unique=True),  # 唯一索引
        Index('idx_match_job_score', 'job_id', 'match_score'),  # 查询岗位的匹配结果（按分数排序）
        Index('idx_match_label_status', 'match_label', 'status'),  # 查询特定标签和状态的匹配
    )


class CompanyInfo(Base):
    """公司信息表"""
    __tablename__ = "company_info"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, unique=True, index=True)  # 租户ID（每个租户只有一条记录）
    
    # 公司基本信息
    name = Column(String(255), nullable=False)  # 公司名称
    industry = Column(String(100))  # 行业
    products = Column(Text)  # 产品/服务
    application_scenarios = Column(Text)  # 应用场景
    company_culture = Column(Text)  # 公司文化
    preferences = Column(Text)  # 偏好（如：对可靠性、安全的偏好）
    
    # 新增字段（用于Prompt增强）
    company_size = Column(String(50))  # 公司规模（如：100-500人、500-1000人）
    development_stage = Column(String(50))  # 发展阶段（如：初创期、成长期、成熟期）
    business_model = Column(Text)  # 商业模式
    core_values = Column(Text)  # 核心价值观
    recruitment_philosophy = Column(Text)  # 招聘理念
    
    # 其他信息（JSON格式，便于扩展）
    additional_info = Column(JSON)  # 其他信息
    
    # 时间戳
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())


class MatchModel(Base):
    """匹配模型表"""
    __tablename__ = "match_models"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID
    
    # 模型基本信息
    name = Column(String(255), nullable=False)  # 模型名称
    description = Column(Text)  # 模型描述
    
    # 模型类型和配置
    model_type = Column(String(50), nullable=False, index=True)  # vector, llm, hybrid
    model_config = Column(JSON, nullable=False)  # 模型配置（JSON格式）
    # 示例配置：
    # {
    #   "vector_weight": 0.3,  # 向量相似度权重
    #   "rule_weight": 0.2,    # 规则匹配权重
    #   "llm_weight": 0.5,     # LLM评分权重
    #   "thresholds": {        # 阈值配置
    #     "strongly_recommended": 8.0,
    #     "recommended": 6.0,
    #     "cautious": 4.0
    #   }
    # }
    
    # 模型状态
    is_default = Column(Boolean, default=False, index=True)  # 是否为默认模型
    is_active = Column(Boolean, default=True, index=True)
    
    # 创建者信息
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    creator = relationship("User")
    
    # 时间戳
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_match_model_type_active', 'model_type', 'is_active'),  # 查询特定类型的活跃模型
    )

