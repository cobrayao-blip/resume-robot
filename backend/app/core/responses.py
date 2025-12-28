"""
统一API响应格式
"""
from typing import Any, Optional, Dict, List
from fastapi.responses import JSONResponse
from fastapi import status


class APIResponse:
    """统一API响应格式"""
    
    @staticmethod
    def success(
        data: Any = None,
        message: str = "操作成功",
        status_code: int = status.HTTP_200_OK
    ) -> Dict[str, Any]:
        """
        成功响应
        
        Args:
            data: 响应数据
            message: 响应消息
            status_code: HTTP状态码
            
        Returns:
            标准化的成功响应字典
        """
        response = {
            "success": True,
            "message": message
        }
        if data is not None:
            response["data"] = data
        return response
    
    @staticmethod
    def error(
        code: int,
        message: str,
        details: Optional[Any] = None,
        status_code: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        错误响应
        
        Args:
            code: 错误代码
            message: 错误消息
            details: 错误详情
            status_code: HTTP状态码（如果不提供，使用code）
            
        Returns:
            标准化的错误响应字典
        """
        response = {
            "success": False,
            "code": code,
            "message": message
        }
        if details is not None:
            response["details"] = details
        return response
    
    @staticmethod
    def paginated(
        data: List[Any],
        total: int,
        page: int,
        page_size: int,
        message: str = "查询成功"
    ) -> Dict[str, Any]:
        """
        分页响应
        
        Args:
            data: 数据列表
            total: 总记录数
            page: 当前页码
            page_size: 每页大小
            message: 响应消息
            
        Returns:
            标准化的分页响应字典
        """
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return {
            "success": True,
            "message": message,
            "data": data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }


class ErrorResponse(JSONResponse):
    """错误响应JSONResponse"""
    
    def __init__(
        self,
        code: int,
        message: str,
        details: Optional[Any] = None,
        status_code: Optional[int] = None
    ):
        """
        创建错误响应
        
        Args:
            code: 错误代码
            message: 错误消息
            details: 错误详情
            status_code: HTTP状态码（如果不提供，使用code）
        """
        content = APIResponse.error(code, message, details)
        super().__init__(
            status_code=status_code or code,
            content=content
        )


class SuccessResponse(JSONResponse):
    """成功响应JSONResponse"""
    
    def __init__(
        self,
        data: Any = None,
        message: str = "操作成功",
        status_code: int = status.HTTP_200_OK
    ):
        """
        创建成功响应
        
        Args:
            data: 响应数据
            message: 响应消息
            status_code: HTTP状态码
        """
        content = APIResponse.success(data, message)
        super().__init__(
            status_code=status_code,
            content=content
        )

