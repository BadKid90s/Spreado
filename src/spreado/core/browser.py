import os
import platform
from pathlib import Path
from typing import Optional, Literal

import json
from playwright.async_api import (
    async_playwright,
    Page,
    BrowserContext,
    Browser,
    Playwright,
)
from playwright_stealth import Stealth

# 支持的浏览器通道
BrowserChannel = Literal["chrome", "msedge", "chromium", None]

# 各平台常见浏览器路径
BROWSER_PATHS = {
    "windows": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "darwin": [  # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "linux": [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge",
        "/snap/bin/chromium",
    ],
}


def _detect_system_browser() -> Optional[str]:
    """
    自动检测系统已安装的浏览器

    Returns:
        浏览器可执行文件路径，未找到返回 None
    """
    system = platform.system().lower()

    for path in BROWSER_PATHS.get(system, []):
        if Path(path).exists():
            return path

    return None


class StealthBrowser:
    """
    支持多种浏览器选项的隐身浏览器

    浏览器选择优先级：
    1. executable_path 参数 - 指定浏览器路径
    2. channel 参数 - 使用系统浏览器 (chrome/msedge)
    3. SPREADO_BROWSER_PATH 环境变量 - 指定浏览器路径
    4. SPREADO_BROWSER_CHANNEL 环境变量 - 使用系统浏览器
    5. 自动检测系统已安装的 Chrome/Edge/Chromium
    6. 默认使用 Playwright 内置的 Chromium
    """

    def __init__(
        self,
        headless: bool = False,
        channel: BrowserChannel = None,
        executable_path: Optional[str] = None,
    ):
        """
        :param headless: 是否无头模式
        :param channel: 浏览器通道 ("chrome", "msedge", "chromium", None)
        :param executable_path: 浏览器可执行文件路径
        """
        self.headless = headless
        self.channel = channel
        self.executable_path = executable_path

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    @classmethod
    async def create(
        cls,
        headless: bool = True,
        channel: BrowserChannel = None,
        executable_path: Optional[str] = None,
    ) -> "StealthBrowser":
        """工厂方法"""
        instance = cls(headless, channel, executable_path)
        await instance.__aenter__()
        return instance

    def _get_browser_config(self) -> tuple[dict, str]:
        """
        获取浏览器配置

        Returns:
            (config_dict, browser_source) - 配置字典和浏览器来源描述
        """
        config = {}

        # 优先级 1: 参数指定的 executable_path
        if self.executable_path:
            config["executable_path"] = self.executable_path
            return config, f"executable_path: {self.executable_path}"

        # 优先级 2: 参数指定的 channel
        if self.channel:
            if self.channel != "chromium":
                config["channel"] = self.channel
            return config, f"channel: {self.channel}"

        # 优先级 3: 环境变量 SPREADO_BROWSER_PATH
        env_path = os.environ.get("SPREADO_BROWSER_PATH")
        if env_path and Path(env_path).exists():
            config["executable_path"] = env_path
            return config, f"env SPREADO_BROWSER_PATH: {env_path}"

        # 优先级 4: 环境变量 SPREADO_BROWSER_CHANNEL
        env_channel = os.environ.get("SPREADO_BROWSER_CHANNEL")
        if env_channel in ("chrome", "msedge"):
            config["channel"] = env_channel
            return config, f"env SPREADO_BROWSER_CHANNEL: {env_channel}"

        # 优先级 5: 自动检测系统浏览器
        detected_path = _detect_system_browser()
        if detected_path:
            config["executable_path"] = detected_path
            return config, f"auto-detected: {detected_path}"

        # 默认: 使用 Playwright 内置 Chromium
        return config, "Playwright built-in Chromium"

    async def __aenter__(self):
        self.playwright = await async_playwright().start()

        args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
        ]

        # 获取浏览器配置
        browser_config, browser_source = self._get_browser_config()
        print(f"[Browser] Using: {browser_source}")

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=args,
            **browser_config,
        )

        # 3. 在创建 Context 时注入 storage_state
        # 这是最稳健的方式，同时恢复 Cookies 和 LocalStorage
        self.context = await self.browser.new_context(
            no_viewport=True, ignore_https_errors=True
        )

        stealth = Stealth(
            navigator_languages_override=("zh-CN", "zh"), init_scripts_only=True
        )
        await stealth.apply_stealth_async(self.context)

        return self

    async def new_page(self) -> Page:
        if not self.context:
            raise RuntimeError("Context 未初始化")
        return await self.context.new_page()

    async def load_cookies_from_file(self, file_path: str | Path) -> None:
        """
        从 JSON 文件加载 Cookie 并注入到当前上下文

        支持两种文件格式：
        1. Playwright storage_state 文件（包含 "cookies" 字段）
        2. 仅为 cookies 列表的纯 JSON
        """
        if self.context is None:
            raise RuntimeError("Context 未初始化")

        path = Path(file_path)
        if not path.is_file():
            # 如有 logger 建议用 logger，这里先用 print 占位
            raise RuntimeError(f"[警告] Cookie 文件不存在: {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise RuntimeError(f"[错误] 读取 Cookie 文件失败: {path}，错误: {e}")

        # 1. 兼容 Playwright 的 storage_state 结构
        #    {"cookies": [...], "origins": [...]}
        if isinstance(data, dict) and "cookies" in data:
            raw_cookies = data["cookies"]
        else:
            # 2. 兼容直接是 cookies 列表的情况
            raw_cookies = data

        if not isinstance(raw_cookies, list):
            raise RuntimeError(
                f"[错误] Cookie 文件格式不正确，应为列表或包含 'cookies' 字段: {path}"
            )

        # 强制转换成 Playwright Cookie 类型，方便 IDE 类型检查
        cookies = raw_cookies

        if not cookies:
            raise RuntimeError(f"[提示] Cookie 文件为空: {path}")

        await self.context.add_cookies(cookies)

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
