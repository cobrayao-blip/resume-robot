"""
权限检查工具
"""
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from typing import List
from ..core.database import get_db
from ..models.user import User
from .security import get_email_from_token
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def require_user_types(allowed_types: List[str]):
    """
    权限检查装饰器工厂
    创建一个依赖函数，检查用户类型是否在允许的列表中
    """
    async def check_permission(
        db: Session = Depends(get_db),
        token: str = Depends(oauth2_scheme)
    ) -> User:
        email = get_email_from_token(token)
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌"
            )
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被禁用"
            )
        
        if user.user_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足，需要以下角色之一: " + ", ".join(allowed_types)
            )
        
        return user
    
    return check_permission

# 预定义的权限检查依赖
require_admin = require_user_types(["super_admin", "template_designer"])
require_super_admin = require_user_types(["super_admin"])

