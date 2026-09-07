#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
账号管理器

支持多账号隔离存储，每个账号独立保存 Cookie、User-Agent 和浏览器指纹。
"""

import json
import logging
import os
import platform as system_platform
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .conf import COOKIES_DIR
from .utils.permissions import ensure_private_directory, restrict_private_file

logger = logging.getLogger("spreado.account_manager")

DEFAULT_ACCOUNT_ID = "default"
_ACCOUNT_COMPONENT = re.compile(r"^\w[\w.-]{0,63}$", re.UNICODE)
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _validate_component(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not _ACCOUNT_COMPONENT.fullmatch(value):
        raise ValueError(f"{label} 只能包含字母、数字、下划线、连字符和点，长度为 1-64")
    reserved_stem = value.split(".", 1)[0].upper()
    if (
        value in {".", ".."}
        or value.endswith(".")
        or reserved_stem in _WINDOWS_RESERVED_NAMES
    ):
        raise ValueError(f"无效的 {label}: {value}")
    return value


def _application_data_dir() -> Path:
    system = system_platform.system().lower()
    if system == "windows":
        return (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
            / "Spreado"
        )
    if system == "darwin":
        return Path.home() / "Library/Application Support/Spreado"
    base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_dir / "spreado"


@dataclass(frozen=True)
class AccountContext:
    """All persistent resources owned by one platform account."""

    platform: str
    account_id: str
    storage_state_path: Path
    browser_profile_dir: Path
    metadata_path: Path
    lock_path: Path

    def prepare(self) -> None:
        """Create private account resources and initial metadata on first use."""
        ensure_private_directory(self.lock_path.parent)
        ensure_private_directory(self.browser_profile_dir)
        if self.metadata_path.exists():
            return
        self.metadata_path.write_text(
            json.dumps(
                {
                    "platform": self.platform,
                    "account_id": self.account_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        restrict_private_file(self.metadata_path)


class AccountManager:
    """
    账号管理器

    账号存储结构:
        cookies/{platform}/{account_name}/
            account.json    -- Playwright storage_state (cookies + origins)
            meta.json       -- 账号元数据 (UA, fingerprint, 创建时间等)
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        profile_base_dir: Path | None = None,
    ):
        self.base_dir = base_dir or COOKIES_DIR
        configured_profiles = os.environ.get(
            "SPREADO_BROWSER_PROFILES_DIR"
        ) or os.environ.get("SPREADO_BROWSER_PROFILE_DIR")
        self.profile_base_dir = profile_base_dir or (
            Path(configured_profiles).expanduser()
            if configured_profiles
            else _application_data_dir() / "browser-profiles"
        )

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
        platform_dir = self.base_dir / _validate_component(platform, label="平台名")
        if not platform_dir.exists():
            return []
        return [
            d.name
            for d in platform_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def get_account_dir(
        self, platform: str, account_name: str = DEFAULT_ACCOUNT_ID
    ) -> Path:
        """
        获取账号存储目录

        Args:
            platform: 平台名
            account_name: 账号名，默认 "default"

        Returns:
            账号目录路径
        """
        platform = _validate_component(platform, label="平台名")
        account_name = _validate_component(account_name, label="账号 ID")
        return self.base_dir / platform / account_name

    def get_account_context(
        self,
        platform: str,
        account_id: str = DEFAULT_ACCOUNT_ID,
        *,
        storage_state_path: str | Path | None = None,
    ) -> AccountContext:
        """Resolve isolated storage, profile, metadata, and lock paths."""
        platform = _validate_component(platform, label="平台名")
        account_id = _validate_component(account_id, label="账号 ID")
        account_dir = self.get_account_dir(platform, account_id)

        if storage_state_path is not None:
            state_path = Path(storage_state_path)
        else:
            state_path = account_dir / "account.json"
            legacy_path = self.base_dir / f"{platform}_uploader" / "account.json"
            if (
                account_id == DEFAULT_ACCOUNT_ID
                and not state_path.exists()
                and legacy_path.exists()
            ):
                state_path = legacy_path

        return AccountContext(
            platform=platform,
            account_id=account_id,
            storage_state_path=state_path,
            browser_profile_dir=self.profile_base_dir / platform / account_id,
            metadata_path=account_dir / "meta.json",
            lock_path=account_dir / ".account.lock",
        )

    def get_cookie_path(
        self, platform: str, account_name: str = DEFAULT_ACCOUNT_ID
    ) -> Path:
        """
        获取账号 Cookie 文件路径

        Args:
            platform: 平台名
            account_name: 账号名

        Returns:
            cookie 文件路径
        """
        return self.get_account_dir(platform, account_name) / "account.json"

    def get_meta_path(
        self, platform: str, account_name: str = DEFAULT_ACCOUNT_ID
    ) -> Path:
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
        self, platform: str, account_name: str = DEFAULT_ACCOUNT_ID
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

    def account_exists(
        self, platform: str, account_name: str = DEFAULT_ACCOUNT_ID
    ) -> bool:
        """检查账号是否存在 (cookie 文件是否存在)"""
        return self.get_account_context(
            platform, account_name
        ).storage_state_path.exists()

    def delete_account(
        self, platform: str, account_name: str = DEFAULT_ACCOUNT_ID
    ) -> bool:
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
                platform = old_dir.name.removesuffix("_uploader")
                old_cookie = old_dir / "account.json"
                if old_cookie.exists():
                    new_dir = self.get_account_dir(platform, "default")
                    ensure_private_directory(new_dir)
                    new_cookie = new_dir / "account.json"
                    if not new_cookie.exists():
                        old_cookie.rename(new_cookie)
                        restrict_private_file(new_cookie)
                        migrated += 1
                        logger.info(
                            f"迁移 Cookie: {old_dir.name} -> {platform}/default"
                        )
        return migrated
