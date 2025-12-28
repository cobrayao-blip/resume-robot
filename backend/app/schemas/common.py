"""
通用响应模式
"""
from pydantic import BaseModel
from typing import Optional, Any, Generic, TypeVar

T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    """统一的 API 响应格式"""
    success: bool
    code: int
    message: str
    data: Optional[T] = None
    
    @classmethod
    def success_response(cls, data: T = None, message: str = "操作成功", code: int = 200):
        """成功响应"""
        return cls(success=True, code=code, message=message, data=data)
    
    @classmethod
    def error_response(cls, code: int, message: str, data: Any = None):
        """错误响应"""
        return cls(success=False, code=code, message=message, data=data)


class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None

