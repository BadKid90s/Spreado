from pathlib import Path
from typing import Optional, Dict
from playwright.async_api import Page
import asyncio

from uploader.base_uploader import BaseUploader
from utils.log import get_logger


class AuthManager:
    """
    认证管理器，统一管理各平台的认证流程
    """

    def __init__(self, uploader: BaseUploader):
        """
        初始化认证管理器

        Args:
            uploader: 上传器实例
        """
        self.uploader = uploader
        self.logger = get_logger("AuthManager")

    async def check_account_file_exists(self) -> bool:
        """
        检查账户文件是否存在

        Returns:
            账户文件是否存在
        """
        exists = self.uploader.account_file.exists()
        if exists:
            self.logger.info(f"[+] 账户文件存在: {self.uploader.account_file}")
        else:
            self.logger.warning(f"[!] 账户文件不存在: {self.uploader.account_file}")
        return exists

    async def verify_cookie_validity(self) -> bool:
        """
        验证Cookie有效性

        Returns:
            Cookie是否有效
        """
        return await self.uploader.verify_cookie()

    async def perform_login(self, headless: bool = False) -> bool:
        """
        执行登录流程

        Args:
            headless: 是否使用无头模式

        Returns:
            登录是否成功
        """
        self.logger.info("[+] 开始执行登录流程")

        if headless:
            self.logger.warning("[!] 无头模式登录可能无法完成，建议使用有头模式")

        try:
            if headless:
                result = await self._headless_login_flow()
            else:
                result = await self.uploader.headful_login_flow()

            if result:
                self.logger.info("[+] 登录成功")
            else:
                self.logger.error("[!] 登录失败")

            return result

        except Exception as e:
            self.logger.error(f"[!] 登录流程出错: {e}")
            return False

    async def _headless_login_flow(self) -> bool:
        """
        无头模式登录流程（仅用于特殊场景）

        Returns:
            登录是否成功
        """
        self.logger.warning("[!] 无头模式登录通常需要人工交互，不建议使用")
        return False

    async def ensure_authenticated(self, auto_login: bool = True) -> bool:
        """
        确保已认证

        Args:
            auto_login: 是否自动执行登录流程

        Returns:
            是否已认证
        """
        self.logger.info("[+] 检查认证状态")

        if not await self.check_account_file_exists():
            if auto_login:
                self.logger.info("[+] 账户文件不存在，开始自动登录")
                return await self.perform_login(headless=False)
            else:
                self.logger.error("[!] 账户文件不存在且未启用自动登录")
                return False

        if await self.verify_cookie_validity():
            self.logger.info("[+] Cookie有效，认证成功")
            return True

        if auto_login:
            self.logger.info("[+] Cookie已失效，开始自动登录")
            return await self.perform_login(headless=False)
        else:
            self.logger.error("[!] Cookie已失效且未启用自动登录")
            return False

    async def refresh_cookie(self) -> bool:
        """
        刷新Cookie

        Returns:
            刷新是否成功
        """
        self.logger.info("[+] 开始刷新Cookie")
        return await self.perform_login(headless=False)

    async def get_auth_status(self) -> Dict[str, bool]:
        """
        获取认证状态信息

        Returns:
            认证状态字典
        """
        account_exists = await self.check_account_file_exists()
        cookie_valid = False

        if account_exists:
            cookie_valid = await self.verify_cookie_validity()

        return {
            "account_file_exists": account_exists,
            "cookie_valid": cookie_valid,
            "authenticated": account_exists and cookie_valid
        }
