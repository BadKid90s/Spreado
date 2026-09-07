"""Authentication state and browser-session orchestration."""

from __future__ import annotations

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable

from filelock import FileLock, Timeout
from playwright.async_api import Error, Page

from ..account_manager import AccountContext
from ..utils.log import StepLogger
from ..utils.permissions import ensure_private_directory
from .browser import BrowserChannel, StealthBrowser
from .page_actions import PageActions


class AuthenticationError(RuntimeError):
    """Raised when a browser session cannot be authenticated."""


class AuthStatus(str, Enum):
    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated"
    CHALLENGE = "challenge"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AuthResult:
    status: AuthStatus
    evidence: str
    url: str


AuthProbe = Callable[[Page], Awaitable[AuthResult | None]]


@dataclass(frozen=True)
class AuthenticationConfig:
    login_url: str
    verification_url: str
    login_selectors: tuple[str, ...]
    authenticated_selectors: tuple[str, ...] = ()
    login_url_patterns: tuple[str, ...] = ()
    challenge_selectors: tuple[str, ...] = ()
    probe: AuthProbe | None = None
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
        platform_name: str,
        state_store: AuthenticationStateStore,
        account_context: AccountContext | None = None,
        browser_factory: BrowserFactory = StealthBrowser.create,
    ):
        self.config = config
        self.logger = logger
        self.platform_name = platform_name
        self._browser_factory = browser_factory
        self._actions = PageActions(logger)
        self.state = state_store
        self.account_context = account_context

    async def _create_browser(self, *, headless: bool) -> StealthBrowser:
        options = {"headless": headless, "channel": self.config.browser_channel}
        if self.account_context is not None:
            options["profile_dir"] = self.account_context.browser_profile_dir
        return await self._browser_factory(**options)

    @asynccontextmanager
    async def _account_session(self) -> AsyncIterator[None]:
        if self.account_context is None:
            yield
            return

        ensure_private_directory(self.account_context.lock_path.parent)
        lock = FileLock(str(self.account_context.lock_path))
        try:
            await asyncio.to_thread(lock.acquire, timeout=0)
        except Timeout as exc:
            raise AuthenticationError(
                "账号正在被其他任务使用: "
                f"{self.account_context.platform}/{self.account_context.account_id}"
            ) from exc
        try:
            self.account_context.prepare()
            yield
        finally:
            await asyncio.to_thread(lock.release)

    async def login(self) -> bool:
        """Ensure an interactive browser session is authenticated."""
        try:
            async with self._account_session():
                with self.logger.step("login_flow", platform=self.platform_name):
                    async with await self._create_browser(headless=False) as browser:
                        await self.state.restore(browser)
                        page = await browser.new_page()
                        try:
                            result = await self._open_verification_page(page)
                            if result.status is AuthStatus.AUTHENTICATED:
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
            async with self._account_session():
                with self.logger.step("verify_authentication"):
                    async with await self._create_browser(headless=True) as browser:
                        await self.state.restore(browser)
                        page = await browser.new_page()
                        try:
                            result = await self._open_verification_page(page)
                            authenticated = result.status is AuthStatus.AUTHENTICATED
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
        async with self._account_session():
            async with await self._create_browser(headless=browser_headless) as browser:
                await self.state.restore(browser)
                page = await browser.new_page()
                try:
                    result = await self._open_verification_page(page)
                    if result.status is not AuthStatus.AUTHENTICATED:
                        if not auto_login:
                            raise AuthenticationError(
                                "认证状态不可用: "
                                f"{result.status.value} ({result.evidence})"
                            )
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
        result = await self._open_verification_page(page)
        if result.status is not AuthStatus.AUTHENTICATED:
            raise AuthenticationError(
                "登录完成但验证未通过: " f"{result.status.value} ({result.evidence})"
            )

    async def _open_verification_page(self, page: Page) -> AuthResult:
        await page.goto(self.config.verification_url, timeout=30000)
        return await self._wait_for_auth_state(page, timeout=10.0)

    async def _detect_auth_state(self, page: Page) -> AuthResult:
        if await self._matches_any(page, self.config.challenge_selectors):
            return AuthResult(AuthStatus.CHALLENGE, "challenge_dom", page.url)

        if await self._matches_any(page, self.config.login_selectors):
            return AuthResult(AuthStatus.UNAUTHENTICATED, "login_dom", page.url)

        if self._matches_login_url(page.url):
            return AuthResult(AuthStatus.UNAUTHENTICATED, "login_url", page.url)

        if self.config.probe:
            try:
                result = await self.config.probe(page)
                if result is not None:
                    return result
            except Exception as exc:
                self.logger.debug("认证探针异常", reason=str(exc)[:100])

        if await self._matches_any(page, self.config.authenticated_selectors):
            return AuthResult(AuthStatus.AUTHENTICATED, "authenticated_dom", page.url)

        return AuthResult(AuthStatus.UNKNOWN, "no_conclusive_evidence", page.url)

    async def _wait_for_auth_state(self, page: Page, *, timeout: float) -> AuthResult:
        deadline = time.monotonic() + timeout
        previous: AuthResult | None = None
        stable_count = 0
        last = AuthResult(AuthStatus.UNKNOWN, "page_not_ready", page.url)

        while time.monotonic() < deadline:
            last = await self._detect_auth_state(page)
            if last.status is AuthStatus.UNKNOWN:
                previous = None
                stable_count = 0
            elif previous and previous.status is last.status:
                stable_count += 1
            else:
                previous = last
                stable_count = 1

            if stable_count >= 2:
                self._log_auth_result(last)
                return last
            await asyncio.sleep(0.5)

        unknown = AuthResult(AuthStatus.UNKNOWN, last.evidence, page.url)
        self._log_auth_result(unknown)
        return unknown

    def _matches_login_url(self, url: str) -> bool:
        return any(
            re.search(pattern, url) for pattern in self.config.login_url_patterns
        )

    def _log_auth_result(self, result: AuthResult) -> None:
        fields = {
            "status": result.status.value,
            "evidence": result.evidence,
            "url": result.url,
        }
        if result.status is AuthStatus.AUTHENTICATED:
            self.logger.info("认证有效", **fields)
        elif result.status is AuthStatus.UNKNOWN:
            self.logger.warning("认证状态未知", **fields)
        else:
            self.logger.warning("认证未通过", **fields)

    async def _wait_for_login(self, page: Page, *, timeout: float) -> bool:
        await page.wait_for_timeout(3000)
        no_login_since = 0.0

        async def check() -> bool:
            nonlocal no_login_since
            if page.url.startswith(("chrome-error://", "edge://")):
                return False
            result = await self._detect_auth_state(page)
            if result.status is AuthStatus.AUTHENTICATED:
                return True
            if result.status in (AuthStatus.UNAUTHENTICATED, AuthStatus.CHALLENGE):
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
                result = await self._open_verification_page(page)
                return result.status is AuthStatus.AUTHENTICATED
            except Exception:
                no_login_since = 0.0
                return False

        return await self._actions.wait_for_condition(
            check, timeout=timeout, interval=2.0, desc="login"
        )

    async def _matches_any(self, page: Page, selectors: tuple[str, ...]) -> bool:
        for selector in selectors:
            try:
                element = page.locator(selector)
                if await element.count() > 0 and await element.first.is_visible():
                    return True
            except Error:
                continue
        return False
