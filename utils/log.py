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
    
    colors = {
        "TRACE": "#cfe2f3",
        "INFO": "#9cbfdd",
        "DEBUG": "#8598ea",
        "WARNING": "#dcad5a",
        "ERROR": "#ae2c2c"
    }
    color = colors.get(record["level"].name, "#b3cfe7")
    return f"<fg #70acde>{{time:YYYY-MM-DD HH:mm:ss Z}}</fg #70acde> | <fg {color}>{{level}}</fg {color}>: <light-white>{{message}}</light-white>\n"


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


# 标准化的上传器日志前缀格式
UPLOADER_LOG_PREFIX = "[UPLOADER-{platform}] {context}: {message}"

# 标准化的时间戳格式
STANDARD_TIME_FORMAT = "YYYY-MM-DD HH:mm:ss Z"

# 上传器日志文件位置
UPLOADER_LOG_FILE = "logs/uploader/{platform}.log"



def get_uploader_logger(platform_name: str, context: Optional[str] = None) -> logger:
    """
    获取标准化的上传器日志记录器

    Args:
        platform_name: 平台名称
        context: 上传过程上下文（可选）

    Returns:
        配置好的标准化日志记录器
    """
    # 创建上传器专用日志记录器
    log_file = UPLOADER_LOG_FILE.format(platform=platform_name.lower())
    uploader_logger = create_logger(f"uploader-{platform_name}", log_file)

    # 封装日志方法，添加标准化前缀
    class UploaderLoggerWrapper:
        def __init__(self, logger_instance, platform, ctx=None):
            self.logger = logger_instance
            self.platform = platform
            self.context = ctx

        def _format_message(self, message, ctx=None):
            """格式化消息，添加标准化前缀"""
            current_context = ctx or self.context or "GENERAL"
            return UPLOADER_LOG_PREFIX.format(
                platform=self.platform.upper(),
                context=current_context.upper(),
                message=message
            )

        def debug(self, message, context=None):
            self.logger.debug(self._format_message(message, context))

        def info(self, message, context=None):
            self.logger.info(self._format_message(message, context))

        def warning(self, message, context=None):
            self.logger.warning(self._format_message(message, context))

        def error(self, message, context=None):
            self.logger.error(self._format_message(message, context))

        def exception(self, message, context=None):
            self.logger.exception(self._format_message(message, context))

        # 保持原有属性访问
        def __getattr__(self, name):
            return getattr(self.logger, name)

    return UploaderLoggerWrapper(uploader_logger, platform_name, context)


# 向后兼容的导出
get_legacy_logger = get_logger
