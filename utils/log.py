from pathlib import Path
from typing import Optional, Dict, Any, Union

from loguru import logger

import conf
from conf import LOGS_DIR

# 移除默认的控制台输出
logger.remove()


def log_formatter(record: Dict[str, Any]) -> str:
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
    return f"<fg #70acde>{{time:YYYY-MM-DD HH:mm:ss Z}}</fg #70acde> | <fg {color}>{{level}}</fg {color}> | <cyan>{{name}}</cyan>:<magenta>{{function}}</magenta>:<yellow>{{line}}</yellow> - <light-white>{{message}}</light-white>\n"


def file_formatter(record: Dict[str, Any]) -> str:
    """
    文件日志格式化器，不包含颜色

    Args:
        record: 包含日志元数据和消息的日志对象

    Returns:
        格式化后的日志字符串
    """
    return f"{{time:YYYY-MM-DD HH:mm:ss Z}} | {{level: <8}} | {{name}}:{{function}}:{{line}} - {{message}}\n"


# 配置控制台日志
logger.add(
    sink=lambda msg: print(msg, end=""),
    level=conf.CONSOLE_LOG_LEVEL,
    format=log_formatter,
    enqueue=True  # 异步处理日志，提高性能
)

# 配置系统日志文件
logger.add(
    sink=LOGS_DIR / "system.log",
    level=conf.LOG_LEVEL,
    format=file_formatter,
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    backtrace=True,
    diagnose=True,
    enqueue=True
)


# 日志记录器缓存
def _get_logger_cache():
    if not hasattr(_get_logger_cache, "_cache"):
        _get_logger_cache._cache = {}
    return _get_logger_cache._cache


def create_logger(log_name: str, file_path: Optional[Union[str, Path]] = None):
    """
    为不同业务模块创建自定义日志记录器

    Args:
        log_name: 日志名称
        file_path: 日志文件路径（可选），如果提供则创建文件日志

    Returns:
        配置好的日志记录器
    """
    def filter_record(record: Dict[str, Any]) -> bool:
        return record["extra"].get("business_name") == log_name

    logger_instance = logger.bind(business_name=log_name)
    
    # 如果提供了文件路径，添加文件日志
    if file_path:
        log_file = LOGS_DIR / file_path
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_file,
            filter=filter_record,
            level=conf.LOG_LEVEL,
            format=file_formatter,
            rotation="10 MB",
            retention="15 days",
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True
        )
    
    return logger_instance


def get_logger(name: str, log_file: Optional[str] = None):
    """
    获取或创建日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径（可选），如果提供则创建文件日志

    Returns:
        配置好的日志记录器
    """
    cache = _get_logger_cache()
    cache_key = f"{name}:{log_file}"
    
    if cache_key not in cache:
        if log_file:
            cache[cache_key] = create_logger(name, log_file)
        else:
            cache[cache_key] = logger.bind(business_name=name)
    
    return cache[cache_key]


# 标准化的上传器日志前缀格式
UPLOADER_LOG_PREFIX = "[UPLOADER-{platform}] {context}: {message}"

# 标准化的时间戳格式
STANDARD_TIME_FORMAT = "YYYY-MM-DD HH:mm:ss Z"

# 上传器日志文件位置
UPLOADER_LOG_FILE = "uploader/{platform}.log"



def get_uploader_logger(platform_name: str, context: Optional[str] = None):
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

        def trace(self, message, context=None):
            self.logger.trace(self._format_message(message, context))

        def debug(self, message, context=None):
            self.logger.debug(self._format_message(message, context))

        def info(self, message, context=None):
            self.logger.info(self._format_message(message, context))

        def warning(self, message, context=None):
            self.logger.warning(self._format_message(message, context))

        def error(self, message, context=None):
            self.logger.error(self._format_message(message, context))

        def critical(self, message, context=None):
            self.logger.critical(self._format_message(message, context))

        def exception(self, message, context=None):
            self.logger.exception(self._format_message(message, context))

        # 保持原有属性访问
        def __getattr__(self, name):
            return getattr(self.logger, name)

    return UploaderLoggerWrapper(uploader_logger, platform_name, context)


# 向后兼容的导出
get_legacy_logger = get_logger


# 确保日志目录存在
LOGS_DIR.mkdir(parents=True, exist_ok=True)
