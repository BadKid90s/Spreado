"""Reusable Playwright page actions for publisher implementations."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from playwright.async_api import Error, Locator, Page

from ..utils.log import StepLogger

WaitState = Literal["visible", "attached", "hidden", "detached"]


class PageActions:
    """Common low-level page operations used by platform publishers."""

    def __init__(self, logger: StepLogger):
        self.logger = logger

    async def find_first_element(
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
        for index, selector in enumerate(selectors):
            try:
                element = page.locator(selector).first
                if await element.count() == 0:
                    self.logger.debug(
                        "选择器未匹配",
                        idx=index + 1,
                        total=len(selectors),
                        sel=selector,
                    )
                    continue
                await element.wait_for(state=state, timeout=timeout)
                self.logger.debug(
                    "选择器命中",
                    idx=index + 1,
                    total=len(selectors),
                    sel=selector,
                )
                if callback:
                    await callback(
                        element,
                        page,
                        {
                            "selector": selector,
                            "index": index,
                            "total": len(selectors),
                            "state": state,
                        },
                    )
                return element
            except Exception as exc:
                self.logger.debug(
                    "选择器失败",
                    idx=index + 1,
                    total=len(selectors),
                    sel=selector,
                    reason=str(exc)[:100],
                )
        self.logger.warning("所有选择器均未命中", count=len(selectors))
        if on_not_found:
            await on_not_found(page, selectors)
        return None

    async def wait_until_attached(
        self, page: Page, selectors: List[str], *, timeout: int = 10000
    ) -> bool:
        per_selector = max(1000, timeout // max(1, len(selectors)))
        for selector in selectors:
            try:
                await page.wait_for_selector(
                    selector, state="attached", timeout=per_selector
                )
                return True
            except Error:
                continue
        return False

    async def click_first_visible(
        self,
        page: Page,
        selectors: List[str],
        *,
        timeout: int = 5000,
        force: bool = False,
    ) -> bool:
        element = await self.find_first_element(
            page, selectors, timeout=timeout, state="visible"
        )
        if element is None:
            return False
        await element.click(force=force, timeout=timeout)
        return True

    async def upload_file_to_first(
        self,
        page: Page,
        selectors: List[str],
        file_path: str | Path,
        *,
        timeout: int = 10000,
    ) -> bool:
        if not await self.wait_until_attached(page, selectors, timeout=timeout):
            self.logger.warning("file input 未找到", selectors=selectors)
            return False
        element = await self.find_first_element(
            page, selectors, timeout=timeout, state="attached"
        )
        if element is None:
            return False
        await element.set_input_files(file_path)
        return True

    async def wait_for_condition(
        self,
        check: Callable[[], Awaitable[bool]],
        *,
        timeout: float = 60.0,
        interval: float = 1.0,
        desc: str = "condition",
    ) -> bool:
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
            except Exception as exc:
                self.logger.debug(
                    "wait_for_condition check 异常",
                    desc=desc,
                    reason=str(exc)[:100],
                )
            await asyncio.sleep(interval)
        self.logger.warning("wait_for_condition 超时", desc=desc, timeout=timeout)
        return False

    async def click_and_wait_for_url(
        self,
        page: Page,
        button: Locator,
        url_pattern: str | re.Pattern,
        *,
        timeout: int = 30000,
        wait_until: str = "load",
    ) -> bool:
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
            current_url = page.url
            if pattern.search(current_url):
                self.logger.info("导航超时但 URL 已匹配", url=current_url)
                return True
            self.logger.error("导航超时且 URL 未匹配", url=current_url)
            return False
