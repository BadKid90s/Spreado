from pathlib import Path
from typing import Optional

from loguru import logger

from conf import BASE_DIR


def log_formatter(record: dict) -> str:
    """
    日志记录格式化器

    Args:
        record: 包含日志元数据和消息的日志对象

    Returns:
        格式化后的日志字符串
    """
    colors = {
        "TRACE": "#cfe2f3",
        "INFO": "#9cbfdd",
        "DEBUG": "#8598ea",
        "WARNING": "#dcad5a",
        "SUCCESS": "#3dd08d",
        "ERROR": "#ae2c2c"
    }
    color = colors.get(record["level"].name, "#b3cfe7")
    return f"<fg #70acde>{{time:YYYY-MM-DD HH:mm:ss}}</fg #70acde> | <fg {color}>{{level}}</fg {color}>: <light-white>{{message}}</light-white>\n"


def create_logger(log_name: str, file_path: str):
    """
    为不同业务模块创建自定义日志记录器

    Args:
        log_name: 日志名称
        file_path: 日志文件路径

    Returns:
        配置好的日志记录器
    """
    def filter_record(record):
        return record["extra"].get("business_name") == log_name

    Path(BASE_DIR / file_path).parent.mkdir(exist_ok=True)
    logger.add(Path(BASE_DIR / file_path), filter=filter_record, level="INFO", rotation="10 MB", retention="10 days", backtrace=True, diagnose=True)
    return logger.bind(business_name=log_name)


def get_logger(name: str, log_file: Optional[str] = None) -> logger:
    """
    获取或创建日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径（可选），如果提供则创建文件日志

    Returns:
        配置好的日志记录器
    """
    if log_file:
        return create_logger(name, log_file)
    return logger.bind(business_name=name)
