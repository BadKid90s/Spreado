"""
日志工具模块
"""

import logging

from ..conf import LOG_LEVEL, LOGS_DIR


def setup_logging():
    """
    设置全局日志配置
    """
    # 创建日志目录
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # 配置根日志
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s: [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            # 文件处理器
            logging.FileHandler(
                filename=LOGS_DIR / "uploader.log", mode="a", encoding="utf-8"
            ),
            # 控制台处理器
            logging.StreamHandler(),
        ],
    )


class UploaderLogger(logging.Logger):
    """
    上传器专用日志记录器
    """

    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

    def info(self, msg, *args, context="GENERAL", **kwargs):
        """
        记录信息日志

        Args:
            msg: 日志消息
            context: 日志上下文
            *args: 其他参数
            **kwargs: 其他关键字参数
        """
        formatted_msg = f"[UPLOADER-{self.name.upper()}] {context.upper()}: {msg}"
        super().info(formatted_msg, *args, **kwargs)

    def warning(self, msg, *args, context="GENERAL", **kwargs):
        """
        记录警告日志

        Args:
            msg: 日志消息
            context: 日志上下文
            *args: 其他参数
            **kwargs: 其他关键字参数
        """
        formatted_msg = f"[UPLOADER-{self.name.upper()}] {context.upper()}: {msg}"
        super().warning(formatted_msg, *args, **kwargs)

    def error(self, msg, *args, context="GENERAL", **kwargs):
        """
        记录错误日志

        Args:
            msg: 日志消息
            context: 日志上下文
            *args: 其他参数
            **kwargs: 其他关键字参数
        """
        formatted_msg = f"[UPLOADER-{self.name.upper()}] {context.upper()}: {msg}"
        super().error(formatted_msg, *args, **kwargs)

    def debug(self, msg, *args, context="GENERAL", **kwargs):
        """
        记录调试日志

        Args:
            msg: 日志消息
            context: 日志上下文
            *args: 其他参数
            **kwargs: 其他关键字参数
        """
        formatted_msg = f"[UPLOADER-{self.name.upper()}] {context.upper()}: {msg}"
        super().debug(formatted_msg, *args, **kwargs)


# 注册自定义日志记录器类
logging.setLoggerClass(UploaderLogger)


def get_logger(name: str) -> UploaderLogger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        UploaderLogger实例
    """
    return logging.getLogger(name)


def get_uploader_logger(platform_name: str) -> UploaderLogger:
    """
    获取上传器专用日志记录器

    Args:
        platform_name: 平台名称

    Returns:
        UploaderLogger实例
    """
    return get_logger(platform_name)


# 初始化日志配置
setup_logging()
