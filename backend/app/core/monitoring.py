"""
监控和指标收集
"""
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from functools import wraps
from fastapi import Request, Response

logger = logging.getLogger(__name__)

# 指标存储（生产环境应使用 Prometheus 或类似工具）
_metrics = {
    "api_requests_total": 0,
    "api_requests_by_endpoint": {},
    "api_requests_by_status": {},
    "api_response_times": [],
    "errors_total": 0,
    "errors_by_type": {},
    "llm_calls_total": 0,
    "llm_calls_by_provider": {},
    "llm_response_times": []
}


def get_metrics() -> Dict[str, Any]:
    """获取所有指标"""
    return {
        "metrics": _metrics.copy(),
        "timestamp": datetime.utcnow().isoformat()
    }


def reset_metrics():
    """重置指标（用于测试）"""
    global _metrics
    _metrics = {
        "api_requests_total": 0,
        "api_requests_by_endpoint": {},
        "api_requests_by_status": {},
        "api_response_times": [],
        "errors_total": 0,
        "errors_by_type": {},
        "llm_calls_total": 0,
        "llm_calls_by_provider": {},
        "llm_response_times": []
    }


def record_api_request(endpoint: str, status_code: int, response_time: float):
    """记录API请求指标"""
    _metrics["api_requests_total"] += 1
    
    # 按端点统计
    if endpoint not in _metrics["api_requests_by_endpoint"]:
        _metrics["api_requests_by_endpoint"][endpoint] = 0
    _metrics["api_requests_by_endpoint"][endpoint] += 1
    
    # 按状态码统计
    status_key = f"{status_code // 100}xx"
    if status_key not in _metrics["api_requests_by_status"]:
        _metrics["api_requests_by_status"][status_key] = 0
    _metrics["api_requests_by_status"][status_key] += 1
    
    # 响应时间（只保留最近1000条）
    _metrics["api_response_times"].append(response_time)
    if len(_metrics["api_response_times"]) > 1000:
        _metrics["api_response_times"] = _metrics["api_response_times"][-1000:]


def record_error(error_type: str, error_message: str = ""):
    """记录错误指标"""
    _metrics["errors_total"] += 1
    
    if error_type not in _metrics["errors_by_type"]:
        _metrics["errors_by_type"][error_type] = 0
    _metrics["errors_by_type"][error_type] += 1
    
    logger.error(f"[监控] 错误记录: {error_type} - {error_message}")


def record_llm_call(provider: str, response_time: float, success: bool = True):
    """记录LLM调用指标"""
    _metrics["llm_calls_total"] += 1
    
    if provider not in _metrics["llm_calls_by_provider"]:
        _metrics["llm_calls_by_provider"][provider] = {"total": 0, "success": 0, "failed": 0}
    
    _metrics["llm_calls_by_provider"][provider]["total"] += 1
    if success:
        _metrics["llm_calls_by_provider"][provider]["success"] += 1
    else:
        _metrics["llm_calls_by_provider"][provider]["failed"] += 1
    
    # 响应时间（只保留最近1000条）
    _metrics["llm_response_times"].append(response_time)
    if len(_metrics["llm_response_times"]) > 1000:
        _metrics["llm_response_times"] = _metrics["llm_response_times"][-1000:]


def get_average_response_time() -> float:
    """获取平均响应时间"""
    if not _metrics["api_response_times"]:
        return 0.0
    return sum(_metrics["api_response_times"]) / len(_metrics["api_response_times"])


def get_error_rate() -> float:
    """获取错误率"""
    if _metrics["api_requests_total"] == 0:
        return 0.0
    return _metrics["errors_total"] / _metrics["api_requests_total"]


async def monitoring_middleware(request: Request, call_next):
    """监控中间件：记录请求指标"""
    start_time = time.time()
    
    # 获取端点路径（去除查询参数）
    endpoint = request.url.path
    
    try:
        response = await call_next(request)
        status_code = response.status_code
        
        # 记录成功请求
        response_time = time.time() - start_time
        record_api_request(endpoint, status_code, response_time)
        
        # 记录错误（4xx和5xx）
        if status_code >= 400:
            error_type = f"http_{status_code}"
            record_error(error_type, f"{request.method} {endpoint}")
        
        return response
    except Exception as e:
        # 记录异常
        response_time = time.time() - start_time
        record_api_request(endpoint, 500, response_time)
        record_error("exception", f"{type(e).__name__}: {str(e)}")
        raise

