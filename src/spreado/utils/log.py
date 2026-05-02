"""阶段化日志工具

提供 StepLogger，支持：
- with log.step("name", **fields):  自动记录开始/结束/耗时/成功失败
- log.info(msg, **fields)           key=value 形式追加结构化字段，便于 grep
- TTY 上启用颜色，文件输出保持纯文本
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator

from ..conf import LOG_LEVEL, LOGS_DIR

_ICON_START = "▶"
_ICON_OK = "✓"
_ICON_FAIL = "✗"

# ANSI 颜色
_C_RESET = "\033[0m"
_C_DIM = "\033[2m"
_C_GREEN = "\033[32m"
_C_RED = "\033[31m"
_C_YELLOW = "\033[33m"
_C_CYAN = "\033[36m"


def _format_fields(fields: dict[str, Any]) -> str:
    if not fields:
        return ""
    parts = []
    for k, v in fields.items():
        if v is None:
            continue
        s = str(v)
        if " " in s or "=" in s:
            s = f'"{s}"'
        parts.append(f"{k}={s}")
    return (" " + " ".join(parts)) if parts else ""


class _StreamFormatter(logging.Formatter):
    """终端格式：彩色"""

    _LVL_COLOR = {
        "DEBUG": _C_DIM,
        "INFO": _C_CYAN,
        "WARNING": _C_YELLOW,
        "ERROR": _C_RED,
        "CRITICAL": _C_RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%H:%M:%S")
        platform = getattr(record, "platform", record.name)
        color = self._LVL_COLOR.get(record.levelname, "")
        lvl = f"{color}{record.levelname:<5}{_C_RESET}"
        plat = f"{_C_DIM}[{platform}]{_C_RESET}"
        return f"{_C_DIM}{ts}{_C_RESET} {lvl} {plat} {record.getMessage()}"


class _FileFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        platform = getattr(record, "platform", record.name)
        return f"{ts} | {record.levelname:<5} | [{platform}] {record.getMessage()}"


def setup_logging() -> None:
    """初始化根 logger（幂等）。"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if getattr(root, "_spreado_configured", False):
        return
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    file_h = logging.FileHandler(LOGS_DIR / "uploader.log", mode="a", encoding="utf-8")
    file_h.setFormatter(_FileFormatter())

    stream_h = logging.StreamHandler()
    if sys.stderr.isatty():
        stream_h.setFormatter(_StreamFormatter())
    else:
        stream_h.setFormatter(_FileFormatter())

    # 清掉默认 handler，避免双写
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(file_h)
    root.addHandler(stream_h)
    root._spreado_configured = True  # type: ignore[attr-defined]


class StepLogger(logging.LoggerAdapter):
    """阶段化日志适配器。

    所有 record 都会带 platform 字段，由 formatter 输出。
    """

    def __init__(self, logger: logging.Logger, platform: str):
        super().__init__(logger, {"platform": platform})
        self.platform = platform

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("platform", self.platform)
        return msg, kwargs

    # 便捷接口：消息 + key=value 字段
    def info(self, msg: str, *args: Any, **fields: Any) -> None:  # type: ignore[override]
        super().info(f"{msg}{_format_fields(fields)}", *args)

    def warning(self, msg: str, *args: Any, **fields: Any) -> None:  # type: ignore[override]
        super().warning(f"{msg}{_format_fields(fields)}", *args)

    def error(self, msg: str, *args: Any, **fields: Any) -> None:  # type: ignore[override]
        super().error(f"{msg}{_format_fields(fields)}", *args)

    def debug(self, msg: str, *args: Any, **fields: Any) -> None:  # type: ignore[override]
        super().debug(f"{msg}{_format_fields(fields)}", *args)

    @contextmanager
    def step(self, name: str, **fields: Any) -> Iterator["_StepHandle"]:
        """记录一个阶段，自动输出开始/结束/耗时。

        失败时（块内抛异常）记 ERROR 后再 raise；成功时记 INFO。
        """
        start = time.monotonic()
        self.info(f"{_ICON_START} {name}", **fields)
        handle = _StepHandle(self, name)
        try:
            yield handle
        except Exception as e:
            dur = time.monotonic() - start
            self.error(
                f"{_ICON_FAIL} {name}",
                duration=f"{dur:.2f}s",
                error=type(e).__name__,
                reason=str(e)[:200],
            )
            raise
        else:
            dur = time.monotonic() - start
            self.info(f"{_ICON_OK} {name}", duration=f"{dur:.2f}s", **handle._fields)


class _StepHandle:
    """step() 上下文里可附加额外字段，最终输出在结束行。"""

    def __init__(self, log: StepLogger, name: str):
        self._log = log
        self._name = name
        self._fields: dict[str, Any] = {}

    def detail(self, msg: str, **fields: Any) -> None:
        self._log.info(f"  · {msg}", **fields)

    def add_field(self, **fields: Any) -> None:
        self._fields.update(fields)


def get_uploader_logger(platform_name: str) -> StepLogger:
    """获取上传器专用日志。"""
    setup_logging()
    base = logging.getLogger(f"spreado.{platform_name}")
    return StepLogger(base, platform_name)


def get_logger(name: str) -> StepLogger:
    """通用 logger 获取入口（保持向后兼容）。"""
    setup_logging()
    base = logging.getLogger(name)
    return StepLogger(base, name)


setup_logging()
