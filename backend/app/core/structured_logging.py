"""
结构化日志配置
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器（JSON格式）"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # 添加模块和行号（仅在调试模式下）
        if record.levelno >= logging.DEBUG:
            log_data["module"] = record.module
            log_data["line"] = record.lineno
            log_data["function"] = record.funcName
        
        return json.dumps(log_data, ensure_ascii=False)


class PlainFormatter(logging.Formatter):
    """普通文本格式化器（开发环境使用）"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(
    use_structured: bool = False, 
    log_level: str = "INFO",
    enable_file_logging: bool = False,
    log_dir: str = "logs"
):
    """
    设置日志配置
    
    Args:
        use_structured: 是否使用结构化日志（JSON格式）
        log_level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        enable_file_logging: 是否启用文件日志（日志轮转）
        log_dir: 日志目录（仅在启用文件日志时有效）
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # 选择格式化器
    if use_structured:
        formatter = StructuredFormatter()
    else:
        formatter = PlainFormatter()
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 如果启用文件日志，添加文件处理器
    if enable_file_logging:
        from .log_rotation import setup_file_logging
        try:
            setup_file_logging(log_dir=log_dir)
            # 使用临时logger记录（因为此时logger可能还未完全初始化）
            temp_logger = logging.getLogger(__name__)
            temp_logger.info(f"文件日志已启用，日志目录: {log_dir}")
        except Exception as e:
            temp_logger = logging.getLogger(__name__)
            temp_logger.warning(f"启用文件日志失败: {e}")
    
    # 配置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)

