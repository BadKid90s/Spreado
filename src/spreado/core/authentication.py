"""Authentication state and browser-session orchestration."""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Sequence
from urllib.parse import urlparse

from playwright.async_api import Error, Page

from ..utils.log import StepLogger
from .browser import BrowserChannel, StealthBrowser
from .page_actions import PageActions


class AuthenticationError(RuntimeError):
    """Raised when a browser session cannot be authenticated."""


@dataclass(frozen=True)
class AuthenticationConfig:
    platform_name: str
    login_url: str
    publish_url: str
    login_selectors: Sequence[str]
    authed_selectors: Sequence[str]
    cookie_file_path: Path
    secure_cookie_directory: bool = False
    browser_channel: BrowserChannel = None


class AuthenticationStateStore:
    """Portable backup of browser authentication state.

    The persistent browser profile is the primary state. This file is restored
    into every new context so session cookies also survive browser restarts.
    """

    def __init__(
        self,
        path: Path,
        logger: StepLogger,
        *,
        secure_directory: bool = False,
    ):
        self.path = path
        self.logger = logger
        self.secure_directory = secure_directory

    def is_expired(self) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.debug("认证状态文件解析失败", reason=str(exc)[:100])
            return True

        cookies = data.get("cookies") if isinstance(data, dict) else data
        origins = data.get("origins", []) if isinstance(data, dict) else []
        if not isinstance(cookies, list):
            return True

        has_local_storage = any(
            isinstance(origin, dict) and origin.get("localStorage")
            for origin in origins
        )
        if not cookies:
            return not has_local_storage

        now = time.time()
        for cookie in cookies:
            expires = cookie.get("expires", -1)
            if expires is None or expires <= 0 or expires > now:
                return False
        return not has_local_storage

    async def restore(self, browser: StealthBrowser) -> bool:
        if not self.path.is_file():
            self.logger.debug("认证状态文件不存在", path=str(self.path))
            return False
        if self.is_expired():
            self.logger.warning("认证状态文件已过期", path=str(self.path))
            return False
        await browser.load_storage_state_from_file(self.path)
        self.logger.debug("认证状态已恢复", path=str(self.path))
        return True

    async def save(self, browser: StealthBrowser) -> None:
        await browser.storage_state(self.path, secure_directory=self.secure_directory)
        self.logger.info("认证状态已保存", path=str(self.path))


BrowserFactory = Callable[..., Awaitable[StealthBrowser]]


class AuthenticationManager:
    """Own authentication checks and authenticated browser sessions."""

    def __init__(
        self,
        config: AuthenticationConfig,
        logger: StepLogger,
        *,
        browser_factory: BrowserFactory = StealthBrowser.create,
    ):
        self.config = config
        self.logger = logger
        self._browser_factory = browser_factory
        self._actions = PageActions(logger)
        self.state = AuthenticationStateStore(
            config.cookie_file_path,
            logger,
            secure_directory=config.secure_cookie_directory,
        )

    async def login(self) -> bool:
        """Ensure an interactive browser session is authenticated."""
        try:
            with self.logger.step("login_flow", platform=self.config.platform_name):
                async with await self._browser_factory(
                    headless=False, channel=self.config.browser_channel
                ) as browser:
                    await self.state.restore(browser)
                    page = await browser.new_page()
                    try:
                        if await self._open_publish_page(page):
                            self.logger.info("已有登录状态可用")
                        else:
                            await self._interactive_login(page)
                        await self.state.save(browser)
                        return True
                    finally:
                        await page.close()
        except Exception as exc:
            self.logger.error("登录失败", reason=str(exc)[:200])
            return False

    async def verify(self) -> bool:
        """Verify restored state and the persistent browser profile."""
        try:
            with self.logger.step("verify_authentication"):
                async with await self._browser_factory(
                    headless=True, channel=self.config.browser_channel
                ) as browser:
                    await self.state.restore(browser)
                    page = await browser.new_page()
                    try:
                        authenticated = await self._open_publish_page(page)
                        if authenticated:
                            await self.state.save(browser)
                        return authenticated
                    finally:
                        await page.close()
        except Exception as exc:
            self.logger.error("认证验证异常", reason=str(exc)[:200])
            return False

    @asynccontextmanager
    async def authenticated_page(
        self, *, headless: bool, auto_login: bool = False
    ) -> AsyncIterator[Page]:
        """Yield one page whose browser session has already been authenticated.

        Restore, validation, optional login, and publishing all happen in the
        same browser process. This keeps device fingerprints and session state
        consistent for platforms such as Kuaishou.
        """
        browser_headless = False if auto_login else headless
        async with await self._browser_factory(
            headless=browser_headless, channel=self.config.browser_channel
        ) as browser:
            await self.state.restore(browser)
            page = await browser.new_page()
            try:
                if not await self._open_publish_page(page):
                    if not auto_login:
                        raise AuthenticationError("认证状态无效")
                    await self._interactive_login(page)
                await self.state.save(browser)
                yield page
            finally:
                await page.close()

    async def _interactive_login(self, page: Page) -> None:
        await page.goto(self.config.login_url, timeout=30000)
        self.logger.info("等待用户在浏览器内完成登录…")
        if not await self._wait_for_login(page, timeout=120.0):
            raise AuthenticationError("登录超时")
        if not await self._open_publish_page(page):
            raise AuthenticationError(
                f"登录完成，但发布页 {self.config.publish_url} 仍要求登录"
            )

    async def _open_publish_page(self, page: Page) -> bool:
        await page.goto(self.config.publish_url, timeout=30000)
        await page.wait_for_timeout(3000)
        return await self._is_authenticated(page, wait_for_positive=True)

    async def _is_authenticated(
        self, page: Page, *, wait_for_positive: bool = False
    ) -> bool:
        authed = await self._check_authed(
            page, timeout=8000 if wait_for_positive else 0
        )
        if authed:
            self.logger.info("认证有效", method="authed_dom")
            return True
        if await self._check_login_required(page):
            self.logger.warning("认证无效", method="login_dom")
            return False

        publish_domain = urlparse(self.config.publish_url).netloc
        current_domain = urlparse(page.url).netloc
        if publish_domain and current_domain == publish_domain:
            self.logger.info("认证有效", method="same_domain", url=page.url)
            return True
        if not self.config.authed_selectors:
            self.logger.info("认证有效", method="no_login_dom")
            return True
        self.logger.warning("认证状态不明，视为无效", url=page.url)
        return False

    async def _wait_for_login(self, page: Page, *, timeout: float) -> bool:
        await page.wait_for_timeout(3000)
        no_login_since = 0.0

        async def check() -> bool:
            nonlocal no_login_since
            if page.url.startswith(("chrome-error://", "edge://")):
                return False
            if await self._check_authed(page, timeout=0):
                return True
            if await self._check_login_required(page):
                no_login_since = 0.0
                return False

            now = time.monotonic()
            if no_login_since == 0.0:
                no_login_since = now
                self.logger.debug("登录表单消失，进入防抖期...")
                return False
            if now - no_login_since < 5.0:
                return False

            try:
                return await self._open_publish_page(page)
            except Exception:
                no_login_since = 0.0
                return False

        return await self._actions.wait_for_condition(
            check, timeout=timeout, interval=2.0, desc="login"
        )

    async def _check_login_required(self, page: Page) -> bool:
        for selector in self.config.login_selectors:
            try:
                element = page.locator(selector)
                if await element.count() > 0 and await element.first.is_visible():
                    return True
            except Error:
                continue
        return False

    async def _check_authed(self, page: Page, *, timeout: int) -> bool:
        if not self.config.authed_selectors:
            return False
        per_selector = max(1000, timeout // max(1, len(self.config.authed_selectors)))
        for selector in self.config.authed_selectors:
            try:
                if timeout:
                    await page.wait_for_selector(
                        selector, state="visible", timeout=per_selector
                    )
                    return True
                element = page.locator(selector)
                if await element.count() > 0 and await element.first.is_visible():
                    return True
            except Error:
                continue
        return False
