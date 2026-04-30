#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
插件基类 BasePublisher

继承 BaseUploader，新增面向任务模型的发布接口。
所有平台插件应继承此类。
"""

from abc import abstractmethod
from typing import List

from .uploader import BaseUploader
from ..models.task import Task


class BasePublisher(BaseUploader):
    """
    发布器插件基类

    在 BaseUploader 的基础上，新增:
    - publish_video(task): 基于 Task 模型的视频发布
    - publish_image_text(task): 基于 Task 模型的图文发布
    - display_name: 中文平台名
    - supported_content_types: 支持的内容类型列表
    """

    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        平台中文名称，用于 UI 展示

        Returns:
            如 "抖音", "小红书"
        """
        pass

    @property
    def supported_content_types(self) -> List[str]:
        """
        支持的内容类型列表

        Returns:
            ["video"] 或 ["video", "image_text"]
        """
        return ["video"]

    async def publish_video(self, task: Task) -> bool:
        """
        基于 Task 模型发布视频

        默认实现将 Task 参数映射到 upload_video_flow。
        子类可覆盖此方法实现更复杂的逻辑。

        Args:
            task: 发布任务

        Returns:
            是否发布成功
        """
        if not task.media_files:
            self.logger.error("[!] 任务缺少素材文件")
            return False

        return await self.upload_video_flow(
            file_path=task.media_files[0],
            title=task.title,
            content=task.content,
            tags=task.tags,
            publish_date=task.publish_date,
            thumbnail_path=task.thumbnail_path,
        )

    async def publish_image_text(self, task: Task) -> bool:
        """
        基于 Task 模型发布图文

        默认不支持，子类需覆盖此方法以实现图文发布。

        Args:
            task: 发布任务

        Returns:
            是否发布成功
        """
        raise NotImplementedError(
            f"平台 {self.display_name} 暂不支持图文发布"
        )

    async def execute(self, task: Task) -> bool:
        """
        统一执行入口，根据 task.type 自动分发到 publish_video 或 publish_image_text

        Args:
            task: 发布任务

        Returns:
            是否执行成功
        """
        if task.type == "video":
            return await self.publish_video(task)
        elif task.type == "image_text":
            return await self.publish_image_text(task)
        else:
            self.logger.error(f"[!] 不支持的任务类型: {task.type}")
            return False
