import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from playwright.async_api import Page, Error

from conf import BASE_DIR
from publisher.browser import StealthBrowser


class BaseUploader(ABC):
    """
    上传器基类，定义通用的上传流程和接口
    所有平台上传器必须继承此类并实现抽象方法
    """
    logger: Optional[logging.Logger] = None  # 日志组件
    browser: Optional[StealthBrowser] = None  # 浏览器实例
    cookie_file_path: str | Path = None  # Cookie 保存路径

    def __init__(self, logger: logging.Logger = None, cookie_file_path: str | Path = None):
        """
        初始化上传器

        Args:
            logger: 日志组件
            cookie_file_path: 账户认证文件路径，None则使用默认路径
        """

        # 初始化日志组件
        if logger is None:
            self.logger = logging.getLogger(self.platform_name)

        # 初始化Cookie文件
        if cookie_file_path is None:
            self.cookie_file_path = Path(BASE_DIR) / "cookies" / f"{self.platform_name}_uploader" / "account.json"
        else:
            self.cookie_file_path = Path(cookie_file_path)


    async def start(self):
        # 方式1：工厂方式（推荐用于长生命周期对象）
        self.browser = await StealthBrowser.create(headless=True)
        return self

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
            except Error:
                continue
        return False

    async def login_flow(self) -> bool:
        """
        有头模式登录流程

        Returns:
            登录是否成功
        """
        self.logger.info("[+] 开始有头模式登录流程")

        try:
            async with await self.browser.new_page() as page:
                await page.goto(self.login_url)
                self.logger.info(f"[+] 已打开登录页面，请在浏览器中完成登录操作")

                # 1. 直接等待目标 URL 出现
                await page.wait_for_url(
                    url=lambda url: self._is_target_url(url),
                    timeout=60000,
                    wait_until="commit"
                )
                # 2. 到了这里说明 URL 匹配成功
                self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)

                # 注意：storage_state 通常属于 context，建议直接通过 page 获取 context
                await page.context.storage_state(path=self.cookie_file_path)
                self.logger.info(f"[+] Cookie已保存到: {self.cookie_file_path}")
                self.logger.info("[+] 登录成功，Cookie已保存")
                return True
        except Error | Exception as e:
            self.logger.warning(f"[!] 页面被关闭或发生错误，登录未完成,{e}")
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

            await  self.browser.load_cookies_from_file(self.cookie_file_path)

            async with await self.browser.new_page() as page:
                self.logger.info(f"[+] 打开上传页面，等待是否跳转到登录页")
                await page.goto(self.upload_url, timeout=30000)

                self.logger.info(f"[+] 检查页面是否包含登录页元素")
                login_required = await self._check_login_required(page)
                if login_required:
                    self.logger.warning("[!] Cookie已失效")
                    return False
                else:
                    self.logger.info("[+] Cookie有效")
                    return True
        except Error | Exception as e:
            self.logger.error(f"[!] 验证Cookie时出错: {e}")
            return False

    async def verify_cookie(self, auto_login: bool = False) -> bool:
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

    @abstractmethod
    async def upload_video(
            self,
            file_path: str | Path,
            title: str,
            content: str,
            tags: List[str],
            publish_date: Optional[datetime] = None,
            thumbnail_path: Optional[str | Path] = None,
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

        if not await self.verify_cookie(auto_login=auto_login):
            self.logger.error("[!] 登录失败，无法上传视频")
            return False

        try:
            result = await self.upload_video(
                file_path=file_path,
                title=title,
                content=content,
                tags=tags,
                publish_date=publish_date,
                thumbnail_path=thumbnail_path
            )

            if result:
                await self.browser.storage_state(self.cookie_file_path)
                self.logger.info(f"[+] 视频上传成功: {title}")
            else:
                self.logger.error(f"[!] 视频上传失败: {title}")
            return result

        except Exception as e:
            self.logger.error(f"[!] 上传视频时出错: {e}")
            return False

    async def close(self):
        """
        关闭浏览器实例

        Returns:
            是否成功关闭
        """
        if self.browser:
            await self.browser.close()
            self.browser = None
