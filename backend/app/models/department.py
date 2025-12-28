"""
组织架构（部门）数据模型
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Index, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base


class Department(Base):
    """部门表（支持多层级组织架构）"""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    
    # 多租户支持
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # 租户ID
    
    # 部门基本信息
    name = Column(String(255), nullable=False, index=True)  # 部门名称
    code = Column(String(50))  # 部门编码（可选）
    description = Column(Text)  # 部门职责描述
    
    # 组织架构（多层级支持）
    parent_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)  # 上级部门ID
    level = Column(Integer, default=1, index=True)  # 部门层级（1=一级部门，2=二级部门...）
    path = Column(String(500))  # 部门路径（如：公司/技术部/后端组），用于快速查询
    
    # 部门文化/特点（用于Prompt增强）
    department_culture = Column(Text)  # 部门文化
    work_style = Column(Text)  # 工作风格
    team_size = Column(Integer)  # 团队规模
    key_responsibilities = Column(Text)  # 核心职责
    
    # 部门负责人（可选）
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 部门负责人ID
    
    # 时间戳
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # 关联关系
    parent = relationship("Department", remote_side=[id], backref="children")  # 上级部门
    manager = relationship("User", foreign_keys=[manager_id])  # 部门负责人
    jobs = relationship("JobPosition", back_populates="department_obj")  # 岗位列表
    
    # 索引
    __table_args__ = (
        Index('idx_department_tenant_parent', 'tenant_id', 'parent_id'),  # 查询租户的部门树
        Index('idx_department_tenant_level', 'tenant_id', 'level'),  # 查询特定层级的部门
    )

