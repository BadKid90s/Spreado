import asyncio
import json
from pathlib import Path

import pytest

from spreado.account_manager import AccountManager
from spreado.core.authentication import (
    AuthenticationConfig,
    AuthenticationError,
    AuthenticationManager,
    AuthenticationStateStore,
)
from spreado.core.browser import StealthBrowser
from spreado.models.task import Task


class _Logger:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _authentication_manager(context):
    logger = _Logger()
    return AuthenticationManager(
        AuthenticationConfig(
            login_url="https://passport.example/login",
            verification_url="https://creator.example/publish",
            login_selectors=(".login",),
        ),
        logger,
        platform_name=context.platform,
        state_store=AuthenticationStateStore(context.storage_state_path, logger),
        account_context=context,
    )


def test_account_context_isolates_every_persistent_resource(tmp_path: Path) -> None:
    manager = AccountManager(
        base_dir=tmp_path / "cookies",
        profile_base_dir=tmp_path / "profiles",
    )

    first = manager.get_account_context("kuaishou", "store-a")
    second = manager.get_account_context("kuaishou", "store-b")

    assert first.storage_state_path != second.storage_state_path
    assert first.browser_profile_dir != second.browser_profile_dir
    assert first.metadata_path != second.metadata_path
    assert first.lock_path != second.lock_path
    assert first.storage_state_path == (
        tmp_path / "cookies" / "kuaishou" / "store-a" / "account.json"
    )
    assert first.browser_profile_dir == (tmp_path / "profiles" / "kuaishou" / "store-a")


@pytest.mark.parametrize(
    "platform,account_id",
    [
        ("../kuaishou", "default"),
        ("kuaishou", "../other"),
        ("kuaishou", "account/name"),
        ("kuaishou", "C:account"),
        ("kuaishou", "CON.txt"),
        ("kuaishou", "account."),
    ],
)
def test_account_context_rejects_path_traversal(
    tmp_path: Path, platform: str, account_id: str
) -> None:
    manager = AccountManager(tmp_path / "cookies", tmp_path / "profiles")

    with pytest.raises(ValueError):
        manager.get_account_context(platform, account_id)


def test_default_account_resolves_legacy_cookie_without_moving_it(
    tmp_path: Path,
) -> None:
    cookies_dir = tmp_path / "cookies"
    legacy = cookies_dir / "kuaishou_uploader" / "account.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text('{"cookies": []}', encoding="utf-8")
    manager = AccountManager(cookies_dir, tmp_path / "profiles")

    context = manager.get_account_context("kuaishou")

    assert context.storage_state_path == legacy
    assert legacy.exists()


def test_account_context_prepares_metadata_and_profile(tmp_path: Path) -> None:
    context = AccountManager(
        tmp_path / "cookies", tmp_path / "profiles"
    ).get_account_context("douyin", "brand")

    context.prepare()

    assert context.browser_profile_dir.is_dir()
    metadata = json.loads(context.metadata_path.read_text(encoding="utf-8"))
    assert metadata["platform"] == "douyin"
    assert metadata["account_id"] == "brand"


def test_same_account_cannot_open_two_sessions(tmp_path: Path) -> None:
    context = AccountManager(
        tmp_path / "cookies", tmp_path / "profiles"
    ).get_account_context("douyin", "brand")
    first = _authentication_manager(context)
    second = _authentication_manager(context)

    async def exercise_lock():
        async with first._account_session():
            with pytest.raises(AuthenticationError, match="账号正在被其他任务使用"):
                async with second._account_session():
                    pass

    asyncio.run(exercise_lock())


def test_different_accounts_can_hold_sessions_together(tmp_path: Path) -> None:
    accounts = AccountManager(tmp_path / "cookies", tmp_path / "profiles")
    first = _authentication_manager(accounts.get_account_context("douyin", "one"))
    second = _authentication_manager(accounts.get_account_context("douyin", "two"))

    async def exercise_locks():
        async with first._account_session():
            async with second._account_session():
                return True

    assert asyncio.run(exercise_locks())


def test_browser_accepts_an_explicit_account_profile(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / "douyin" / "brand"

    browser = StealthBrowser(profile_dir=profile_dir)

    assert browser._profile_dir == profile_dir


def test_authentication_passes_account_profile_to_browser(tmp_path: Path) -> None:
    context = AccountManager(
        tmp_path / "cookies", tmp_path / "profiles"
    ).get_account_context("douyin", "brand")
    manager = _authentication_manager(context)
    calls = []

    async def browser_factory(**options):
        calls.append(options)
        return object()

    manager._browser_factory = browser_factory

    asyncio.run(manager._create_browser(headless=True))

    assert calls == [
        {
            "headless": True,
            "channel": None,
            "profile_dir": context.browser_profile_dir,
        }
    ]


def test_task_serializes_account_id() -> None:
    task = Task(platform="douyin", account_id="brand")

    restored = Task.from_json(task.to_json())

    assert restored.account_id == "brand"
