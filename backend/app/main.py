from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import sys
import os
import traceback
from .core.config import settings
from .core.responses import APIResponse
from .api.v1.api import api_router
from .core.database import SessionLocal
from .core.security import get_password_hash
from .core.rate_limit import setup_rate_limit
from .models.user import User
from .services.cache_service import cache_service

# 配置日志：使用结构化日志或普通日志
from .core.structured_logging import setup_logging, get_logger

# 根据环境变量决定是否使用结构化日志
USE_STRUCTURED_LOGGING = os.getenv("USE_STRUCTURED_LOGGING", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if settings.debug else "WARNING")
ENABLE_FILE_LOGGING = os.getenv("ENABLE_FILE_LOGGING", "false").lower() == "true"
LOG_DIR = os.getenv("LOG_DIR", "logs")

setup_logging(
    use_structured=USE_STRUCTURED_LOGGING,
    log_level=LOG_LEVEL,
    enable_file_logging=ENABLE_FILE_LOGGING,
    log_dir=LOG_DIR
)

logger = get_logger(__name__)

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    debug=settings.debug
)

# CORS中间件 - 生产环境限制方法和头部
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"] if not settings.debug else ["*"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"] if not settings.debug else ["*"],
)

# 设置速率限制
setup_rate_limit(app)

# 添加多租户中间件（必须在监控中间件之前）
from .core.tenant_middleware import TenantMiddleware
app.add_middleware(TenantMiddleware)

# 添加监控中间件
from .core.monitoring import monitoring_middleware
app.middleware("http")(monitoring_middleware)

# 包含API路由
app.include_router(api_router, prefix="/api/v1")

# 请求验证错误处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数验证错误"""
    errors = exc.errors()
    error_details = []
    for error in errors:
        error_details.append({
            "field": ".".join(str(loc) for loc in error.get("loc", [])),
            "message": error.get("msg", "验证失败"),
            "type": error.get("type", "validation_error")
        })
    
    logger.warning(f"请求验证失败: {request.url} - {error_details}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=APIResponse.error(
            code=422,
            message="请求参数验证失败",
            details={"errors": error_details}
        ),
    )

# HTTP异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 HTTP 异常"""
    logger.info(f"HTTP异常: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse.error(
            code=exc.status_code,
            message=exc.detail
        ),
    )

# 全局异常处理（放在最后，作为兜底）
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    error_traceback = traceback.format_exc()
    logger.error(
        f"未处理的异常: {type(exc).__name__}: {str(exc)}\n"
        f"请求路径: {request.url}\n"
        f"堆栈跟踪:\n{error_traceback}"
    )
    
    # 在生产环境中，不返回详细的错误信息
    error_message = "服务器内部错误"
    if settings.debug:
        error_message = f"{type(exc).__name__}: {str(exc)}"
    
    return JSONResponse(
        status_code=500,
        content=APIResponse.error(
            code=500,
            message=error_message
        ),
    )

@app.get("/")
async def root():
    return {
        "message": "ResumeAI Platform API",
        "version": settings.version
    }

@app.get("/health")
async def health_check():
    """
    健康检查端点
    
    用于监控系统运行状态，检查数据库和Redis连接。
    
    **响应示例**:
    ```json
    {
      "status": "healthy",
      "database": "connected",
      "redis": "connected",
      "version": "1.0.0"
    }
    ```
    """
    from .services.cache_service import cache_service
    
    health_status = {
        "status": "healthy",
        "version": settings.version
    }
    
    # 检查数据库连接
    try:
        from .core.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
        # 检查Redis连接
    try:
        if cache_service.redis_client:
            await cache_service.redis_client.ping()
            health_status["redis"] = "connected"
        else:
            health_status["redis"] = "not_configured"
    except Exception as e:
        health_status["redis"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 连接Redis缓存
    await cache_service.connect()
    
    # 在开发/调试下创建演示账号
    if settings.debug:
        seed_demo_user()

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    # 关闭Redis连接
    await cache_service.close()

def seed_demo_user():
    """创建演示账号"""
    db = SessionLocal()
    try:
        email = "demo@example.com"
        user = db.query(User).filter(User.email == email).first()
        if not user:
            from datetime import timedelta
            from sqlalchemy.sql import func
            demo = User(
                email=email,
                password_hash=get_password_hash("demo1234"),
                full_name="Demo",
                user_type="trial_user",
                is_active=True,
                registration_status="approved",
                is_verified=True,
                monthly_usage_limit=10,  # 演示账户给10次使用机会
                current_month_usage=0,
                usage_reset_date=func.now() + timedelta(days=30),
            )
            db.add(demo)
            db.commit()
        else:
            # 如果用户已存在，确保设置了使用限制
            if user.monthly_usage_limit is None:
                user.monthly_usage_limit = 10
                user.registration_status = "approved"
                user.is_active = True
                user.is_verified = True
                db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

