"""Base contract and workflow orchestration for platform publishers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page

from ..conf import COOKIES_DIR
from ..models.task import Task
from ..utils.log import StepLogger, get_uploader_logger
from .authentication import (
    AuthenticationConfig,
    AuthenticationManager,
    AuthenticationStateStore,
)
from .page_actions import PageActions


class BasePublisher(ABC):
    """Common lifecycle for authentication and content publication.

    Platform implementations provide identity, one grouped authentication
    configuration, and content-specific publishing methods. Browser state and
    low-level page operations are composed services rather than subclass APIs.
    """

    logger: StepLogger
    cookie_file_path: Path

    def __init__(
        self,
        logger: Optional[StepLogger] = None,
        cookie_file_path: str | Path | None = None,
        headless: bool = True,
    ):
        self.logger = logger or get_uploader_logger(self.platform_name)
        uses_managed_cookie_directory = cookie_file_path is None
        self.cookie_file_path = (
            COOKIES_DIR / f"{self.platform_name}_uploader" / "account.json"
            if cookie_file_path is None
            else Path(cookie_file_path)
        )
        self._headless = headless
        self.actions = PageActions(self.logger)
        state_store = AuthenticationStateStore(
            self.cookie_file_path,
            self.logger,
            secure_directory=uses_managed_cookie_directory,
        )
        self._authentication = AuthenticationManager(
            self.authentication_config,
            self.logger,
            platform_name=self.platform_name,
            state_store=state_store,
        )

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Stable machine-readable platform name."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable platform name."""

    @property
    @abstractmethod
    def authentication_config(self) -> AuthenticationConfig:
        """Authentication URLs, DOM signals, and browser selection."""

    @property
    def login_url(self) -> str:
        return self.authentication_config.login_url

    @property
    def publish_url(self) -> str:
        return self.authentication_config.verification_url

    @property
    def supported_content_types(self) -> List[str]:
        return ["video"]

    @abstractmethod
    async def _upload_video(
        self,
        page: Page,
        file_path: str | Path,
        title: str = "",
        content: str = "",
        tags: Optional[List[str]] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
    ) -> bool:
        """Implement the platform-specific video publication steps."""

    async def login_flow(self) -> bool:
        """Restore an existing session or perform an interactive login."""
        return await self._authentication.login()

    async def verify_cookie_flow(self, auto_login: bool = False) -> bool:
        """Verify authentication, optionally falling back to interactive login."""
        if await self._authentication.verify():
            return True
        return await self._authentication.login() if auto_login else False

    async def upload_video_flow(
        self,
        file_path: str | Path,
        title: str = "",
        content: str = "",
        tags: Optional[List[str]] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
        auto_login: bool = False,
    ) -> bool:
        """Authenticate and upload in one browser session."""
        try:
            with self.logger.step("upload_video_flow", title=title) as step:
                async with self._authentication.authenticated_page(
                    headless=self._headless,
                    auto_login=auto_login,
                ) as page:
                    result = await self._upload_video(
                        page=page,
                        file_path=file_path,
                        title=title,
                        content=content,
                        tags=tags,
                        publish_date=publish_date,
                        thumbnail_path=thumbnail_path,
                    )
                    step.add_field(result="success" if result else "failure")
                    return result
        except Exception as exc:
            self.logger.error("上传流程异常", reason=str(exc)[:200])
            return False

    async def publish_video(self, task: Task) -> bool:
        if not task.media_files:
            self.logger.error("任务缺少素材文件")
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
        raise NotImplementedError(f"平台 {self.display_name} 暂不支持图文发布")

    async def execute(self, task: Task) -> bool:
        if task.type == "video":
            return await self.publish_video(task)
        if task.type == "image_text":
            return await self.publish_image_text(task)
        self.logger.error("不支持的任务类型", content_type=task.type)
        return False
