#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
插件加载器

自动扫描内置上传器和外部插件目录，动态发现并注册所有 BasePublisher 子类。
"""

import importlib
import inspect
import logging
from typing import Dict, Type, Optional, List

from .core.base_publisher import BasePublisher
from .conf import PLUGINS_DIR

logger = logging.getLogger("spreado.plugin_loader")

# 内置上传器模块路径 (在 plugins/ 下)
_BUILTIN_MODULES = [
    "spreado.plugins.douyin.uploader",
    "spreado.plugins.xiaohongshu.uploader",
    "spreado.plugins.kuaishou.uploader",
    "spreado.plugins.shipinhao.uploader",
]


class PluginLoader:
    """
    插件加载器

    自动发现并管理所有 BasePublisher 子类。
    扫描来源:
    1. 内置上传器 (plugins/ 下的各平台子目录)
    2. 外部插件目录 (plugins/ 下的子目录)
    """

    def __init__(self):
        self._publishers: Dict[str, Type[BasePublisher]] = {}
        self._loaded = False

    def load(self) -> None:
        """
        扫描并加载所有插件

        加载顺序: 先内置上传器，再外部插件。
        外部插件可覆盖内置上传器 (同 platform_name)。
        """
        if self._loaded:
            return

        # 1. 加载内置上传器
        for module_path in _BUILTIN_MODULES:
            self._load_module(module_path)

        # 2. 加载外部插件目录 (子目录中的 uploader.py)
        if PLUGINS_DIR.exists():
            for sub_dir in sorted(PLUGINS_DIR.iterdir()):
                if not sub_dir.is_dir() or sub_dir.name.startswith("_"):
                    continue
                uploader_file = sub_dir / "uploader.py"
                if uploader_file.exists():
                    module_name = f"spreado.plugins.{sub_dir.name}.uploader"
                    self._load_module(module_name)

        self._loaded = True
        logger.info(
            f"已加载 {len(self._publishers)} 个平台插件: {list(self._publishers.keys())}"
        )

    def _load_module(self, module_path: str) -> None:
        """通过模块路径加载"""
        try:
            module = importlib.import_module(module_path)
            self._discover_publishers(module)
        except Exception as e:
            logger.warning(f"加载模块失败 {module_path}: {e}")

    def _discover_publishers(self, module) -> None:
        """从模块中发现 BasePublisher 子类"""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BasePublisher)
                and obj is not BasePublisher
                and not inspect.isabstract(obj)
            ):
                try:
                    # 实例化获取 platform_name (通过临时实例)
                    # 使用 getattr 避免需要完整构造
                    platform_name = None
                    for cls in reversed(obj.__mro__):
                        if "platform_name" in cls.__dict__:
                            prop = cls.__dict__["platform_name"]
                            if hasattr(prop, "fget"):
                                # 创建一个最小实例来获取 platform_name
                                # 由于 platform_name 是纯数据属性，可以直接从类推断
                                break

                    # 使用临时实例获取 platform_name
                    # platform_name 不需要浏览器，安全获取
                    temp = object.__new__(obj)
                    # 绕过 __init__，直接读取 property
                    platform_name = obj.platform_name.fget(temp)

                    if platform_name:
                        self._publishers[platform_name] = obj
                        logger.debug(f"注册插件: {platform_name} -> {obj.__name__}")
                except Exception as e:
                    logger.warning(f"注册插件 {name} 失败: {e}")

    def get_publisher_class(self, platform_name: str) -> Optional[Type[BasePublisher]]:
        """
        获取指定平台的发布器类

        Args:
            platform_name: 平台名 (如 "douyin")

        Returns:
            发布器类，未找到返回 None
        """
        if not self._loaded:
            self.load()
        return self._publishers.get(platform_name)

    def get_publisher(self, platform_name: str, **kwargs) -> Optional[BasePublisher]:
        """
        创建指定平台的发布器实例

        Args:
            platform_name: 平台名
            **kwargs: 传递给发布器构造函数的参数

        Returns:
            发布器实例，未找到返回 None
        """
        cls = self.get_publisher_class(platform_name)
        if cls is None:
            return None
        return cls(**kwargs)

    def list_publishers(self) -> Dict[str, str]:
        """
        列出所有已注册的发布器

        Returns:
            {platform_name: display_name} 映射
        """
        if not self._loaded:
            self.load()

        result = {}
        for name, cls in self._publishers.items():
            try:
                temp = object.__new__(cls)
                display = cls.display_name.fget(temp)
                result[name] = display
            except Exception:
                result[name] = name
        return result

    def list_publisher_names(self) -> List[str]:
        """
        列出所有已注册的平台名

        Returns:
            平台名列表
        """
        if not self._loaded:
            self.load()
        return list(self._publishers.keys())

    def reload(self) -> None:
        """重新加载所有插件"""
        self._publishers.clear()
        self._loaded = False
        self.load()


# 全局单例
_loader: Optional[PluginLoader] = None


def get_plugin_loader() -> PluginLoader:
    """获取全局插件加载器单例"""
    global _loader
    if _loader is None:
        _loader = PluginLoader()
        _loader.load()
    return _loader
