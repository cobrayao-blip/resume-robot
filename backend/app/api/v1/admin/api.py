"""
管理后台API路由
所有管理后台相关的API端点都挂载在这里
"""
from fastapi import APIRouter
from .endpoints import tenants, subscriptions, system

admin_router = APIRouter()

admin_router.include_router(tenants.router, prefix="/tenants", tags=["admin-tenants"])
admin_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["admin-subscriptions"])
admin_router.include_router(system.router, prefix="/system", tags=["admin-system"])

