from pathlib import Path
from typing import Optional
from loguru import logger

import conf
from conf import BASE_DIR
from utils.log import create_logger

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
from utils.log import get_logger as get_legacy_logger