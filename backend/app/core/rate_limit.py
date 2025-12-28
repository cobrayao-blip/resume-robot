"""
API 速率限制模块
使用 slowapi 实现速率限制
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# 创建限流器实例
limiter = Limiter(key_func=get_remote_address)

# 速率限制配置
RATE_LIMITS = {
    "login": "5/minute",  # 登录接口：每分钟5次
    "register": "3/hour",  # 注册接口：每小时3次
    "parse_resume": "10/hour",  # 解析简历：每小时10次
    "default": "100/minute",  # 默认：每分钟100次
}


def get_rate_limit(limit_name: str = "default") -> str:
    """获取速率限制配置"""
    return RATE_LIMITS.get(limit_name, RATE_LIMITS["default"])


def setup_rate_limit(app):
    """设置速率限制到 FastAPI 应用"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """处理速率限制异常"""
        logger.warning(f"速率限制触发: {request.url} - {get_remote_address(request)}")
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "code": 429,
                "message": f"请求过于频繁，请稍后再试。限制: {exc.detail}",
            },
        )

