"""Base uploader contract and publication orchestration."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from playwright.async_api import Locator, Page

from ..conf import COOKIES_DIR
from ..utils.log import StepLogger, get_uploader_logger
from .authentication import AuthenticationConfig, AuthenticationManager
from .browser import BrowserChannel
from .page_actions import PageActions, WaitState


class BaseUploader(ABC):
    """Platform contract plus the public login and upload workflows.

    Authentication is delegated to :class:`AuthenticationManager`; reusable
    locator operations are delegated to :class:`PageActions`. Platform plugins
    only provide URLs, login signals, and the actual upload implementation.
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
        self._uses_managed_cookie_directory = cookie_file_path is None
        self.cookie_file_path = (
            COOKIES_DIR / f"{self.platform_name}_uploader" / "account.json"
            if cookie_file_path is None
            else Path(cookie_file_path)
        )
        self._headless = headless
        self._page_actions = PageActions(self.logger)
        self._authentication = AuthenticationManager(
            AuthenticationConfig(
                platform_name=self.platform_name,
                login_url=self.login_url,
                publish_url=self.publish_url,
                login_selectors=tuple(self._login_selectors),
                authed_selectors=tuple(self._authed_selectors),
                cookie_file_path=self.cookie_file_path,
                secure_cookie_directory=self._uses_managed_cookie_directory,
                browser_channel=self._browser_channel,
            ),
            self.logger,
        )

    @property
    def _browser_channel(self) -> BrowserChannel:
        """System browser product used for this platform."""
        return None

    @property
    def _headless_upload(self) -> bool:
        return self._headless

    @property
    @abstractmethod
    def platform_name(self) -> str: ...

    @property
    @abstractmethod
    def login_url(self) -> str: ...

    @property
    @abstractmethod
    def publish_url(self) -> str: ...

    @property
    @abstractmethod
    def _login_selectors(self) -> List[str]:
        """Elements which indicate that authentication is required."""

    @property
    def _authed_selectors(self) -> List[str]:
        """Elements visible only in an authenticated session."""
        return []

    @abstractmethod
    async def _upload_video(
        self,
        page: Page,
        file_path: str | Path,
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
    ) -> bool: ...

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
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
        auto_login: bool = False,
    ) -> bool:
        """Authenticate and upload in one browser session."""
        try:
            with self.logger.step("upload_video_flow", title=title) as step:
                async with self._authentication.authenticated_page(
                    headless=self._headless_upload,
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

    # Compatibility wrappers for existing platform plugins. New core code uses
    # PageActions directly, while plugins keep their established helper names.

    async def _find_first_element(
        self,
        page: Page,
        selectors: List[str],
        *,
        timeout: int = 5000,
        state: WaitState = "visible",
        callback: Optional[
            Callable[[Locator, Page, Dict[str, Any]], Awaitable[Any]]
        ] = None,
        on_not_found: Optional[Callable[[Page, List[str]], Awaitable[None]]] = None,
    ) -> Optional[Locator]:
        return await self._page_actions.find_first_element(
            page,
            selectors,
            timeout=timeout,
            state=state,
            callback=callback,
            on_not_found=on_not_found,
        )

    async def _wait_until_attached(
        self, page: Page, selectors: List[str], *, timeout: int = 10000
    ) -> bool:
        return await self._page_actions.wait_until_attached(
            page, selectors, timeout=timeout
        )

    async def _click_first_visible(
        self,
        page: Page,
        selectors: List[str],
        *,
        timeout: int = 5000,
        force: bool = False,
    ) -> bool:
        return await self._page_actions.click_first_visible(
            page, selectors, timeout=timeout, force=force
        )

    async def _upload_file_to_first(
        self,
        page: Page,
        selectors: List[str],
        file_path: str | Path,
        *,
        timeout: int = 10000,
    ) -> bool:
        return await self._page_actions.upload_file_to_first(
            page, selectors, file_path, timeout=timeout
        )

    async def _wait_for_condition(
        self,
        check: Callable[[], Awaitable[bool]],
        *,
        timeout: float = 60.0,
        interval: float = 1.0,
        desc: str = "condition",
    ) -> bool:
        return await self._page_actions.wait_for_condition(
            check, timeout=timeout, interval=interval, desc=desc
        )

    async def _click_and_wait_for_url(
        self,
        page: Page,
        button: Locator,
        url_pattern: str | re.Pattern,
        *,
        timeout: int = 30000,
        wait_until: str = "load",
    ) -> bool:
        return await self._page_actions.click_and_wait_for_url(
            page,
            button,
            url_pattern,
            timeout=timeout,
            wait_until=wait_until,
        )
