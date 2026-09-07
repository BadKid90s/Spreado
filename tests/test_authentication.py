import asyncio
import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from spreado.core.authentication import (
    AuthResult,
    AuthStatus,
    AuthenticationConfig,
    AuthenticationManager,
    AuthenticationStateStore,
)
from spreado.core.base_publisher import BasePublisher
from spreado.core.browser import StealthBrowser


class _Step:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def add_field(self, **fields):
        pass


class _Logger:
    def step(self, *args, **kwargs):
        return _Step()

    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _Locator:
    def __init__(self, visible=False):
        self.visible = visible

    @property
    def first(self):
        return self

    async def count(self):
        return int(self.visible)

    async def is_visible(self):
        return self.visible


class _Page:
    def __init__(self, visible_selectors=()):
        self.url = "about:blank"
        self.visited = []
        self.closed = False
        self.visible_selectors = set(visible_selectors)

    async def goto(self, url, **kwargs):
        self.url = url
        self.visited.append(url)

    async def wait_for_timeout(self, timeout):
        pass

    async def wait_for_selector(self, *args, **kwargs):
        raise AssertionError("No authenticated selector is configured")

    def locator(self, selector):
        return _Locator(selector in self.visible_selectors)

    async def close(self):
        self.closed = True


class _Browser:
    def __init__(self, state_path):
        self.page = _Page()
        self.state_path = state_path
        self.loaded = False
        self.saved = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        pass

    async def new_page(self):
        return self.page

    async def load_storage_state_from_file(self, path):
        self.loaded = True

    async def storage_state(self, path, *, secure_directory=False):
        self.saved = True
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text('{"cookies": []}', encoding="utf-8")


class _BrowserContext:
    def __init__(self):
        self.cookies = None
        self.scripts = []

    async def add_cookies(self, cookies):
        self.cookies = cookies

    async def add_init_script(self, script):
        self.scripts.append(script)


class _CdpSession:
    def __init__(self):
        self.commands = []

    async def send(self, command):
        self.commands.append(command)


class _CdpBrowser:
    def __init__(self):
        self.session = _CdpSession()

    async def new_browser_cdp_session(self):
        return self.session


class _Process:
    def __init__(self):
        self.wait_calls = 0
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self.wait_calls == 0 else 0

    def wait(self, timeout):
        self.wait_calls += 1
        return 0

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class _Playwright:
    def __init__(self):
        self.stopped = False

    async def stop(self):
        self.stopped = True


class AuthenticationTests(unittest.TestCase):
    def test_publisher_groups_authentication_configuration(self):
        self.assertFalse(hasattr(BasePublisher, "_login_selectors"))
        self.assertFalse(hasattr(BasePublisher, "_authed_selectors"))

    def test_state_store_expiration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "account.json"
            store = AuthenticationStateStore(path, _Logger())

            self.assertTrue(store.is_expired())
            path.write_text(
                json.dumps({"cookies": [{"name": "session", "expires": -1}]}),
                encoding="utf-8",
            )
            self.assertFalse(store.is_expired())
            path.write_text(
                json.dumps({"cookies": [{"name": "old", "expires": 1}]}),
                encoding="utf-8",
            )
            self.assertTrue(store.is_expired())
            path.write_text(
                json.dumps(
                    {
                        "cookies": [],
                        "origins": [
                            {
                                "origin": "https://creator.example",
                                "localStorage": [{"name": "token", "value": "value"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertFalse(store.is_expired())

    def test_login_reuses_authenticated_profile_before_opening_login_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "account.json"
            browser = _Browser(state_path)
            factory_calls = []

            async def factory(**kwargs):
                factory_calls.append(kwargs)
                return browser

            manager = AuthenticationManager(
                AuthenticationConfig(
                    login_url="https://passport.example/login",
                    verification_url="https://creator.example/publish",
                    login_selectors=(),
                    authenticated_selectors=(".authenticated",),
                ),
                _Logger(),
                platform_name="test",
                state_store=AuthenticationStateStore(state_path, _Logger()),
                browser_factory=factory,
            )
            browser.page.visible_selectors.add(".authenticated")

            self.assertTrue(asyncio.run(manager.login()))
            self.assertEqual(browser.page.visited, ["https://creator.example/publish"])
            self.assertTrue(browser.saved)
            self.assertEqual(factory_calls, [{"headless": False, "channel": None}])

    def test_upload_uses_authenticated_page_without_a_second_browser(self):
        class Publisher(BasePublisher):
            authentication_config = AuthenticationConfig(
                login_url="https://passport.example/login",
                verification_url="https://creator.example/publish",
                login_selectors=(),
                authenticated_selectors=(".authenticated",),
            )

            @property
            def platform_name(self):
                return "test"

            @property
            def display_name(self):
                return "Test"

            async def _upload_video(self, page, file_path, **kwargs):
                self.upload_page = page
                return True

        class Authentication:
            def __init__(self):
                self.calls = 0
                self.page = object()

            @asynccontextmanager
            async def authenticated_page(self, **kwargs):
                self.calls += 1
                yield self.page

        publisher = Publisher(logger=_Logger())
        authentication = Authentication()
        publisher._authentication = authentication

        result = asyncio.run(publisher.upload_video_flow("video.mp4"))

        self.assertTrue(result)
        self.assertEqual(authentication.calls, 1)
        self.assertIs(publisher.upload_page, authentication.page)

    def test_authentication_detection_returns_explicit_states(self):
        state_path = Path("unused.json")
        manager = AuthenticationManager(
            AuthenticationConfig(
                login_url="https://passport.example/login",
                verification_url="https://creator.example/publish",
                login_selectors=(".login",),
                authenticated_selectors=(".authenticated",),
                login_url_patterns=(r"passport\.example/login",),
                challenge_selectors=(".challenge",),
            ),
            _Logger(),
            platform_name="test",
            state_store=AuthenticationStateStore(state_path, _Logger()),
        )

        async def detect(page):
            return await manager._detect_auth_state(page)

        authenticated = _Page((".authenticated",))
        authenticated.url = "https://creator.example/publish"
        self.assertEqual(
            asyncio.run(detect(authenticated)).status, AuthStatus.AUTHENTICATED
        )

        login = _Page((".login",))
        login.url = "https://passport.example/login"
        self.assertEqual(asyncio.run(detect(login)).status, AuthStatus.UNAUTHENTICATED)

        login_by_url = _Page()
        login_by_url.url = "https://passport.example/login?next=publish"
        result = asyncio.run(detect(login_by_url))
        self.assertEqual(result.status, AuthStatus.UNAUTHENTICATED)
        self.assertEqual(result.evidence, "login_url")

        challenge = _Page((".challenge", ".login"))
        challenge.url = "https://passport.example/login"
        self.assertEqual(asyncio.run(detect(challenge)).status, AuthStatus.CHALLENGE)

        unknown = _Page()
        unknown.url = "https://creator.example/publish"
        result = asyncio.run(detect(unknown))
        self.assertEqual(result.status, AuthStatus.UNKNOWN)
        self.assertEqual(result.evidence, "no_conclusive_evidence")

    def test_authentication_state_requires_two_stable_observations(self):
        manager = AuthenticationManager(
            AuthenticationConfig(
                login_url="https://passport.example/login",
                verification_url="https://creator.example/publish",
                login_selectors=(".login",),
                authenticated_selectors=(".authenticated",),
            ),
            _Logger(),
            platform_name="test",
            state_store=AuthenticationStateStore(Path("unused.json"), _Logger()),
        )
        page = _Page()
        page.url = "https://creator.example/publish"
        states = iter(
            (
                AuthStatus.AUTHENTICATED,
                AuthStatus.UNKNOWN,
                AuthStatus.AUTHENTICATED,
                AuthStatus.AUTHENTICATED,
            )
        )

        async def detect(_page):
            status = next(states)
            return AuthResult(status, "test", page.url)

        manager._detect_auth_state = detect
        result = asyncio.run(manager._wait_for_auth_state(page, timeout=3.0))
        self.assertEqual(result.status, AuthStatus.AUTHENTICATED)

    def test_browser_restores_cookies_and_local_storage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "account.json"
            state_path.write_text(
                json.dumps(
                    {
                        "cookies": [{"name": "session", "value": "value"}],
                        "origins": [
                            {
                                "origin": "https://creator.example",
                                "localStorage": [{"name": "token", "value": "secret"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            context = _BrowserContext()
            browser = StealthBrowser()
            browser.context = context

            asyncio.run(browser.load_storage_state_from_file(state_path))

            self.assertEqual(context.cookies[0]["name"], "session")
            self.assertIn("https://creator.example", context.scripts[0])
            self.assertIn("token", context.scripts[0])

    def test_owned_browser_waits_for_graceful_shutdown(self):
        browser = StealthBrowser()
        cdp_browser = _CdpBrowser()
        process = _Process()
        playwright = _Playwright()
        browser.browser = cdp_browser
        browser.context = object()
        browser.playwright = playwright
        browser._browser_process = process

        asyncio.run(browser.close())

        self.assertEqual(cdp_browser.session.commands, ["Browser.close"])
        self.assertEqual(process.wait_calls, 1)
        self.assertFalse(process.terminated)
        self.assertFalse(process.killed)
        self.assertTrue(playwright.stopped)


if __name__ == "__main__":
    unittest.main()
