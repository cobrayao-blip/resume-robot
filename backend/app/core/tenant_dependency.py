"""
多租户依赖注入
从请求上下文中获取tenant_id，并提供给API端点使用
"""
from fastapi import Request, HTTPException, status
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def get_tenant_id(request: Request) -> Optional[int]:
    """
    从请求上下文中获取tenant_id
    
    用于API端点依赖注入：
    @router.get("/items")
    async def get_items(
        tenant_id: int = Depends(get_tenant_id),
        ...
    ):
        ...
    """
    tenant_id = getattr(request.state, 'tenant_id', None)
    
    # 如果是管理后台API，tenant_id可以为None
    is_admin_api = getattr(request.state, 'is_admin_api', False)
    if is_admin_api:
        return tenant_id
    
    # 用户侧API必须要有tenant_id
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无法获取租户信息，请重新登录"
        )
    
    return tenant_id


def require_tenant_id(request: Request) -> int:
    """
    要求必须有tenant_id（非可选）
    
    用于必须要有tenant_id的API端点：
    @router.get("/items")
    async def get_items(
        tenant_id: int = Depends(require_tenant_id),
        ...
    ):
        ...
    """
    tenant_id = getattr(request.state, 'tenant_id', None)
    
    # 如果从 request.state 中获取不到，尝试从 token 中提取
    if tenant_id is None:
        from ....core.security import get_tenant_id_from_token, get_email_from_token
        from ....models.user import User
        from ....core.database import SessionLocal
        
        try:
            authorization = request.headers.get("Authorization")
            if authorization and authorization.startswith("Bearer "):
                token = authorization.split(" ")[1]
                # 先尝试从 token 中直接获取
                tenant_id = get_tenant_id_from_token(token)
                
                # 如果 token 中没有，从用户表获取
                if tenant_id is None:
                    email = get_email_from_token(token)
                    if email:
                        db = SessionLocal()
                        try:
                            user = db.query(User).filter(User.email == email).first()
                            if user and user.tenant_id:
                                tenant_id = user.tenant_id
                                # 更新 request.state，避免重复查询
                                request.state.tenant_id = tenant_id
                        except Exception as e:
                            logger.warning(f"从用户获取tenant_id失败: {e}")
                        finally:
                            db.close()
        except Exception as e:
            logger.warning(f"尝试从token获取tenant_id失败: {e}")
    
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无法获取租户信息，请重新登录"
        )
    
    return tenant_id

