"""
系统配置API（管理后台）
平台管理员可以管理系统配置和查看平台统计
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, Any
import logging

from .....core.database import get_db
from .....core.permissions import require_admin
from .....models.user import User
from .....models.tenant import Tenant
from .....models.job import JobPosition, ResumeJobMatch
from .....models.resume import CandidateResume

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/config")
async def get_system_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取系统配置（平台管理员）
    """
    try:
        from .....models.system_settings import SystemSetting
        from .....schemas.system_settings import SystemSettingResponse
        
        # 获取所有系统配置
        settings = db.query(SystemSetting).all()
        
        config = {}
        for setting in settings:
            config[setting.key] = {
                "value": setting.value,
                "description": setting.description,
                "type": setting.setting_type
            }
        
        return {
            "success": True,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"获取系统配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统配置失败: {str(e)}"
        )


@router.put("/config")
async def update_system_config(
    config_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新系统配置（平台管理员）
    """
    try:
        from .....models.system_settings import SystemSetting
        from datetime import datetime
        
        updated_count = 0
        for key, value in config_data.items():
            setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting:
                setting.value = str(value)
                setting.updated_at = datetime.utcnow()
                updated_count += 1
        
        db.commit()
        
        logger.info(f"系统配置已更新: {updated_count}项, updated_by={current_user.id}")
        return {
            "success": True,
            "message": f"已更新 {updated_count} 项配置"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"更新系统配置失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新系统配置失败: {str(e)}"
        )


@router.get("/stats")
async def get_platform_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取平台数据统计（平台管理员）
    """
    try:
        # 租户统计
        total_tenants = db.query(Tenant).count()
        active_tenants = db.query(Tenant).filter(Tenant.status == "active").count()
        suspended_tenants = db.query(Tenant).filter(Tenant.status == "suspended").count()
        
        # 按套餐统计租户
        from sqlalchemy import func
        tenant_by_plan = db.query(
            Tenant.subscription_plan,
            func.count(Tenant.id).label("count")
        ).group_by(Tenant.subscription_plan).all()
        tenant_by_plan_dict = {plan: count for plan, count in tenant_by_plan}
        
        # 用户统计
        from .....models.user import User
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        
        # 岗位统计
        total_jobs = db.query(JobPosition).count()
        published_jobs = db.query(JobPosition).filter(JobPosition.status == "published").count()
        
        # 简历统计
        total_resumes = db.query(CandidateResume).count()
        
        # 匹配统计
        total_matches = db.query(ResumeJobMatch).count()
        high_match_matches = db.query(ResumeJobMatch).filter(
            ResumeJobMatch.match_label.in_(["强烈推荐", "推荐"])
        ).count()
        
        # 本月简历处理量统计
        from datetime import datetime, timedelta
        this_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_resumes = db.query(CandidateResume).filter(
            CandidateResume.created_at >= this_month_start
        ).count()
        
        return {
            "success": True,
            "stats": {
                "tenants": {
                    "total": total_tenants,
                    "active": active_tenants,
                    "suspended": suspended_tenants,
                    "by_plan": tenant_by_plan_dict
                },
                "users": {
                    "total": total_users,
                    "active": active_users
                },
                "jobs": {
                    "total": total_jobs,
                    "published": published_jobs
                },
                "resumes": {
                    "total": total_resumes,
                    "this_month": this_month_resumes
                },
                "matches": {
                    "total": total_matches,
                    "high_match": high_match_matches
                }
            }
        }
        
    except Exception as e:
        logger.error(f"获取平台统计失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取平台统计失败: {str(e)}"
        )

