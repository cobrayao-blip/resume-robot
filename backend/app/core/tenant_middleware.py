"""
多租户中间件
自动从JWT Token中提取tenant_id，并注入到请求上下文中
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import logging
from .security import get_email_from_token, get_tenant_id_from_token
from .database import SessionLocal
from ..models.user import User

logger = logging.getLogger(__name__)


async def get_tenant_id_from_request(request: Request) -> Optional[int]:
    """
    从请求中提取tenant_id
    
    优先级：
    1. 从JWT Token中提取（用户登录后，直接从Token中获取tenant_id）
    2. 从请求头中提取（X-Tenant-ID，用于管理后台）
    3. 从查询参数中提取（tenant_id，用于测试）
    """
    # 方法1：从JWT Token中直接提取tenant_id（优先，避免数据库查询）
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        tenant_id = get_tenant_id_from_token(token)
        if tenant_id is not None:
            return tenant_id
        
        # 如果Token中没有tenant_id，尝试从数据库查询（向后兼容）
        email = get_email_from_token(token)
        if email:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.email == email).first()
                if user and hasattr(user, 'tenant_id'):
                    return user.tenant_id
            except Exception as e:
                logger.warning(f"从用户获取tenant_id失败: {e}")
            finally:
                db.close()
    
    # 方法2：从请求头中提取（管理后台使用）
    tenant_id_header = request.headers.get("X-Tenant-ID")
    if tenant_id_header:
        try:
            return int(tenant_id_header)
        except ValueError:
            pass
    
    # 方法3：从查询参数中提取（测试用）
    tenant_id_param = request.query_params.get("tenant_id")
    if tenant_id_param:
        try:
            return int(tenant_id_param)
        except ValueError:
            pass
    
    return None


class TenantMiddleware(BaseHTTPMiddleware):
    """
    多租户中间件
    自动从请求中提取tenant_id，并设置到request.state中
    """
    
    async def dispatch(self, request: Request, call_next):
        # 排除管理后台API和认证API（不需要tenant_id）
        path = request.url.path
        
        # 管理后台API不需要tenant_id（平台管理员可以跨租户操作）
        if path.startswith("/api/v1/admin/"):
            request.state.tenant_id = None
            request.state.is_admin_api = True
            response = await call_next(request)
            return response
        
        # 认证API不需要tenant_id（登录时还没有tenant_id）
        if path.startswith("/api/v1/auth/"):
            request.state.tenant_id = None
            request.state.is_admin_api = False
            response = await call_next(request)
            return response
        
        # 健康检查API不需要tenant_id
        if path.startswith("/api/v1/monitoring/health"):
            request.state.tenant_id = None
            request.state.is_admin_api = False
            response = await call_next(request)
            return response
        
        # 其他API需要tenant_id
        tenant_id = await get_tenant_id_from_request(request)
        request.state.tenant_id = tenant_id
        request.state.is_admin_api = False
        
        # 如果无法获取tenant_id，记录警告但不阻止请求（某些API可能允许匿名访问）
        if tenant_id is None:
            logger.warning(f"无法从请求中提取tenant_id: {path}")
        
        response = await call_next(request)
        return response

