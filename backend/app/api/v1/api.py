from fastapi import APIRouter
from .endpoints import auth, users, deepseek, export, templates, resumes, parsed_resumes, files, source_files, admin, monitoring, jobs, batch, organization, tenant_users
from .admin.api import admin_router

api_router = APIRouter()

# ========== 用户侧API（自动注入tenant_id） ==========
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(deepseek.router, prefix="/deepseek", tags=["deepseek"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(templates.router, prefix="/templates", tags=["templates"])  # 推荐报告模板管理
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(parsed_resumes.router, prefix="/parsed-resumes", tags=["parsed-resumes"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(source_files.router, prefix="/source-files", tags=["source-files"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(batch.router, prefix="/batch", tags=["batch"])
api_router.include_router(organization.router, prefix="/organization", tags=["organization"])
api_router.include_router(tenant_users.router, prefix="/tenant-users", tags=["tenant-users"])

# ========== 管理后台API（需要平台管理员权限） ==========
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])  # 新的管理后台API（租户、订阅、系统配置）
api_router.include_router(admin.router, prefix="/admin", tags=["admin-legacy"])  # 保留旧的admin API（用户管理、模板管理等）