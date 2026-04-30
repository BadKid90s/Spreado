#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频上传器 (示例插件)

演示如何通过插件机制扩展 Spreado，支持新的平台。
将此文件放在 plugins/ 目录下即可被自动发现和加载。
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page

from spreado.publisher.base_publisher import BasePublisher


class BilibiliUploader(BasePublisher):
    """
    B站视频上传器

    示例插件，展示如何通过插件机制扩展新平台。
    """

    @property
    def platform_name(self) -> str:
        return "bilibili"

    @property
    def display_name(self) -> str:
        return "B站"

    @property
    def login_url(self) -> str:
        return "https://passport.bilibili.com/login"

    @property
    def login_success_url(self) -> str:
        return "https://member.bilibili.com/platform/upload/video/frame"

    @property
    def upload_url(self) -> str:
        return "https://member.bilibili.com/platform/upload/video/frame"

    @property
    def success_url_pattern(self) -> str:
        return "https://member.bilibili.com/platform/upload/video/frame"

    @property
    def _login_selectors(self) -> List[str]:
        return [
            'text="登录"',
            'text="扫码登录"',
            'text="短信登录"',
            ".login-btn",
        ]

    async def _upload_video(
        self,
        page: Page,
        file_path: str | Path,
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
    ) -> bool:
        """
        B站视频上传实现

        注意: 这是一个示例框架，实际的 B站 上传逻辑需要根据页面结构实现。
        """
        self.logger.info("[+] B站上传器是示例插件，请根据实际页面结构实现上传逻辑")

        # TODO: 实现 B站 上传逻辑
        # 1. 上传视频文件
        # 2. 等待上传完成
        # 3. 填写标题、描述、标签
        # 4. 设置封面
        # 5. 点击发布

        raise NotImplementedError("B站上传器是示例插件，请实现具体的上传逻辑")
