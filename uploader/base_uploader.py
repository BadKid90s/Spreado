from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from playwright.async_api import Page, BrowserContext, Browser, Playwright
import asyncio
import platform
import os
import threading

from conf import BASE_DIR


class BrowserInstanceManager:
    """
    浏览器实例管理器，用于复用浏览器实例
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._browser: Optional[Browser] = None
                    cls._instance._playwright: Optional[Playwright] = None
                    cls._instance._headless: Optional[bool] = None
                    cls._instance._executable_path: Optional[str] = None
                    cls._instance._ref_count = 0
        return cls._instance
    
    async def get_browser(self, headless: bool, executable_path: Optional[str] = None) -> Browser:
        """
        获取浏览器实例，如果不存在则创建
        
        Args:
            headless: 是否使用无头模式
            executable_path: Chrome可执行文件路径
            
        Returns:
            浏览器实例
        """
        from playwright.async_api import async_playwright
        
        if self._browser is None or not self._browser.is_connected():
            self._headless = headless
            self._executable_path = executable_path
            
            self._playwright = await async_playwright().start()
            launch_options = {"headless": headless}
            
            if executable_path:
                launch_options["executable_path"] = executable_path
            
            self._browser = await self._playwright.chromium.launch(**launch_options)
        
        self._ref_count += 1
        return self._browser
    
    async def release_browser(self):
        """
        释放浏览器实例引用
        """
        self._ref_count -= 1
        
        if self._ref_count <= 0 and self._browser is not None:
            try:
                if self._browser.is_connected():
                    await asyncio.wait_for(self._browser.close(), timeout=3)
            except Exception:
                pass
            
            try:
                if self._playwright:
                    await asyncio.wait_for(self._playwright.stop(), timeout=2)
            except Exception:
                pass
            
            self._browser = None
            self._playwright = None
            self._ref_count = 0
    
    async def close_all(self):
        """
        强制关闭所有浏览器实例
        """
        if self._browser is not None:
            try:
                if self._browser.is_connected():
                    await asyncio.wait_for(self._browser.close(), timeout=3)
            except Exception:
                pass
        
        if self._playwright is not None:
            try:
                await asyncio.wait_for(self._playwright.stop(), timeout=2)
            except Exception:
                pass
        
        self._browser = None
        self._playwright = None
        self._ref_count = 0


from utils.base_social_media import set_init_script
from utils.log import get_logger


class BaseUploader(ABC):
    """
    上传器基类，定义通用的上传流程和接口
    所有平台上传器必须继承此类并实现抽象方法
    """

    def __init__(self, account_file: str | Path = None, headless: bool = None):
        """
        初始化上传器

        Args:
            account_file: 账户认证文件路径，None则使用默认路径
            headless: 是否使用无头模式，None则使用配置文件中的默认值
        """
        if account_file is None:
            self.account_file = Path(BASE_DIR) / "cookies" / f"{self.platform_name}_uploader" / "account.json"
        else:
            self.account_file = Path(account_file)
        self.account_file.parent.mkdir(parents=True, exist_ok=True)
        self.headless = headless if headless is not None else True
        self.logger = get_logger(self.platform_name)
        self.local_executable_path = self._get_chrome_path()
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._browser_manager = BrowserInstanceManager()

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        平台名称，用于日志和文件命名

        Returns:
            平台名称字符串
        """
        pass

    @property
    @abstractmethod
    def login_url(self) -> str:
        """
        登录页面URL

        Returns:
            登录页面URL
        """
        pass

    @property
    @abstractmethod
    def upload_url(self) -> str:
        """
        上传页面URL

        Returns:
            上传页面URL
        """
        pass

    @property
    @abstractmethod
    def success_url_pattern(self) -> str:
        """
        上传成功后的URL模式

        Returns:
            URL模式字符串
        """
        pass

    @property
    @abstractmethod
    def login_selectors(self) -> List[str]:
        """
        登录相关的页面元素选择器列表

        Returns:
            选择器列表，用于检测是否需要登录
        """
        pass

    def _get_chrome_path(self) -> Optional[str]:
        """
        自动检测本地Chrome浏览器路径

        Returns:
            Chrome可执行文件路径，未找到则返回None
        """
        system = platform.system()

        if system == "Windows":
            possible_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
            ]
        elif system == "Darwin":
            possible_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            ]
        elif system == "Linux":
            possible_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/opt/google/chrome/chrome"
            ]
        else:
            return None

        for path in possible_paths:
            if os.path.exists(path):
                self.logger.info(f"[+] 自动检测到Chrome浏览器: {path}")
                return path

        self.logger.warning("[!] 未检测到Chrome浏览器，将使用Playwright默认浏览器")
        return None

    async def _init_browser(self, headless: bool = None) -> Browser:
        """
        初始化浏览器实例（使用实例管理器复用）

        Args:
            headless: 是否使用无头模式，None则使用实例配置

        Returns:
            浏览器实例
        """
        if headless is None:
            headless = self.headless

        browser = await self._browser_manager.get_browser(headless, self.local_executable_path)
        self._browser = browser
        return browser

    async def _init_context(self, browser: Browser, use_cookie: bool = True) -> BrowserContext:
        """
        初始化浏览器上下文

        Args:
            browser: 浏览器实例
            use_cookie: 是否使用Cookie文件

        Returns:
            浏览器上下文实例
        """
        context_options = {}
        if use_cookie and self.account_file.exists():
            context_options["storage_state"] = str(self.account_file)

        context = await browser.new_context(**context_options)
        context = await set_init_script(context)
        self._context = context
        return context

    async def _init_page(self, context: BrowserContext) -> Page:
        """
        初始化页面

        Args:
            context: 浏览器上下文实例

        Returns:
            页面实例
        """
        page = await context.new_page()
        self._page = page
        return page

    async def _cleanup_resources(self):
        """
        清理浏览器资源（使用实例管理器）
        """
        try:
            if self._page and not self._page.is_closed():
                try:
                    await asyncio.wait_for(self._page.close(), timeout=2)
                except Exception:
                    pass

            if self._context:
                try:
                    await asyncio.wait_for(self._context.close(), timeout=2)
                except Exception:
                    pass

            if self._browser:
                await self._browser_manager.release_browser()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None

    async def _save_cookie(self):
        """
        保存Cookie到账户文件
        """
        if self._context and self.account_file:
            self.account_file.parent.mkdir(parents=True, exist_ok=True)
            await self._context.storage_state(path=str(self.account_file))
            self.logger.info(f"[+] Cookie已保存到: {self.account_file}")

    async def _check_login_required(self, page: Page) -> bool:
        """
        检查页面是否需要登录

        Args:
            page: 页面实例

        Returns:
            是否需要登录
        """
        for selector in self.login_selectors:
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    if await element.first.is_visible():
                        return True
            except Exception:
                continue
        return False

    async def headful_login_flow(self) -> bool:
        """
        有头模式登录流程

        Returns:
            登录是否成功
        """
        self.logger.info("[+] 开始有头模式登录流程")

        try:
            browser = await self._init_browser(headless=False)
            context = await self._init_context(browser, use_cookie=False)
            page = await self._init_page(context)

            await page.goto(self.login_url)
            self.logger.info(f"[+] 已打开登录页面，请在浏览器中完成登录操作")

            url_changed_event = asyncio.Event()
            page_closed_event = asyncio.Event()

            async def on_framenavigated(frame):
                if frame == page.main_frame:
                    current_url = page.url
                    if self._is_target_url(current_url):
                        url_changed_event.set()

            def on_close():
                page_closed_event.set()

            page.on("framenavigated", lambda frame: asyncio.create_task(on_framenavigated(frame)))
            page.on("close", on_close)

            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(url_changed_event.wait()),
                    asyncio.create_task(page_closed_event.wait())
                ],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if url_changed_event.is_set():
                await self._save_cookie()
                self.logger.info("[+] 登录成功，Cookie已保存")
                await self._cleanup_resources()
                return True
            else:
                self.logger.warning("[!] 页面被关闭，登录未完成")
                await self._cleanup_resources()
                return False

        except Exception as e:
            self.logger.error(f"[!] 登录流程出错: {e}")
            await self._cleanup_resources()
            return False

    def _is_target_url(self, current_url: str) -> bool:
        """
        检查当前URL是否为目标URL

        Args:
            current_url: 当前页面URL

        Returns:
            是否匹配目标URL
        """
        target_url = self.success_url_pattern
        return (
            current_url.startswith(target_url) or
            current_url.split('?')[0] == target_url.split('?')[0] or
            target_url in current_url
        )

    async def verify_cookie(self) -> bool:
        """
        无头模式验证Cookie有效性

        Returns:
            Cookie是否有效
        """
        if not self.account_file.exists():
            self.logger.warning("[!] 账户文件不存在")
            return False

        self.logger.info("[+] 开始验证Cookie有效性")

        try:
            browser = await self._init_browser(headless=True)
            context = await self._init_context(browser, use_cookie=True)
            page = await self._init_page(context)

            await page.goto(self.upload_url)

            try:
                await page.wait_for_url(self.upload_url, timeout=10000)
            except Exception:
                pass

            login_required = await self._check_login_required(page)

            if login_required:
                self.logger.warning("[!] Cookie已失效")
                await self._cleanup_resources()
                return False
            else:
                self.logger.info("[+] Cookie有效")
                await self._cleanup_resources()
                return True

        except Exception as e:
            self.logger.error(f"[!] 验证Cookie时出错: {e}")
            await self._cleanup_resources()
            return False

    async def ensure_login(self, auto_login: bool = False) -> bool:
        """
        确保已登录，如果未登录则执行登录流程

        Args:
            auto_login: 是否自动执行登录流程

        Returns:
            是否已登录
        """
        if not self.account_file.exists():
            self.logger.warning("[!] 账户文件不存在")
            if auto_login:
                return await self.headful_login_flow()
            return False

        if await self.verify_cookie():
            return True

        if auto_login:
            return await self.headful_login_flow()

        return False

    @abstractmethod
    async def upload_video(
        self,
        file_path: str | Path,
        title: str,
        content: str,
        tags: List[str],
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
        **kwargs
    ) -> bool:
        """
        上传视频

        Args:
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径
            **kwargs: 其他平台特定参数

        Returns:
            上传是否成功
        """
        pass

    async def upload(
        self,
        file_path: str | Path,
        title: str,
        content: str,
        tags: List[str],
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
        auto_login: bool = False,
        **kwargs
    ) -> bool:
        """
        主上传流程，包含登录验证和视频上传

        Args:
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径
            auto_login: 是否自动执行登录流程
            **kwargs: 其他平台特定参数

        Returns:
            上传是否成功
        """
        self.logger.info(f"[+] 开始上传视频: {title}")

        if not await self.ensure_login(auto_login=auto_login):
            self.logger.error("[!] 登录失败，无法上传视频")
            return False

        try:
            result = await self.upload_video(
                file_path=file_path,
                title=title,
                content=content,
                tags=tags,
                publish_date=publish_date,
                thumbnail_path=thumbnail_path,
                **kwargs
            )

            if result:
                await self._save_cookie()
                self.logger.success(f"[+] 视频上传成功: {title}")
            else:
                self.logger.error(f"[!] 视频上传失败: {title}")

            return result

        except Exception as e:
            self.logger.error(f"[!] 上传视频时出错: {e}")
            return False
        finally:
            await self._cleanup_resources()
