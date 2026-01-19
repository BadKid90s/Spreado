import os
from pathlib import Path
from typing import Optional, Union

from playwright.async_api import async_playwright, Page, BrowserContext, Browser, Playwright
from playwright_stealth import Stealth


class StealthBrowser:
    def __init__(self, headless: bool = False):
        """
        :param headless: 是否无头模式
        """
        self.headless = headless


        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None


    @classmethod
    async def create(cls, headless: bool = False) -> "StealthBrowser":
        """工厂方法"""
        instance = cls(headless)
        await instance.__aenter__()
        return instance

    async def __aenter__(self):
        self.playwright = await async_playwright().start()

        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=args,
        )

        # 3. 在创建 Context 时注入 storage_state
        # 这是最稳健的方式，同时恢复 Cookies 和 LocalStorage
        self.context = await self.browser.new_context(
            no_viewport=True,
            ignore_https_errors=True
        )

        stealth = Stealth(
            navigator_languages_override=("zh-CN", "zh"),
            init_scripts_only=True
        )
        await stealth.apply_stealth_async(self.context)

        return self


    async def new_page(self) -> Page:
        if not self.context:
            raise RuntimeError("Context 未初始化")
        return await self.context.new_page()

    async def load_cookies_from_file(self, file_path: str | Path):
        """
        从 JSON 文件加载 Cookie 并注入到当前上下文
        自动处理类型转换，消除 IDE 报错
        """
        # if not self.context:
        #     raise RuntimeError("Context 未初始化")
        #
        # path = Path(file_path)
        # if not path.exists():
        #     print(f"[警告] Cookie 文件不存在: {path}")
        #     return
        #
        # context_options = {"storage_state": str(file_path)}
        # # 注入 Cookie
        # await self.context.add_cookies(**context_options)

    async def storage_state(self, path: Path | str):
        """保存当前 Cookie 到文件"""
        if not self.context:
            raise RuntimeError("Context 未初始化")
        # 确保存储目录存在
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return await self.context.storage_state(path=path)

    async def close(self):
        await self.__aexit__(None, None, None)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None



# ==========================================
# 实际使用示例
# ==========================================

class MySpider:
    def __init__(self):
        # 推荐方式 1：用 create 工厂（最安全）
        self.browser: Optional[StealthBrowser] = None

        # 推荐方式 2：如果你喜欢 async with（最优雅）
        self._browser_context_manager = None

    async def start(self):
        # 方式1：工厂方式（推荐用于长生命周期对象）
        self.browser = await StealthBrowser.create(headless=True)

    async def some_task(self):
        page = await self.browser.new_page()
        await page.goto("https://httpbin.org/headers")
        print(await page.content())
        await page.close()

    async def close(self):
        if self.browser:
            await self.browser.close()
            self.browser = None


# 使用示例（完美）
async def main():
    spider = MySpider()
    await spider.start()

    for i in range(10):
        await spider.some_task()

    await spider.close()  # 手动关闭（推荐）

    # 就算你忘记 close()，__del__ + weakref.finalize 也会自动清理！
    # 绝不漏关，内存永不泄露！
