import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Literal, Callable, Awaitable, Any, Dict

from playwright.async_api import Page, Locator, Error

from ..conf import BASE_DIR
from ..publisher.browser import StealthBrowser
from ..utils.log import get_uploader_logger


class BaseUploader(ABC):
    """
    上传器基类，定义通用的上传流程和接口
    所有平台上传器必须继承此类并实现抽象方法
    """

    logger: Optional[logging.Logger] = None  # 日志组件
    browser: Optional[StealthBrowser] = None  # 浏览器实例
    cookie_file_path: str | Path = None  # Cookie 保存路径

    def __init__(
        self, logger: logging.Logger = None, cookie_file_path: str | Path = None
    ):
        """
        初始化上传器

        Args:
            logger: 日志组件
            cookie_file_path: 账户认证文件路径，None则使用默认路径
        """

        # 初始化日志组件
        if logger is None:
            self.logger = get_uploader_logger(self.platform_name)

        # 初始化Cookie文件
        if cookie_file_path is None:
            self.cookie_file_path = (
                Path(BASE_DIR)
                / "cookies"
                / f"{self.platform_name}_uploader"
                / "account.json"
            )
        else:
            self.cookie_file_path = Path(cookie_file_path)

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
    def login_success_url(self) -> str:
        """
        登录成功后跳转的页面URL

        Returns:
            登录成功后跳转的页面URL
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

    async def login_flow(self) -> bool:
        """
        有头模式登录流程

        Returns:
            登录是否成功
        """
        try:
            async with await StealthBrowser.create(headless=False) as browser:
                page = await browser.new_page()
                await page.goto(self.login_url)
                self.logger.info("[+] 已打开登录页面，请在浏览器中完成登录操作")
                # 1. 直接等待目标 URL 出现
                await page.wait_for_url(
                    url=self.login_success_url, timeout=120000, wait_until="commit"
                )
                # 2. 到了这里说明 URL 匹配成功
                self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
                # 注意：storage_state 通常属于 context，建议直接通过 page 获取 context
                await page.context.storage_state(path=self.cookie_file_path)
                self.logger.info(f"[+] Cookie已保存到: {self.cookie_file_path}")
                self.logger.info("[+] 登录成功，Cookie已保存")
                return True
        except (Error, Exception) as e:
            self.logger.error(f"[!] 登录过程中出错: {e}")
            return False

    async def verify_cookie_flow(self, auto_login: bool = False) -> bool:
        """
        确保已登录，如果未登录则执行登录流程

        Args:
            auto_login: 是否自动执行登录流程

        Returns:
            是否已登录
        """
        if not self.cookie_file_path.exists():
            self.logger.warning("[!] 账户文件不存在")
            if auto_login:
                return await self.login_flow()
            return False

        if await self._verify_cookie():
            return True

        if auto_login:
            return await self.login_flow()

        return False

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

        Returns:
            上传是否成功
        """
        self.logger.info(f"[+] 开始上传视频: {title}")

        if not await self.verify_cookie_flow(auto_login=auto_login):
            self.logger.error("[!] 登录失败，无法上传视频")
            return False

        try:

            async with await StealthBrowser.create(headless=True) as browser:
                await browser.load_cookies_from_file(self.cookie_file_path)
                async with await browser.new_page() as page:
                    self.logger.info("[-] 正在打开上传页面...")
                    await page.goto(self.upload_url)

                    result = await self._upload_video(
                        page=page,
                        file_path=file_path,
                        title=title,
                        content=content,
                        tags=tags,
                        publish_date=publish_date,
                        thumbnail_path=thumbnail_path,
                    )
                    if result:
                        self.logger.info(f"[+] 视频上传成功: {title}")
                    else:
                        self.logger.error(f"[!] 视频上传失败: {title}")
                    return result

        except Exception as e:
            self.logger.error(f"[!] 上传视频时出错: {e}")
            return False

    @property
    @abstractmethod
    def _login_selectors(self) -> List[str]:
        """
        登录相关的页面元素选择器列表

        Returns:
            选择器列表，用于检测是否需要登录
        """
        pass

    async def _check_login_required(self, page: Page) -> bool:
        """
        检查页面是否需要登录

        Args:
            page: 页面实例

        Returns:
            是否需要登录
        """
        for selector in self._login_selectors:
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    if await element.first.is_visible():
                        return True
            except Error:
                continue
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
            current_url.startswith(target_url)
            or current_url.split("?")[0] == target_url.split("?")[0]
            or target_url in current_url
        )

    async def _verify_cookie(self) -> bool:
        """
        无头模式验证Cookie有效性

        Returns:
            Cookie是否有效
        """
        try:
            if not self.cookie_file_path.exists():
                self.logger.warning("[!] 账户文件不存在")
                return False

            self.logger.info("[+] 开始验证Cookie有效性")

            async with await StealthBrowser.create(headless=True) as browser:
                await browser.load_cookies_from_file(self.cookie_file_path)
                self.logger.info("[+] 检查页面是否包含登录页元素")
                async with await browser.new_page() as page:
                    self.logger.info("[+] 打开上传页面，等待是否跳转到登录页")
                    await page.goto(self.upload_url, timeout=30000)
                    self.logger.info("[+] 检查页面是否包含登录页元素")
                    login_required = await self._check_login_required(page)
                    if login_required:
                        self.logger.warning("[!] Cookie已失效")
                        return False
                    else:
                        self.logger.info("[+] Cookie有效")
                        return True
        except (Error, Exception) as e:
            self.logger.error(f"[!] 验证Cookie时出错: {e}")
            return False

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
    ) -> bool:
        """
        上传视频

        Args:
            page: 页面
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径

        Returns:
            上传是否成功
        """
        pass

    async def _find_first_element(
        self,
        page: Page,
        selectors: List[str],
        *,
        timeout: int = 5000,
        state: Literal["visible", "attached", "hidden", "detached"] = "visible",
        callback: Optional[
            Callable[[Locator, Page, Dict[str, Any]], Awaitable[Any]]
        ] = None,
        on_not_found: Optional[Callable[[Page, List[str]], Awaitable[None]]] = None,
    ) -> Optional[Locator]:
        """
        通过多个选择器查找第一个可用元素（增强版）

        Args:
            page: Playwright 页面对象
            selectors: 选择器列表
            timeout: 等待超时时间（毫秒）
            state: 元素期望状态
            callback: 找到元素的回调
                     async def callback(element: Locator, page: Page, info: Dict) -> Any
                     info 包含: selector, index, total
            on_not_found: 未找到元素的回调
                         async def callback(page: Page, selectors: List[str]) -> None

        Returns:
            找到的元素或 None
        """
        for idx, selector in enumerate(selectors):
            try:
                element = page.locator(selector).first

                # 检查元素数量
                count = await element.count()
                if count == 0:
                    self.logger.debug(
                        f"[-] 选择器未匹配 [{idx + 1}/{len(selectors)}]: {selector}"
                    )
                    continue

                # 等待元素状态
                await element.wait_for(state=state, timeout=timeout)

                self.logger.info(
                    f"[✓] 找到元素 [{idx + 1}/{len(selectors)}]: {selector}"
                )

                # 构建信息字典
                info = {
                    "selector": selector,
                    "index": idx,
                    "total": len(selectors),
                    "count": count,
                    "state": state,
                }

                # 执行回调
                if callback:
                    result = await callback(element, page, info)
                    # 如果回调返回值，可以在这里处理
                    if result is not None:
                        self.logger.debug(f"回调返回: {result}")

                return element

            except Exception as e:
                self.logger.debug(
                    f"[-] 选择器失败 [{idx + 1}/{len(selectors)}] {selector}: {e}"
                )
                continue

        # 所有选择器都失败
        self.logger.error(f"[✗] 所有 {len(selectors)} 个选择器均未找到元素")

        if on_not_found:
            await on_not_found(page, selectors)

        return None
