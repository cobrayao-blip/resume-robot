"""
订阅管理API（管理后台）
平台管理员可以管理订阅套餐和租户订阅
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from .....core.database import get_db
from .....core.permissions import require_admin
from .....models.user import User
from .....models.tenant import Tenant, SubscriptionPlan
from .....schemas.tenant import (
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    SubscriptionPlanResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ========== 订阅套餐管理 ==========

@router.post("/plans", response_model=SubscriptionPlanResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    plan_data: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    创建订阅套餐（平台管理员）
    """
    try:
        # 检查套餐名称是否已存在
        existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan_data.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"套餐名称 {plan_data.name} 已存在"
            )
        
        # 创建套餐
        db_plan = SubscriptionPlan(**plan_data.dict())
        db.add(db_plan)
        db.commit()
        db.refresh(db_plan)
        
        logger.info(f"订阅套餐已创建: id={db_plan.id}, name={db_plan.name}, created_by={current_user.id}")
        return db_plan
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建订阅套餐失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建订阅套餐失败: {str(e)}"
        )


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def list_subscription_plans(
    is_active: Optional[bool] = None,
    is_visible: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    查询订阅套餐列表（平台管理员）
    """
    try:
        query = db.query(SubscriptionPlan)
        
        if is_active is not None:
            query = query.filter(SubscriptionPlan.is_active == is_active)
        
        if is_visible is not None:
            query = query.filter(SubscriptionPlan.is_visible == is_visible)
        
        plans = query.order_by(SubscriptionPlan.id).all()
        return plans
        
    except Exception as e:
        logger.error(f"查询订阅套餐列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询订阅套餐列表失败: {str(e)}"
        )


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def get_subscription_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取订阅套餐详情（平台管理员）
    """
    try:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订阅套餐不存在"
            )
        return plan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取订阅套餐详情失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取订阅套餐详情失败: {str(e)}"
        )


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
async def update_subscription_plan(
    plan_id: int,
    plan_data: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新订阅套餐（平台管理员）
    """
    try:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="订阅套餐不存在"
            )
        
        # 更新字段
        update_data = plan_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(plan, field):
                setattr(plan, field, value)
        
        plan.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(plan)
        
        logger.info(f"订阅套餐已更新: id={plan.id}, updated_by={current_user.id}")
        return plan
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新订阅套餐失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新订阅套餐失败: {str(e)}"
        )


# ========== 租户订阅管理 ==========

@router.post("/tenants/{tenant_id}/subscription")
async def update_tenant_subscription(
    tenant_id: int,
    subscription_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新租户订阅（平台管理员）
    """
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在"
            )
        
        # 获取套餐信息
        plan_name = subscription_data.get("subscription_plan")
        if plan_name:
            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.name == plan_name).first()
            if not plan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"订阅套餐 {plan_name} 不存在"
                )
            
            # 更新租户订阅信息
            tenant.subscription_plan = plan_name
            tenant.subscription_start = subscription_data.get("subscription_start") or datetime.utcnow()
            tenant.subscription_end = subscription_data.get("subscription_end")
            
            # 更新使用限制（从套餐获取）
            if plan.max_users is not None:
                tenant.max_users = plan.max_users
            if plan.max_jobs is not None:
                tenant.max_jobs = plan.max_jobs
            if plan.max_resumes_per_month is not None:
                tenant.max_resumes_per_month = plan.max_resumes_per_month
        
        tenant.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(tenant)
        
        logger.info(f"租户订阅已更新: tenant_id={tenant.id}, plan={tenant.subscription_plan}, updated_by={current_user.id}")
        return {
            "success": True,
            "tenant": tenant
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新租户订阅失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新租户订阅失败: {str(e)}"
        )

