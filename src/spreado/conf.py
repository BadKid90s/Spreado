"""
项目配置文件
"""

from pathlib import Path

# 包内基础目录（仅用于定位包内资源，例如 examples/）
BASE_DIR = Path(__file__).parent

# 运行时数据目录：cookies、logs 写到调用者的工作目录下，避免污染包目录
RUNTIME_DIR = Path.cwd()

# Cookies配置
COOKIES_DIR = RUNTIME_DIR / "cookies"  # 统一的Cookies目录

# 日志配置 - 使用loguru兼容的字符串格式
LOG_LEVEL = "INFO"  # 设置日志级别为INFO，只打印INFO及以上级别的日志

# 控制台日志级别
CONSOLE_LOG_LEVEL = "INFO"  # 控制台输出的日志级别

# 日志文件目录
LOGS_DIR = RUNTIME_DIR / "logs"

# 插件目录
PLUGINS_DIR = BASE_DIR / "plugins"
