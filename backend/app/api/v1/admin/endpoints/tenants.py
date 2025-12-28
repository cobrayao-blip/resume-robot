"""
租户管理API（管理后台）
平台管理员可以创建、查询、更新、删除租户
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from .....core.database import get_db
from .....core.permissions import require_admin
from .....core.security import get_password_hash
from .....models.user import User
from .....models.tenant import Tenant
from .....schemas.tenant import TenantCreate, TenantUpdate, TenantResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    创建租户（平台管理员）
    """
    try:
        logger.info(f"创建租户请求: {tenant_data.dict()}")
        
        # 检查域名是否已存在
        if tenant_data.domain:
            existing = db.query(Tenant).filter(Tenant.domain == tenant_data.domain).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"域名 {tenant_data.domain} 已被使用"
                )
        
        # 创建租户
        db_tenant = Tenant(
            name=tenant_data.name,
            domain=tenant_data.domain,
            contact_email=tenant_data.contact_email,
            contact_phone=tenant_data.contact_phone,
            subscription_plan=tenant_data.subscription_plan or "trial",
            subscription_start=tenant_data.subscription_start or datetime.utcnow(),
            subscription_end=tenant_data.subscription_end,
            status=tenant_data.status or "active",
            max_users=tenant_data.max_users or 5,
            max_jobs=tenant_data.max_jobs or 10,
            max_resumes_per_month=tenant_data.max_resumes_per_month or 100
        )
        db.add(db_tenant)
        db.flush()  # 获取租户ID
        
        # 如果提供了管理员邮箱，创建租户管理员账户
        if tenant_data.admin_email:
            # 检查邮箱是否已存在（检查所有用户，因为邮箱必须全局唯一）
            # 注意：由于唯一约束是 (tenant_id, email)，平台管理员(tenant_id=None)的邮箱必须全局唯一
            # 租户用户的邮箱在同一租户内唯一，但不同租户可以使用相同邮箱
            # 为了简化，我们要求所有邮箱全局唯一
            existing_user = db.query(User).filter(User.email == tenant_data.admin_email).first()
            if existing_user:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"邮箱 {tenant_data.admin_email} 已被使用"
                )
            
            try:
                # 创建租户管理员
                # 如果没有提供密码，使用默认密码 Admin123456
                admin_password = tenant_data.admin_password or "Admin123456"
                admin_password_hash = get_password_hash(admin_password)
                admin_user = User(
                    email=tenant_data.admin_email,
                    password_hash=admin_password_hash,
                    full_name=tenant_data.admin_name or "租户管理员",
                    role="tenant_admin",
                    user_type="tenant_admin",
                    tenant_id=db_tenant.id,
                    is_active=True,
                    is_verified=True,
                    registration_status="approved"  # 自动批准
                )
                db.add(admin_user)
                logger.info(f"租户管理员已创建: email={tenant_data.admin_email}, tenant_id={db_tenant.id}")
            except Exception as e:
                db.rollback()
                logger.error(f"创建租户管理员失败: {e}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"创建租户管理员失败: {str(e)}"
                )
        
        try:
            db.commit()
            db.refresh(db_tenant)
            logger.info(f"租户已创建: id={db_tenant.id}, name={db_tenant.name}, created_by={current_user.id}")
            return db_tenant
        except Exception as commit_error:
            db.rollback()
            logger.error(f"提交事务失败: {commit_error}", exc_info=True)
            # 检查是否是唯一约束冲突
            error_str = str(commit_error).lower()
            if 'unique' in error_str or 'duplicate' in error_str:
                if 'email' in error_str or 'uq_user_tenant_email' in error_str:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"邮箱 {tenant_data.admin_email if tenant_data.admin_email else 'N/A'} 已被使用"
                    )
                elif 'domain' in error_str:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"域名 {tenant_data.domain} 已被使用"
                    )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"创建租户失败: {str(commit_error)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建租户失败: {e}", exc_info=True)
        # 检查是否是唯一约束冲突
        error_str = str(e).lower()
        if 'unique' in error_str or 'duplicate' in error_str:
            if 'email' in error_str or 'uq_user_tenant_email' in error_str:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"邮箱已被使用"
                )
            elif 'domain' in error_str:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"域名已被使用"
                )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建租户失败: {str(e)}"
        )


@router.get("", response_model=List[TenantResponse])
async def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    status: Optional[str] = None,
    subscription_plan: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    查询租户列表（平台管理员）
    """
    try:
        query = db.query(Tenant)
        
        # 搜索过滤
        if search:
            query = query.filter(
                Tenant.name.ilike(f"%{search}%")
            )
        
        # 状态过滤
        if status:
            query = query.filter(Tenant.status == status)
        
        # 订阅套餐过滤
        if subscription_plan:
            query = query.filter(Tenant.subscription_plan == subscription_plan)
        
        tenants = query.order_by(Tenant.created_at.desc()).offset(skip).limit(limit).all()
        return tenants
        
    except Exception as e:
        logger.error(f"查询租户列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询租户列表失败: {str(e)}"
        )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取租户详情（平台管理员）
    """
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        return tenant
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取租户详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取租户详情失败: {str(e)}"
        )


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    tenant_data: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新租户信息（平台管理员）
    """
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        # 更新字段
        update_data = tenant_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(tenant, field):
                setattr(tenant, field, value)
        
        tenant.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(tenant)
        
        logger.info(f"租户已更新: id={tenant.id}, updated_by={current_user.id}")
        return tenant
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新租户失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新租户失败: {str(e)}"
        )


@router.post("/{tenant_id}/activate", response_model=TenantResponse)
async def activate_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    激活租户（平台管理员）
    """
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        tenant.status = "active"
        tenant.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(tenant)
        
        logger.info(f"租户已激活: id={tenant.id}, updated_by={current_user.id}")
        return tenant
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"激活租户失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"激活租户失败: {str(e)}"
        )


@router.post("/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    暂停租户（平台管理员）
    """
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        tenant.status = "suspended"
        tenant.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(tenant)
        
        logger.info(f"租户已暂停: id={tenant.id}, updated_by={current_user.id}")
        return tenant
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"暂停租户失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"暂停租户失败: {str(e)}"
        )


@router.get("/{tenant_id}/stats")
async def get_tenant_stats(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取租户数据统计（平台管理员）
    """
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        # 统计用户数
        from ....models.user import User
        user_count = db.query(User).filter(User.tenant_id == tenant_id).count()
        
        # 统计岗位数
        from .....models.job import JobPosition
        job_count = db.query(JobPosition).filter(JobPosition.tenant_id == tenant_id).count()
        
        # 统计简历数
        from .....models.resume import CandidateResume
        resume_count = db.query(CandidateResume).filter(CandidateResume.tenant_id == tenant_id).count()
        
        # 统计匹配数
        from ....models.job import ResumeJobMatch
        match_count = db.query(ResumeJobMatch).filter(ResumeJobMatch.tenant_id == tenant_id).count()
        
        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "stats": {
                "users": user_count,
                "jobs": job_count,
                "resumes": resume_count,
                "matches": match_count,
                "current_month_resume_count": tenant.current_month_resume_count,
                "max_resumes_per_month": tenant.max_resumes_per_month
            },
            "limits": {
                "max_users": tenant.max_users,
                "max_jobs": tenant.max_jobs,
                "max_resumes_per_month": tenant.max_resumes_per_month
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取租户统计失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取租户统计失败: {str(e)}"
        )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除租户（平台管理员）
    
    注意：删除租户会级联删除该租户的所有数据（用户、岗位、简历等）
    """
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        # 删除租户（级联删除关联数据）
        db.delete(tenant)
        db.commit()
        
        logger.info(f"租户已删除: id={tenant_id}, name={tenant.name}, deleted_by={current_user.id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除租户失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除租户失败: {str(e)}"
        )

