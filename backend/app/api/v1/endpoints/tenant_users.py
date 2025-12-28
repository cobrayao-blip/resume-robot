"""
租户内用户管理API
租户管理员可以管理本租户内的用户
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
from ....core.database import get_db
from ....core.tenant_dependency import require_tenant_id
from ....core.security import get_password_hash
from ....models.user import User
from ....models.tenant import Tenant
from ....schemas.user import UserResponse, UserCreate, UserUpdate
from ....core.password_validator import validate_password_strength
from ....api.v1.endpoints.users import get_current_user
from fastapi import Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[UserResponse])  # 移除尾随斜杠，避免 307 重定向
async def list_tenant_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词（邮箱、姓名）"),
    role: Optional[str] = Query(None, description="角色筛选"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    获取租户内用户列表（租户管理员）
    
    只有租户管理员可以访问此接口
    """
    # 检查权限：只有租户管理员可以管理用户
    if current_user.role != 'tenant_admin' and current_user.user_type != 'super_admin':
        logger.warning(f"用户 {current_user.email} (role={current_user.role}, user_type={current_user.user_type}) 尝试访问用户管理接口")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有租户管理员可以管理用户"
        )
    
    logger.info(f"获取租户用户列表: tenant_id={tenant_id}, current_user={current_user.email}, role={current_user.role}")
    
    # 查询租户内的用户
    query = db.query(User).filter(User.tenant_id == tenant_id)
    
    # 搜索过滤
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) |
            (User.full_name.ilike(f"%{search}%"))
        )
    
    # 角色过滤
    if role:
        query = query.filter(User.role == role)
    
    # 排除平台管理员（平台管理员没有tenant_id）
    query = query.filter(User.tenant_id == tenant_id)
    
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    logger.info(f"查询到 {len(users)} 个用户 (tenant_id={tenant_id})")
    # 返回空列表是正常的，不应该报错
    return users


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)  # 移除尾随斜杠，避免 307 重定向
async def create_tenant_user(
    user_data: UserCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    创建租户内用户（租户管理员）
    
    只有租户管理员可以创建用户
    """
    # 检查权限
    if current_user.role != 'tenant_admin' and current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有租户管理员可以创建用户"
        )
    
    # 检查租户是否存在
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    
    # 检查邮箱是否已存在（在同一租户内）
    existing = db.query(User).filter(
        User.email == user_data.email,
        User.tenant_id == tenant_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"邮箱 {user_data.email} 已存在"
        )
    
    # 检查租户用户数限制
    user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
    if tenant.max_users and user_count >= tenant.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"租户用户数已达上限（{tenant.max_users}）"
        )
    
    # 创建用户
    try:
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role or 'hr_user',
            user_type='hr_user' if user_data.role == 'hr_user' else 'tenant_admin',
            tenant_id=tenant_id,
            is_active=True,
            is_verified=True,
            registration_status="approved"  # 自动批准
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"租户用户已创建: id={new_user.id}, email={new_user.email}, tenant_id={tenant_id}, created_by={current_user.id}")
        return new_user
    except Exception as e:
        db.rollback()
        logger.error(f"创建租户用户失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建用户失败: {str(e)}"
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_tenant_user(
    user_id: int,
    user_data: UserUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    更新租户内用户（租户管理员）
    """
    # 检查权限
    if current_user.role != 'tenant_admin' and current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有租户管理员可以更新用户"
        )
    
    # 查询用户（必须在同一租户内）
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新用户信息
    if user_data.email is not None:
        # 检查新邮箱是否已被其他用户使用
        existing = db.query(User).filter(
            User.email == user_data.email,
            User.tenant_id == tenant_id,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"邮箱 {user_data.email} 已被使用"
            )
        user.email = user_data.email
    
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    
    if user_data.role is not None:
        user.role = user_data.role
        # 更新user_type
        if user_data.role == 'tenant_admin':
            user.user_type = 'tenant_admin'
        else:
            user.user_type = 'hr_user'
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    # 如果提供了新密码，重置用户密码（管理员操作）
    if user_data.password:
        # 验证新密码强度
        is_valid, error_message = validate_password_strength(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        user.password_hash = get_password_hash(user_data.password)
        logger.info(f"管理员 {current_user.email} 重置用户 {user.email} 的密码")
    
    db.commit()
    db.refresh(user)
    
    logger.info(f"租户用户已更新: id={user_id}, tenant_id={tenant_id}, updated_by={current_user.id}")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_user(
    user_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    删除租户内用户（租户管理员）
    """
    # 检查权限
    if current_user.role != 'tenant_admin' and current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有租户管理员可以删除用户"
        )
    
    # 不能删除自己
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户"
        )
    
    # 查询用户（必须在同一租户内）
    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == tenant_id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    db.delete(user)
    db.commit()
    
    logger.info(f"租户用户已删除: id={user_id}, tenant_id={tenant_id}, deleted_by={current_user.id}")
    return None


@router.post("/invite", status_code=status.HTTP_200_OK)
async def invite_user(
    invite_data: dict = Body(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id)
):
    """
    邀请用户加入租户（租户管理员）
    
    TODO: 实现邮件发送功能
    """
    # 检查权限
    if current_user.role != 'tenant_admin' and current_user.user_type != 'super_admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有租户管理员可以邀请用户"
        )
    
    email = invite_data.get('email')
    role = invite_data.get('role', 'hr_user')
    
    if not email:
        raise HTTPException(status_code=400, detail="邮箱不能为空")
    
    # 检查邮箱是否已存在
    existing = db.query(User).filter(
        User.email == email,
        User.tenant_id == tenant_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户 {email} 已存在"
        )
    
    # TODO: 发送邀请邮件
    # 这里暂时返回成功，实际应该发送邮件并创建待激活的用户记录
    
    logger.info(f"用户邀请已发送: email={email}, role={role}, tenant_id={tenant_id}, invited_by={current_user.id}")
    return {
        "success": True,
        "message": f"邀请邮件已发送到 {email}（功能待实现）"
    }

