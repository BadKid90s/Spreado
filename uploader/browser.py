import asyncio
from typing import Optional, List
from playwright.async_api import async_playwright, Page, BrowserContext, Browser, Playwright
from playwright_stealth import Stealth


class StealthBrowser:
    """
    异步 Playwright 浏览器封装类
    集成自动资源释放与防检测机制
    """

    def __init__(self, headless: bool = False):
        self.headless = headless

        # 内部实例容器
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def __aenter__(self):
        """
        进入异步上下文：启动 Playwright -> 启动 Browser -> 创建 Context
        """
        self.playwright = await async_playwright().start()

        # 1. 核心启动参数：这是防检测的第一道防线
        # --disable-blink-features=AutomationControlled: 移除 "受到自动测试软件控制" 的特征
        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",  # 隐藏“Chrome正在受到自动软件的控制”提示
            "--disable-dev-shm-usage",
        ]

        # 2. 启动浏览器
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=args,
        )

        # 3. 创建上下文 (Context)
        # 建议在这里预设 User-Agent 和 视口，比在 Page 级别设置更安全
        self.context = await self.browser.new_context(
            no_viewport=True,  # 允许页面自适应
            ignore_https_errors=True
        )
        # 4.  增加防检测机制
        stealth = Stealth(
            navigator_languages_override=("zh-CN", "zh"),
            init_scripts_only=True
        )
        await stealth.apply_stealth_async(self.context)

        return self

    async def new_page(self) -> Page:
        """
        创建一个新的 Page 实例，并注入 stealth 脚本
        """
        if not self.context:
            raise RuntimeError("Context 未初始化，请在 'async with' 块中使用。")

        page = await self.context.new_page()


        return page

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        退出异步上下文：按顺序安全关闭所有资源
        """
        # 无论是否发生异常，都执行清理
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        # 返回 False 表示不吞掉异常，让异常继续向外抛出（方便调试）
        return False


# ==========================================
# 实际使用示例
# ==========================================

async def main():
    print("启动异步浏览器...")

    # 使用 async with 自动管理生命周期
    try:
        async with StealthBrowser(headless=False) as browser:

            # 获取经过伪装的页面
            page = await browser.new_page()

            # --- 开始业务逻辑 ---
            target_url = "https://bot.sannysoft.com/"
            print(f"正在访问: {target_url}")

            await page.goto(target_url, wait_until="networkidle")

            # 验证 1: 检查 navigator.webdriver 属性 (最常见的检测点)
            is_webdriver = await page.evaluate("() => navigator.webdriver")
            print(f"检测点 - navigator.webdriver: {is_webdriver} (预期: False/None)")

            # 验证 2: 截图查看详细检测结果
            screenshot_path = "async_stealth_check.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"检测截图已保存至: {screenshot_path}")

            # 模拟用户操作演示
            await page.wait_for_timeout(2000)

    except Exception as e:
        print(f"运行过程中发生错误: {e}")

    print("程序结束，浏览器资源已自动释放。")


if __name__ == "__main__":
    asyncio.run(main())
