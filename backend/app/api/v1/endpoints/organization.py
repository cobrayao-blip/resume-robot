"""
组织架构管理API
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, Field

from ....core.database import get_db
from ....core.tenant_dependency import require_tenant_id, get_tenant_id
from ....api.v1.endpoints.users import get_current_user
from ....models.user import User
from ....models.department import Department

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Schemas ====================

class DepartmentCreate(BaseModel):
    """创建部门请求"""
    name: str = Field(..., description="部门名称")
    code: Optional[str] = Field(None, description="部门编码")
    description: Optional[str] = Field(None, description="部门职责描述")
    parent_id: Optional[int] = Field(None, description="上级部门ID")
    department_culture: Optional[str] = Field(None, description="部门文化")
    work_style: Optional[str] = Field(None, description="工作风格")
    team_size: Optional[int] = Field(None, description="团队规模")
    key_responsibilities: Optional[str] = Field(None, description="核心职责")
    manager_id: Optional[int] = Field(None, description="部门负责人ID")


class DepartmentUpdate(BaseModel):
    """更新部门请求"""
    name: Optional[str] = Field(None, description="部门名称")
    code: Optional[str] = Field(None, description="部门编码")
    description: Optional[str] = Field(None, description="部门职责描述")
    parent_id: Optional[int] = Field(None, description="上级部门ID")
    department_culture: Optional[str] = Field(None, description="部门文化")
    work_style: Optional[str] = Field(None, description="工作风格")
    team_size: Optional[int] = Field(None, description="团队规模")
    key_responsibilities: Optional[str] = Field(None, description="核心职责")
    manager_id: Optional[int] = Field(None, description="部门负责人ID")


class DepartmentResponse(BaseModel):
    """部门响应"""
    id: int
    tenant_id: Optional[int]
    name: str
    code: Optional[str]
    description: Optional[str]
    parent_id: Optional[int]
    level: Optional[int]
    path: Optional[str]
    department_culture: Optional[str]
    work_style: Optional[str]
    team_size: Optional[int]
    key_responsibilities: Optional[str]
    manager_id: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]
    
    # 关联信息
    parent_name: Optional[str] = None
    manager_name: Optional[str] = None
    children_count: int = 0
    jobs_count: int = 0
    
    class Config:
        from_attributes = True


class DepartmentTreeResponse(DepartmentResponse):
    """部门树形结构响应"""
    children: List['DepartmentTreeResponse'] = []


# ==================== Helper Functions ====================

def _calculate_department_path(db: Session, department: Department) -> str:
    """计算部门路径"""
    path_parts = []
    current = department
    while current:
        path_parts.insert(0, current.name)
        if current.parent_id:
            current = db.query(Department).filter(Department.id == current.parent_id).first()
        else:
            current = None
    return " / ".join(path_parts)


def _calculate_department_level(db: Session, parent_id: Optional[int]) -> int:
    """计算部门层级"""
    if not parent_id:
        return 1
    
    parent = db.query(Department).filter(Department.id == parent_id).first()
    if not parent:
        return 1
    
    return parent.level + 1 if parent.level else 1


def _build_department_tree(
    db: Session,
    departments: List[Department],
    parent_id: Optional[int] = None
) -> List[DepartmentTreeResponse]:
    """构建部门树形结构"""
    tree = []
    
    for dept in departments:
        if dept.parent_id == parent_id:
            # 获取关联信息
            parent_name = None
            if dept.parent_id:
                parent = db.query(Department).filter(Department.id == dept.parent_id).first()
                if parent:
                    parent_name = parent.name
            
            manager_name = None
            if dept.manager_id:
                manager = db.query(User).filter(User.id == dept.manager_id).first()
                if manager:
                    manager_name = manager.full_name or manager.email
            
            # 统计子部门数量
            children_count = db.query(Department).filter(
                Department.parent_id == dept.id,
                Department.tenant_id == dept.tenant_id
            ).count()
            
            # 统计岗位数量
            from ....models.job import JobPosition
            jobs_count = db.query(JobPosition).filter(
                JobPosition.department_id == dept.id,
                JobPosition.tenant_id == dept.tenant_id
            ).count()
            
            dept_response = DepartmentTreeResponse(
                id=dept.id,
                tenant_id=dept.tenant_id,
                name=dept.name,
                code=dept.code,
                description=dept.description,
                parent_id=dept.parent_id,
                level=dept.level,
                path=dept.path or _calculate_department_path(db, dept),
                department_culture=dept.department_culture,
                work_style=dept.work_style,
                team_size=dept.team_size,
                key_responsibilities=dept.key_responsibilities,
                manager_id=dept.manager_id,
                created_at=dept.created_at.isoformat() if dept.created_at else None,
                updated_at=dept.updated_at.isoformat() if dept.updated_at else None,
                parent_name=parent_name,
                manager_name=manager_name,
                children_count=children_count,
                jobs_count=jobs_count,
                children=[]
            )
            
            # 递归获取子部门
            dept_response.children = _build_department_tree(db, departments, dept.id)
            
            tree.append(dept_response)
    
    return tree


# ==================== API Endpoints ====================

@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    创建部门
    """
    try:
        # 验证上级部门（如果提供）
        if department_data.parent_id:
            parent = db.query(Department).filter(
                Department.id == department_data.parent_id,
                Department.tenant_id == tenant_id
            ).first()
            if not parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="上级部门不存在"
                )
        
        # 验证部门负责人（如果提供）
        if department_data.manager_id:
            manager = db.query(User).filter(
                User.id == department_data.manager_id,
                User.tenant_id == tenant_id
            ).first()
            if not manager:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="部门负责人不存在"
                )
        
        # 计算层级和路径
        level = _calculate_department_level(db, department_data.parent_id)
        
        # 创建部门
        new_department = Department(
            tenant_id=tenant_id,
            name=department_data.name,
            code=department_data.code,
            description=department_data.description,
            parent_id=department_data.parent_id,
            level=level,
            department_culture=department_data.department_culture,
            work_style=department_data.work_style,
            team_size=department_data.team_size,
            key_responsibilities=department_data.key_responsibilities,
            manager_id=department_data.manager_id
        )
        
        db.add(new_department)
        db.commit()
        db.refresh(new_department)
        
        # 计算并更新路径
        new_department.path = _calculate_department_path(db, new_department)
        db.commit()
        db.refresh(new_department)
        
        # 获取关联信息
        parent_name = None
        if new_department.parent_id:
            parent = db.query(Department).filter(Department.id == new_department.parent_id).first()
            if parent:
                parent_name = parent.name
        
        manager_name = None
        if new_department.manager_id:
            manager = db.query(User).filter(User.id == new_department.manager_id).first()
            if manager:
                manager_name = manager.full_name or manager.email
        
        logger.info(f"创建部门成功: department_id={new_department.id}, name={new_department.name}, tenant_id={tenant_id}")
        
        return DepartmentResponse(
            id=new_department.id,
            tenant_id=new_department.tenant_id,
            name=new_department.name,
            code=new_department.code,
            description=new_department.description,
            parent_id=new_department.parent_id,
            level=new_department.level,
            path=new_department.path,
            department_culture=new_department.department_culture,
            work_style=new_department.work_style,
            team_size=new_department.team_size,
            key_responsibilities=new_department.key_responsibilities,
            manager_id=new_department.manager_id,
            created_at=new_department.created_at.isoformat() if new_department.created_at else None,
            updated_at=new_department.updated_at.isoformat() if new_department.updated_at else None,
            parent_name=parent_name,
            manager_name=manager_name,
            children_count=0,
            jobs_count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建部门失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建部门失败: {str(e)}"
        )


@router.get("/departments", response_model=List[DepartmentTreeResponse])
async def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    tree: bool = True
):
    """
    查询部门列表（支持树形结构）
    
    Args:
        tree: 是否返回树形结构（默认True）
    """
    try:
        # 查询所有部门
        departments = db.query(Department).filter(
            Department.tenant_id == tenant_id
        ).order_by(Department.level, Department.name).all()
        
        if tree:
            # 返回树形结构
            tree_data = _build_department_tree(db, departments)
            return tree_data
        else:
            # 返回扁平列表
            result = []
            for dept in departments:
                parent_name = None
                if dept.parent_id:
                    parent = db.query(Department).filter(Department.id == dept.parent_id).first()
                    if parent:
                        parent_name = parent.name
                
                manager_name = None
                if dept.manager_id:
                    manager = db.query(User).filter(User.id == dept.manager_id).first()
                    if manager:
                        manager_name = manager.full_name or manager.email
                
                from ....models.job import JobPosition
                jobs_count = db.query(JobPosition).filter(
                    JobPosition.department_id == dept.id,
                    JobPosition.tenant_id == dept.tenant_id
                ).count()
                
                children_count = db.query(Department).filter(
                    Department.parent_id == dept.id,
                    Department.tenant_id == dept.tenant_id
                ).count()
                
                result.append(DepartmentResponse(
                    id=dept.id,
                    tenant_id=dept.tenant_id,
                    name=dept.name,
                    code=dept.code,
                    description=dept.description,
                    parent_id=dept.parent_id,
                    level=dept.level,
                    path=dept.path or _calculate_department_path(db, dept),
                    department_culture=dept.department_culture,
                    work_style=dept.work_style,
                    team_size=dept.team_size,
                    key_responsibilities=dept.key_responsibilities,
                    manager_id=dept.manager_id,
                    created_at=dept.created_at.isoformat() if dept.created_at else None,
                    updated_at=dept.updated_at.isoformat() if dept.updated_at else None,
                    parent_name=parent_name,
                    manager_name=manager_name,
                    children_count=children_count,
                    jobs_count=jobs_count
                ))
            
            return result
        
    except Exception as e:
        logger.error(f"查询部门列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询部门列表失败: {str(e)}"
        )


@router.get("/departments/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    获取部门详情
    """
    try:
        department = db.query(Department).filter(
            Department.id == department_id,
            Department.tenant_id == tenant_id
        ).first()
        
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="部门不存在"
            )
        
        # 获取关联信息
        parent_name = None
        if department.parent_id:
            parent = db.query(Department).filter(Department.id == department.parent_id).first()
            if parent:
                parent_name = parent.name
        
        manager_name = None
        if department.manager_id:
            manager = db.query(User).filter(User.id == department.manager_id).first()
            if manager:
                manager_name = manager.full_name or manager.email
        
        from ....models.job import JobPosition
        jobs_count = db.query(JobPosition).filter(
            JobPosition.department_id == department.id,
            JobPosition.tenant_id == department.tenant_id
        ).count()
        
        children_count = db.query(Department).filter(
            Department.parent_id == department.id,
            Department.tenant_id == department.tenant_id
        ).count()
        
        return DepartmentResponse(
            id=department.id,
            tenant_id=department.tenant_id,
            name=department.name,
            code=department.code,
            description=department.description,
            parent_id=department.parent_id,
            level=department.level,
            path=department.path or _calculate_department_path(db, department),
            department_culture=department.department_culture,
            work_style=department.work_style,
            team_size=department.team_size,
            key_responsibilities=department.key_responsibilities,
            manager_id=department.manager_id,
            created_at=department.created_at.isoformat() if department.created_at else None,
            updated_at=department.updated_at.isoformat() if department.updated_at else None,
            parent_name=parent_name,
            manager_name=manager_name,
            children_count=children_count,
            jobs_count=jobs_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取部门详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取部门详情失败: {str(e)}"
        )


@router.put("/departments/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    更新部门
    """
    try:
        department = db.query(Department).filter(
            Department.id == department_id,
            Department.tenant_id == tenant_id
        ).first()
        
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="部门不存在"
            )
        
        # 验证上级部门（如果提供且需要更新）
        if department_data.parent_id is not None and department_data.parent_id != department.parent_id:
            # 不能将自己设为上级部门
            if department_data.parent_id == department_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能将自己设为上级部门"
                )
            
            # 验证上级部门是否存在
            if department_data.parent_id:
                parent = db.query(Department).filter(
                    Department.id == department_data.parent_id,
                    Department.tenant_id == tenant_id
                ).first()
                if not parent:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="上级部门不存在"
                    )
        
        # 验证部门负责人（如果提供）
        if department_data.manager_id is not None:
            if department_data.manager_id:
                manager = db.query(User).filter(
                    User.id == department_data.manager_id,
                    User.tenant_id == tenant_id
                ).first()
                if not manager:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="部门负责人不存在"
                    )
        
        # 更新字段
        update_data = department_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(department, key, value)
        
        # 如果parent_id改变，重新计算层级和路径
        if 'parent_id' in update_data:
            department.level = _calculate_department_level(db, department.parent_id)
            department.path = _calculate_department_path(db, department)
            
            # 更新所有子部门的层级和路径
            _update_children_levels_and_paths(db, department, tenant_id)
        
        db.commit()
        db.refresh(department)
        
        # 获取关联信息
        parent_name = None
        if department.parent_id:
            parent = db.query(Department).filter(Department.id == department.parent_id).first()
            if parent:
                parent_name = parent.name
        
        manager_name = None
        if department.manager_id:
            manager = db.query(User).filter(User.id == department.manager_id).first()
            if manager:
                manager_name = manager.full_name or manager.email
        
        from ....models.job import JobPosition
        jobs_count = db.query(JobPosition).filter(
            JobPosition.department_id == department.id,
            JobPosition.tenant_id == department.tenant_id
        ).count()
        
        children_count = db.query(Department).filter(
            Department.parent_id == department.id,
            Department.tenant_id == department.tenant_id
        ).count()
        
        logger.info(f"更新部门成功: department_id={department_id}, tenant_id={tenant_id}")
        
        return DepartmentResponse(
            id=department.id,
            tenant_id=department.tenant_id,
            name=department.name,
            code=department.code,
            description=department.description,
            parent_id=department.parent_id,
            level=department.level,
            path=department.path,
            department_culture=department.department_culture,
            work_style=department.work_style,
            team_size=department.team_size,
            key_responsibilities=department.key_responsibilities,
            manager_id=department.manager_id,
            created_at=department.created_at.isoformat() if department.created_at else None,
            updated_at=department.updated_at.isoformat() if department.updated_at else None,
            parent_name=parent_name,
            manager_name=manager_name,
            children_count=children_count,
            jobs_count=jobs_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新部门失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新部门失败: {str(e)}"
        )


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    删除部门
    
    注意：如果部门有子部门或关联岗位，不能删除
    """
    try:
        department = db.query(Department).filter(
            Department.id == department_id,
            Department.tenant_id == tenant_id
        ).first()
        
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="部门不存在"
            )
        
        # 检查是否有子部门
        children_count = db.query(Department).filter(
            Department.parent_id == department_id,
            Department.tenant_id == tenant_id
        ).count()
        
        if children_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该部门下有{children_count}个子部门，无法删除。请先删除或移动子部门。"
            )
        
        # 检查是否有关联岗位
        from ....models.job import JobPosition
        jobs_count = db.query(JobPosition).filter(
            JobPosition.department_id == department_id,
            JobPosition.tenant_id == tenant_id
        ).count()
        
        if jobs_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该部门下有关联的岗位（{jobs_count}个），无法删除。请先删除或移动岗位。"
            )
        
        db.delete(department)
        db.commit()
        
        logger.info(f"删除部门成功: department_id={department_id}, tenant_id={tenant_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除部门失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除部门失败: {str(e)}"
        )


def _update_children_levels_and_paths(db: Session, parent: Department, tenant_id: int):
    """递归更新子部门的层级和路径"""
    children = db.query(Department).filter(
        Department.parent_id == parent.id,
        Department.tenant_id == tenant_id
    ).all()
    
    for child in children:
        child.level = _calculate_department_level(db, child.parent_id)
        child.path = _calculate_department_path(db, child)
        db.commit()
        
        # 递归更新子部门的子部门
        _update_children_levels_and_paths(db, child, tenant_id)

