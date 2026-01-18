"""
项目配置文件
"""
from pathlib import Path

# 项目基础目录
BASE_DIR = Path(__file__).parent

# 日志配置 - 使用loguru兼容的字符串格式
LOG_LEVEL = "INFO"  # 设置日志级别为INFO，只打印INFO及以上级别的日志

# 控制台日志级别
CONSOLE_LOG_LEVEL = "INFO"  # 控制台输出的日志级别

