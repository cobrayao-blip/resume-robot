"""
使用限制检查中间件
"""
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..core.database import get_db
from ..models.user import User
from ..api.v1.endpoints.users import get_current_user

def check_usage_limit():
    """
    使用限制检查依赖
    检查用户是否还有剩余使用次数
    """
    async def check_limit(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
    ) -> User:
        # 管理员和模板设计师不受限制
        if current_user.user_type in ["super_admin", "template_designer"]:
            return current_user
        
        # 检查使用次数重置日期
        now = datetime.utcnow()
        if current_user.usage_reset_date and current_user.usage_reset_date < now:
            # 重置使用次数
            current_user.current_month_usage = 0
            current_user.usage_reset_date = now + timedelta(days=30)
            db.commit()
        
        # 如果没有设置重置日期，设置一个
        if not current_user.usage_reset_date:
            current_user.usage_reset_date = now + timedelta(days=30)
            db.commit()
        
        # 检查是否超过限制
        # 如果管理员没有设置限制，则不允许使用（必须由管理员设置）
        if current_user.monthly_usage_limit is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="使用次数限制未设置，请联系管理员"
            )
        
        limit = current_user.monthly_usage_limit
        if current_user.current_month_usage >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="USAGE_LIMIT_EXCEEDED:你的使用次数超过上线，请联系管理员！"
            )
        
        return current_user
    
    return check_limit

def increment_usage(db: Session, user: User):
    """
    增加用户使用次数
    """
    user.current_month_usage = (user.current_month_usage or 0) + 1
    user.resume_generated_count = (user.resume_generated_count or 0) + 1
    db.commit()

