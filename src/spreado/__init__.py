#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado - 全平台内容发布工具
"""

__version__ = "1.2.0"
__author__ = "wangruiyu"
__email__ = "wry10150@163.com"
__logo__ = r"""
   _____ _____  _____  ______          _____   ____
  / ____|  __ \|  __ \|  ____|   /\   |  __ \ / __ \
 | (___ | |__) | |__) | |__     /  \  | |  | | |  | |
  \___ \|  ___/|  _  /|  __|   / /\ \ | |  | | |  | |
  ____) | |    | | \ \| |____ / ____ \| |__| | |__| |
 |_____/|_|    |_|  \_\______/_/    \_\_____/ \____/
"""

from spreado.publisher.uploader import BaseUploader
from spreado.publisher.base_publisher import BasePublisher
from spreado.plugin_loader import PluginLoader, get_plugin_loader
from spreado.account_manager import AccountManager
from spreado.models.task import Task

__all__ = [
    "BaseUploader",
    "BasePublisher",
    "PluginLoader",
    "get_plugin_loader",
    "AccountManager",
    "Task",
    "__version__",
    "__logo__",
]
