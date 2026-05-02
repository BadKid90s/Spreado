#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
账号管理器

支持多账号隔离存储，每个账号独立保存 Cookie、User-Agent 和浏览器指纹。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from .conf import COOKIES_DIR

logger = logging.getLogger("spreado.account_manager")


class AccountManager:
    """
    账号管理器

    账号存储结构:
        cookies/{platform}/{account_name}/
            account.json    -- Playwright storage_state (cookies + origins)
            meta.json       -- 账号元数据 (UA, fingerprint, 创建时间等)
    """

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or COOKIES_DIR

    def list_platforms(self) -> List[str]:
        """列出所有有账号数据的平台"""
        if not self.base_dir.exists():
            return []
        return [
            d.name
            for d in self.base_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def list_accounts(self, platform: str) -> List[str]:
        """
        列出指定平台的所有账号

        Args:
            platform: 平台名 (如 "douyin")

        Returns:
            账号名列表
        """
        platform_dir = self.base_dir / platform
        if not platform_dir.exists():
            return []
        return [
            d.name
            for d in platform_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def get_account_dir(self, platform: str, account_name: str = "default") -> Path:
        """
        获取账号存储目录

        Args:
            platform: 平台名
            account_name: 账号名，默认 "default"

        Returns:
            账号目录路径
        """
        return self.base_dir / platform / account_name

    def get_cookie_path(self, platform: str, account_name: str = "default") -> Path:
        """
        获取账号 Cookie 文件路径

        Args:
            platform: 平台名
            account_name: 账号名

        Returns:
            cookie 文件路径
        """
        return self.get_account_dir(platform, account_name) / "account.json"

    def get_meta_path(self, platform: str, account_name: str = "default") -> Path:
        """
        获取账号元数据文件路径

        Args:
            platform: 平台名
            account_name: 账号名

        Returns:
            meta 文件路径
        """
        return self.get_account_dir(platform, account_name) / "meta.json"

    def save_account_meta(
        self, platform: str, account_name: str, meta: Dict[str, Any]
    ) -> None:
        """
        保存账号元数据

        Args:
            platform: 平台名
            account_name: 账号名
            meta: 元数据字典 (如 user_agent, fingerprint, created_at)
        """
        meta_path = self.get_meta_path(platform, account_name)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存账号元数据: {platform}/{account_name}")

    def load_account_meta(
        self, platform: str, account_name: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """
        加载账号元数据

        Args:
            platform: 平台名
            account_name: 账号名

        Returns:
            元数据字典，不存在返回 None
        """
        meta_path = self.get_meta_path(platform, account_name)
        if not meta_path.exists():
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"加载账号元数据失败: {platform}/{account_name}: {e}")
            return None

    def account_exists(self, platform: str, account_name: str = "default") -> bool:
        """检查账号是否存在 (cookie 文件是否存在)"""
        return self.get_cookie_path(platform, account_name).exists()

    def delete_account(self, platform: str, account_name: str = "default") -> bool:
        """
        删除账号数据

        Args:
            platform: 平台名
            account_name: 账号名

        Returns:
            是否删除成功
        """
        import shutil

        account_dir = self.get_account_dir(platform, account_name)
        if account_dir.exists():
            shutil.rmtree(account_dir)
            logger.info(f"已删除账号: {platform}/{account_name}")
            return True
        return False

    def migrate_legacy_cookies(self) -> int:
        """
        迁移旧版 Cookie 文件到新的多账号目录结构

        旧结构: cookies/{platform}_uploader/account.json
        新结构: cookies/{platform}/default/account.json

        Returns:
            迁移的账号数量
        """
        migrated = 0
        if not self.base_dir.exists():
            return 0

        for old_dir in self.base_dir.iterdir():
            if not old_dir.is_dir():
                continue
            # 旧目录名格式: {platform}_uploader
            if old_dir.name.endswith("_uploader"):
                platform = old_dir.name.replace("_uploader", "")
                old_cookie = old_dir / "account.json"
                if old_cookie.exists():
                    new_dir = self.get_account_dir(platform, "default")
                    new_dir.mkdir(parents=True, exist_ok=True)
                    new_cookie = new_dir / "account.json"
                    if not new_cookie.exists():
                        old_cookie.rename(new_cookie)
                        migrated += 1
                        logger.info(
                            f"迁移 Cookie: {old_dir.name} -> {platform}/default"
                        )
        return migrated
