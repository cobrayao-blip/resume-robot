"""
监控和指标端点
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ....core.database import get_db
from ....core.permissions import require_super_admin
from ....models.user import User
from ....core.monitoring import get_metrics, get_average_response_time, get_error_rate

router = APIRouter()


@router.get("/metrics")
async def get_system_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    获取系统指标
    
    返回系统运行指标，包括API请求统计、错误统计、LLM调用统计等。
    
    **权限要求**: 仅超级管理员
    
    **响应示例**:
    ```json
    {
      "metrics": {
        "api_requests_total": 1000,
        "api_requests_by_endpoint": {
          "/api/v1/deepseek/parse-resume": 500,
          "/api/v1/auth/login": 300
        },
        "api_requests_by_status": {
          "2xx": 950,
          "4xx": 30,
          "5xx": 20
        },
        "api_response_times": [0.1, 0.2, ...],
        "errors_total": 50,
        "errors_by_type": {
          "http_400": 20,
          "http_500": 30
        },
        "llm_calls_total": 200,
        "llm_calls_by_provider": {
          "deepseek": {
            "total": 150,
            "success": 145,
            "failed": 5
          },
          "doubao": {
            "total": 50,
            "success": 48,
            "failed": 2
          }
        },
        "llm_response_times": [2.5, 3.1, ...]
      },
      "statistics": {
        "average_response_time": 0.25,
        "error_rate": 0.05,
        "llm_success_rate": 0.965
      },
      "timestamp": "2025-12-09T10:00:00Z"
    }
    ```
    """
    metrics = get_metrics()
    
    # 计算统计信息
    statistics = {
        "average_response_time": get_average_response_time(),
        "error_rate": get_error_rate(),
    }
    
    # 计算LLM成功率
    llm_total = metrics["metrics"]["llm_calls_total"]
    if llm_total > 0:
        llm_success = sum(
            provider_stats["success"]
            for provider_stats in metrics["metrics"]["llm_calls_by_provider"].values()
        )
        statistics["llm_success_rate"] = llm_success / llm_total
    else:
        statistics["llm_success_rate"] = 0.0
    
    return {
        **metrics,
        "statistics": statistics
    }

