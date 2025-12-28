"""
日志轮转配置
"""
import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path


def setup_file_logging(
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    when: str = "midnight",  # 每天午夜轮转
    interval: int = 1
):
    """
    设置文件日志轮转
    
    Args:
        log_dir: 日志目录
        max_bytes: 单个日志文件最大大小（字节）
        backup_count: 保留的备份文件数量
        when: 时间轮转间隔（'midnight', 'H', 'D'等）
        interval: 轮转间隔数量
    """
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 按大小轮转的处理器（用于应用日志）
    app_log_file = log_path / "app.log"
    app_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    root_logger.addHandler(app_handler)
    
    # 按时间轮转的处理器（用于错误日志）
    error_log_file = log_path / "error.log"
    error_handler = TimedRotatingFileHandler(
        error_log_file,
        when=when,
        interval=interval,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    root_logger.addHandler(error_handler)
    
    return app_handler, error_handler

