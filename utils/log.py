from pathlib import Path
from typing import Optional
import logging

from loguru import logger

import conf
from conf import BASE_DIR

# 配置基础日志设置 - 从conf.py移动过来
logging.basicConfig(
    level=conf.LOG_LEVEL,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s'
)


def log_formatter(record: dict) -> str:
    """
    日志记录格式化器

    Args:
        record: 包含日志元数据和消息的日志对象

    Returns:
        格式化后的日志字符串
    """
    # 去除SUCCESS级别，将其映射到INFO级别
    if record["level"].name == "SUCCESS":
        record["level"].name = "INFO"
    
    colors = {
        "TRACE": "#cfe2f3",
        "INFO": "#9cbfdd",
        "DEBUG": "#8598ea",
        "WARNING": "#dcad5a",
        "ERROR": "#ae2c2c"
    }
    color = colors.get(record["level"].name, "#b3cfe7")
    return f"<fg #70acde>{{time:YYYY-MM-DD HH:mm:ss}}</fg #70acde> | <fg {color}>{{level}}</fg {color}>: <light-white>{{message}}</light-white>\n"


# 配置loguru的控制台输出日志级别
logger.remove()  # 移除默认的控制台输出
logger.add(
    sink=lambda msg: print(msg, end=""),
    level=conf.CONSOLE_LOG_LEVEL,
    format=log_formatter
)


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
    logger.add(Path(BASE_DIR / file_path), filter=filter_record, level=conf.LOG_LEVEL, rotation="10 MB", retention="10 days", backtrace=True, diagnose=True)
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
