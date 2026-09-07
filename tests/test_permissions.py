import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

from spreado.account_manager import AccountManager
from spreado.core.browser import StealthBrowser
from spreado.utils.permissions import (
    ensure_private_directory,
    restrict_private_file,
)


def test_ensure_private_directory_uses_owner_only_mode_on_posix() -> None:
    path = Mock(spec=Path)

    with patch("spreado.utils.permissions._is_posix", return_value=True):
        ensure_private_directory(path)

    path.mkdir.assert_called_once_with(mode=0o700, parents=True, exist_ok=True)
    path.chmod.assert_called_once_with(0o700)


def test_restrict_private_file_uses_owner_only_mode_on_posix() -> None:
    path = Mock(spec=Path)

    with patch("spreado.utils.permissions._is_posix", return_value=True):
        restrict_private_file(path)

    path.chmod.assert_called_once_with(0o600)


def test_permission_helpers_do_not_chmod_on_windows() -> None:
    directory = Mock(spec=Path)
    file_path = Mock(spec=Path)

    with patch("spreado.utils.permissions._is_posix", return_value=False):
        ensure_private_directory(directory)
        restrict_private_file(file_path)

    directory.chmod.assert_not_called()
    file_path.chmod.assert_not_called()


def test_browser_storage_state_secures_managed_cookie_path(tmp_path: Path) -> None:
    cookie_path = tmp_path / "cookies" / "account.json"
    context = Mock()

    async def write_storage_state(*, path: Path) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return {"cookies": [], "origins": []}

    context.storage_state = write_storage_state
    browser = StealthBrowser()
    browser.context = context

    with (
        patch("spreado.core.browser.ensure_private_directory") as secure_directory,
        patch("spreado.core.browser.restrict_private_file") as secure_file,
    ):
        state = asyncio.run(browser.storage_state(cookie_path, secure_directory=True))

    assert state == {"cookies": [], "origins": []}
    secure_directory.assert_called_once_with(cookie_path.parent)
    secure_file.assert_called_once_with(cookie_path)


def test_migrate_legacy_cookie_restricts_destination(tmp_path: Path) -> None:
    old_cookie = tmp_path / "douyin_uploader" / "account.json"
    old_cookie.parent.mkdir()
    old_cookie.write_text("{}", encoding="utf-8")
    expected_cookie = tmp_path / "douyin" / "default" / "account.json"

    with (
        patch("spreado.account_manager.ensure_private_directory") as secure_directory,
        patch("spreado.account_manager.restrict_private_file") as secure_file,
    ):
        secure_directory.side_effect = lambda path: path.mkdir(
            parents=True, exist_ok=True
        )
        migrated = AccountManager(tmp_path).migrate_legacy_cookies()

    assert migrated == 1
    assert expected_cookie.exists()
    secure_directory.assert_called_once_with(expected_cookie.parent)
    secure_file.assert_called_once_with(expected_cookie)
