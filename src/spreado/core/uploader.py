"""上传器基类。

提供：
- 公共流程：login_flow / verify_cookie_flow / upload_video_flow
- 通用工具：_find_first_element / _click_first_visible / _upload_file_to_first
            _wait_for_condition / _wait_until_attached / _click_and_wait_for_url
- 登录检测：cookie 文件过期预检 + positive DOM + negative DOM 兜底
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from playwright.async_api import Error, Locator, Page

from ..conf import COOKIES_DIR
from ..utils.log import StepLogger, get_uploader_logger
from .browser import StealthBrowser

WaitState = Literal["visible", "attached", "hidden", "detached"]


class BaseUploader(ABC):
    """所有平台上传器的基类，定义通用流程与可复用工具方法。"""

    logger: StepLogger
    cookie_file_path: Path

    def __init__(
        self,
        logger: Optional[StepLogger] = None,
        cookie_file_path: str | Path | None = None,
    ):
        self.logger = logger or get_uploader_logger(self.platform_name)
        if cookie_file_path is None:
            self.cookie_file_path = (
                COOKIES_DIR / f"{self.platform_name}_uploader" / "account.json"
            )
        else:
            self.cookie_file_path = Path(cookie_file_path)

    # ---------------------------------------------------------------- 抽象 API

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
        """登录页特征元素（negative 信号；找到 = 未登录）。"""

    @property
    def _authed_selectors(self) -> List[str]:
        """登录后才出现的元素（positive 信号；找到 = 已登录）。

        默认空列表 = 仅依赖 negative 检测。子类应覆盖以提升鲁棒性。
        """
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

    # ----------------------------------------------------------------- 公共流程

    async def login_flow(self) -> bool:
        try:
            with self.logger.step("login_flow", platform=self.platform_name):
                async with await StealthBrowser.create(headless=False) as browser:
                    page = await browser.new_page()
                    await page.goto(self.login_url)
                    self.logger.info("等待用户在浏览器内完成登录…")
                    if not await self._wait_for_login(page, timeout=120.0):
                        raise RuntimeError("登录超时")
                    self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
                    await page.context.storage_state(path=self.cookie_file_path)
                    self.logger.info("cookie 已保存", path=str(self.cookie_file_path))
                    return True
        except Exception as e:
            self.logger.error("登录失败", reason=str(e)[:200])
            return False

    async def _wait_for_login(self, page: Page, *, timeout: float = 120.0) -> bool:
        """等待登录完成：positive DOM 出现，或 negative DOM 消失。"""

        async def check() -> bool:
            if self._authed_selectors:
                for sel in self._authed_selectors:
                    try:
                        el = page.locator(sel)
                        if await el.count() > 0 and await el.first.is_visible():
                            return True
                    except Error:
                        continue
                return False
            return not await self._check_login_required(page)

        return await self._wait_for_condition(
            check, timeout=timeout, interval=1.0, desc="login"
        )

    async def verify_cookie_flow(self, auto_login: bool = False) -> bool:
        if not self.cookie_file_path.exists():
            self.logger.warning("cookie 文件不存在", path=str(self.cookie_file_path))
            return await self.login_flow() if auto_login else False

        if self._is_cookie_file_expired():
            self.logger.warning("cookie 文件已过期（本地预检）")
            return await self.login_flow() if auto_login else False

        if await self._verify_cookie():
            return True
        return await self.login_flow() if auto_login else False

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
        try:
            with self.logger.step("upload_video_flow", title=title) as step:
                if not await self.verify_cookie_flow(auto_login=auto_login):
                    raise RuntimeError("cookie 无效")
                async with await StealthBrowser.create(headless=True) as browser:
                    await browser.load_cookies_from_file(self.cookie_file_path)
                    async with await browser.new_page() as page:
                        await page.goto(self.publish_url)
                        ok = await self._upload_video(
                            page=page,
                            file_path=file_path,
                            title=title,
                            content=content,
                            tags=tags,
                            publish_date=publish_date,
                            thumbnail_path=thumbnail_path,
                        )
                        step.add_field(result="success" if ok else "failure")
                        return ok
        except Exception as e:
            self.logger.error("上传流程异常", reason=str(e)[:200])
            return False

    # -------------------------------------------------------- 登录检测：内部实现

    def _is_cookie_file_expired(self) -> bool:
        """读 storage_state JSON，判断认证 cookie 是否全部过期。

        规则：
        - 解析失败 → True（视为过期，触发重登）
        - 任一 cookie 的 expires <= 0（session）→ 视为有效，返回 False
        - 任一 cookie 的 expires > now → 返回 False
        - 否则全部过期 → True
        """
        try:
            data = json.loads(self.cookie_file_path.read_text(encoding="utf-8"))
        except Exception as e:
            self.logger.debug("cookie 文件解析失败", reason=str(e)[:100])
            return True

        cookies = data.get("cookies") or []
        if not cookies:
            return True
        now = time.time()
        for c in cookies:
            exp = c.get("expires", -1)
            if exp is None or exp <= 0:
                return False  # session cookie，无法判断 → 交给浏览器层
            if exp > now:
                return False
        return True

    async def _check_login_required(self, page: Page) -> bool:
        """negative 检测：登录页特征元素是否可见。"""
        for selector in self._login_selectors:
            try:
                el = page.locator(selector)
                if await el.count() > 0 and await el.first.is_visible():
                    return True
            except Error:
                continue
        return False

    async def _check_authed(self, page: Page, timeout: int = 8000) -> Optional[bool]:
        """positive 检测：等待任一登录后特征元素出现。

        Returns:
            True   登录后元素已出现
            False  超时未出现
            None   未配置 _authed_selectors，跳过
        """
        if not self._authed_selectors:
            return None
        per = max(1000, timeout // max(1, len(self._authed_selectors)))
        for selector in self._authed_selectors:
            try:
                await page.wait_for_selector(selector, state="visible", timeout=per)
                return True
            except Error:
                continue
        return False

    async def _verify_cookie(self) -> bool:
        """启动浏览器加载 cookie，先 positive 后 negative 双重判定。"""
        try:
            with self.logger.step("verify_cookie"):
                async with await StealthBrowser.create(headless=True) as browser:
                    await browser.load_cookies_from_file(self.cookie_file_path)
                    async with await browser.new_page() as page:
                        await page.goto(self.publish_url, timeout=30000)
                        # 1) positive 检测优先
                        authed = await self._check_authed(page)
                        if authed is True:
                            self.logger.info("cookie 有效", method="authed_dom")
                            return True
                        # 2) negative 兜底
                        if await self._check_login_required(page):
                            self.logger.warning("cookie 失效", method="login_dom")
                            return False
                        # 3) 既无 positive 也无 negative：保守判为有效
                        if authed is None:
                            self.logger.info("cookie 有效", method="no_login_dom")
                            return True
                        self.logger.warning("cookie 状态不明，视为失效")
                        return False
        except Exception as e:
            self.logger.error("verify_cookie 异常", reason=str(e)[:200])
            return False

    # ------------------------------------------------------------- 通用工具方法

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
        """按顺序尝试 selectors，返回首个达到 state 的 Locator。"""
        for idx, selector in enumerate(selectors):
            try:
                el = page.locator(selector).first
                if await el.count() == 0:
                    self.logger.debug(
                        "选择器未匹配", idx=idx + 1, total=len(selectors), sel=selector
                    )
                    continue
                await el.wait_for(state=state, timeout=timeout)
                self.logger.debug(
                    "选择器命中", idx=idx + 1, total=len(selectors), sel=selector
                )
                if callback:
                    info = {
                        "selector": selector,
                        "index": idx,
                        "total": len(selectors),
                        "state": state,
                    }
                    await callback(el, page, info)
                return el
            except Exception as e:
                self.logger.debug(
                    "选择器失败",
                    idx=idx + 1,
                    total=len(selectors),
                    sel=selector,
                    reason=str(e)[:100],
                )
                continue
        self.logger.warning("所有选择器均未命中", count=len(selectors))
        if on_not_found:
            await on_not_found(page, selectors)
        return None

    async def _wait_until_attached(
        self,
        page: Page,
        selectors: List[str],
        *,
        timeout: int = 10000,
    ) -> bool:
        """对每个选择器调用 wait_for_selector(state='attached')，命中即返回 True。"""
        per = max(1000, timeout // max(1, len(selectors)))
        for selector in selectors:
            try:
                await page.wait_for_selector(selector, state="attached", timeout=per)
                return True
            except Error:
                continue
        return False

    async def _click_first_visible(
        self,
        page: Page,
        selectors: List[str],
        *,
        timeout: int = 5000,
        force: bool = False,
    ) -> bool:
        """点击首个可见的 selector，未命中返回 False。"""
        el = await self._find_first_element(
            page, selectors, timeout=timeout, state="visible"
        )
        if el is None:
            return False
        await el.click(force=force, timeout=timeout)
        return True

    async def _upload_file_to_first(
        self,
        page: Page,
        selectors: List[str],
        file_path: str | Path,
        *,
        timeout: int = 10000,
    ) -> bool:
        """向首个 attached 的 file input 注入文件。

        显式 wait_for_selector(state='attached') 解决"input 异步挂载"的竞态。
        """
        if not await self._wait_until_attached(page, selectors, timeout=timeout):
            self.logger.warning("file input 未找到", selectors=selectors)
            return False
        el = await self._find_first_element(
            page, selectors, timeout=timeout, state="attached"
        )
        if el is None:
            return False
        await el.set_input_files(file_path)
        return True

    async def _wait_for_condition(
        self,
        check: Callable[[], Awaitable[bool]],
        *,
        timeout: float = 60.0,
        interval: float = 1.0,
        desc: str = "condition",
    ) -> bool:
        """通用轮询：每 interval 秒调用 check()，True 即返回。"""
        deadline = time.monotonic() + timeout
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            try:
                if await check():
                    self.logger.debug(
                        "wait_for_condition 命中", desc=desc, attempt=attempt
                    )
                    return True
            except Exception as e:
                self.logger.debug(
                    "wait_for_condition check 异常",
                    desc=desc,
                    reason=str(e)[:100],
                )
            await asyncio.sleep(interval)
        self.logger.warning("wait_for_condition 超时", desc=desc, timeout=timeout)
        return False

    async def _click_and_wait_for_url(
        self,
        page: Page,
        button: Locator,
        url_pattern: str | re.Pattern,
        *,
        timeout: int = 30000,
        wait_until: str = "load",
    ) -> bool:
        """点击按钮并等待跳转到匹配 url_pattern 的页面，超时则兜底检查当前 URL。"""
        pattern = (
            url_pattern
            if isinstance(url_pattern, re.Pattern)
            else re.compile(url_pattern)
        )
        try:
            async with page.expect_navigation(
                url=pattern, wait_until=wait_until, timeout=timeout
            ):
                await button.click(force=True)
            return True
        except Error:
            current = page.url
            if pattern.search(current):
                self.logger.info("导航超时但 URL 已匹配", url=current)
                return True
            self.logger.error("导航超时且 URL 未匹配", url=current)
            return False
