import asyncio
import json
import os
import platform
import subprocess
import urllib.request
from pathlib import Path
from typing import Literal, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright_stealth import Stealth

from ..utils.permissions import ensure_private_directory, restrict_private_file

BrowserChannel = Literal["chrome", "msedge", "chromium", None]


def _browser_candidates() -> dict[str, list[Path]]:
    """Return installed-browser candidates grouped by product."""
    system = platform.system().lower()
    if system == "windows":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        program_files_x86 = Path(
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        )
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        return {
            "chrome": [
                program_files / "Google/Chrome/Application/chrome.exe",
                program_files_x86 / "Google/Chrome/Application/chrome.exe",
                local_app_data / "Google/Chrome/Application/chrome.exe",
            ],
            "msedge": [
                program_files / "Microsoft/Edge/Application/msedge.exe",
                program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
                local_app_data / "Microsoft/Edge/Application/msedge.exe",
            ],
            "chromium": [
                local_app_data / "Chromium/Application/chrome.exe",
                program_files / "BraveSoftware/Brave-Browser/Application/brave.exe",
                local_app_data / "BraveSoftware/Brave-Browser/Application/brave.exe",
            ],
        }
    if system == "darwin":
        return {
            "chrome": [
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            ],
            "msedge": [
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
            ],
            "chromium": [
                Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
                Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
            ],
        }
    return {
        "chrome": [
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
        ],
        "msedge": [
            Path("/usr/bin/microsoft-edge"),
            Path("/usr/bin/microsoft-edge-stable"),
        ],
        "chromium": [
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/snap/bin/chromium"),
            Path("/usr/bin/brave-browser"),
        ],
    }


def _resolve_system_browser(
    executable_path: Optional[str] = None, channel: BrowserChannel = None
) -> Path:
    """Resolve a local Chromium browser without a bundled fallback."""
    configured_path = executable_path or os.environ.get("SPREADO_BROWSER_PATH")
    if configured_path:
        path = Path(configured_path).expanduser()
        if path.is_file():
            return path
        raise RuntimeError(f"配置的系统浏览器不存在: {path}")

    selected_channel = channel or os.environ.get("SPREADO_BROWSER_CHANNEL")
    candidates = _browser_candidates()
    if selected_channel and selected_channel not in candidates:
        raise RuntimeError("SPREADO_BROWSER_CHANNEL 仅支持 chrome、msedge 或 chromium")

    channels = [selected_channel] if selected_channel else list(candidates)
    for browser_channel in channels:
        for path in candidates[browser_channel]:
            if path.is_file():
                return path

    raise RuntimeError(
        "未找到支持 CDP 的系统浏览器。请安装 Chrome、Edge、Chromium 或 Brave，"
        "或通过 SPREADO_BROWSER_PATH 指定浏览器可执行文件。"
    )


def _default_profile_dir() -> Path:
    """Return Spreado's persistent, isolated system-browser profile."""
    configured_path = os.environ.get("SPREADO_BROWSER_PROFILE_DIR")
    if configured_path:
        return Path(configured_path).expanduser()

    system = platform.system().lower()
    if system == "windows":
        base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return base_dir / "Spreado/browser-profile"
    if system == "darwin":
        return Path.home() / "Library/Application Support/Spreado/browser-profile"
    base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_dir / "spreado/browser-profile"


def _build_cdp_command(
    executable_path: Path, profile_dir: Path, headless: bool
) -> list[str]:
    command = [
        str(executable_path),
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=0",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
    ]
    if headless:
        command.append("--headless=new")
    command.append("about:blank")
    return command


class StealthBrowser:
    """Control a locally installed browser through Chrome DevTools Protocol.

    Playwright remains only as the adapter used by the existing Page/Locator
    implementations. It never launches or falls back to bundled Chromium.
    """

    def __init__(
        self,
        headless: bool = False,
        channel: BrowserChannel = None,
        executable_path: Optional[str] = None,
        profile_dir: str | Path | None = None,
    ):
        self.headless = headless
        self.channel = channel
        self.executable_path = executable_path

        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._browser_process: Optional[subprocess.Popen] = None
        self._profile_dir = (
            Path(profile_dir).expanduser()
            if profile_dir is not None
            else _default_profile_dir()
        )
        self._cdp_endpoint: Optional[str] = None

    @classmethod
    async def create(
        cls,
        headless: bool = True,
        channel: BrowserChannel = None,
        executable_path: Optional[str] = None,
        profile_dir: str | Path | None = None,
    ) -> "StealthBrowser":
        instance = cls(headless, channel, executable_path, profile_dir)
        await instance.__aenter__()
        return instance

    async def _wait_for_cdp_endpoint(self, timeout: float = 15.0) -> str:
        if not self._browser_process:
            raise RuntimeError("系统浏览器进程尚未启动")

        active_port_file = self._profile_dir / "DevToolsActivePort"
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if (
                self._browser_process.poll() is not None
                and self._browser_process.returncode != 0
            ):
                raise RuntimeError(
                    f"系统浏览器启动失败，退出码: {self._browser_process.returncode}"
                )
            try:
                port = int(active_port_file.read_text(encoding="utf-8").splitlines()[0])
                return f"http://127.0.0.1:{port}"
            except (FileNotFoundError, IndexError, ValueError, OSError):
                await asyncio.sleep(0.1)

        raise RuntimeError("等待系统浏览器 CDP 端点超时")

    def _read_cdp_endpoint(self) -> Optional[str]:
        try:
            port = int(
                (self._profile_dir / "DevToolsActivePort")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
        except (FileNotFoundError, IndexError, ValueError, OSError):
            return None
        return f"http://127.0.0.1:{port}"

    async def _cdp_endpoint_is_available(self, endpoint: str) -> bool:
        def probe() -> bool:
            try:
                with urllib.request.urlopen(
                    f"{endpoint}/json/version", timeout=0.5
                ) as response:
                    return response.status == 200
            except OSError:
                return False

        return await asyncio.to_thread(probe)

    async def __aenter__(self):
        if self.context is not None:
            return self

        browser_path = _resolve_system_browser(self.executable_path, self.channel)
        ensure_private_directory(self._profile_dir)
        active_port_file = self._profile_dir / "DevToolsActivePort"
        print(f"[Browser] CDP system browser: {browser_path}")
        print(f"[Browser] Spreado profile: {self._profile_dir}")
        try:
            endpoint = self._read_cdp_endpoint()
            if not endpoint or not await self._cdp_endpoint_is_available(endpoint):
                active_port_file.unlink(missing_ok=True)
                command = _build_cdp_command(
                    browser_path, self._profile_dir, self.headless
                )
                process_options = {
                    "stdin": subprocess.DEVNULL,
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                }
                if platform.system().lower() == "windows":
                    process_options["creationflags"] = getattr(
                        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                    )
                else:
                    process_options["start_new_session"] = True
                self._browser_process = subprocess.Popen(command, **process_options)
                endpoint = await self._wait_for_cdp_endpoint()

            self._cdp_endpoint = endpoint
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(endpoint)
            if not self.browser.contexts:
                raise RuntimeError("CDP 连接成功，但系统浏览器没有可用上下文")
            self.context = self.browser.contexts[0]

            await self.context.add_init_script("""
                Element.prototype._attachShadow = Element.prototype.attachShadow;
                Element.prototype.attachShadow = function(init) {
                    if (init && init.mode === 'closed') {
                        init = Object.assign({}, init, { mode: 'open' });
                    }
                    return this._attachShadow(init);
                };
            """)
            stealth = Stealth(
                navigator_languages_override=("zh-CN", "zh"),
                init_scripts_only=True,
            )
            await stealth.apply_stealth_async(self.context)
        except Exception:
            await self.__aexit__(None, None, None)
            raise
        return self

    async def new_page(self) -> Page:
        if not self.context:
            raise RuntimeError("Context 未初始化")
        return await self.context.new_page()

    async def load_storage_state_from_file(self, file_path: str | Path) -> None:
        """Restore cookies and local storage from a Playwright state file."""
        if self.context is None:
            raise RuntimeError("Context 未初始化")

        path = Path(file_path)
        if not path.is_file():
            raise RuntimeError(f"[警告] Cookie 文件不存在: {path}")

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as exc:
            raise RuntimeError(
                f"[错误] 读取 Cookie 文件失败: {path}，错误: {exc}"
            ) from exc

        if isinstance(data, dict):
            raw_cookies = data.get("cookies", [])
            raw_origins = data.get("origins", [])
        else:
            raw_cookies = data
            raw_origins = []
        if not isinstance(raw_cookies, list):
            raise RuntimeError(
                f"[错误] Cookie 文件格式不正确，应为列表或包含 'cookies' 字段: {path}"
            )
        if not isinstance(raw_origins, list):
            raise RuntimeError(f"[错误] origins 字段格式不正确: {path}")
        if not raw_cookies and not raw_origins:
            raise RuntimeError(f"[提示] 认证状态文件为空: {path}")
        if raw_cookies:
            await self.context.add_cookies(raw_cookies)

        local_storage = {
            origin["origin"]: origin.get("localStorage", [])
            for origin in raw_origins
            if isinstance(origin, dict) and origin.get("origin")
        }
        if local_storage:
            serialized_state = json.dumps(local_storage, ensure_ascii=True)
            await self.context.add_init_script(f"""
                (() => {{
                    const state = {serialized_state};
                    for (const item of state[window.location.origin] || []) {{
                        window.localStorage.setItem(item.name, item.value);
                    }}
                }})();
                """)

    async def load_cookies_from_file(self, file_path: str | Path) -> None:
        """Compatibility alias for restoring a complete storage-state file."""
        await self.load_storage_state_from_file(file_path)

    async def storage_state(self, path: Path | str, *, secure_directory: bool = False):
        """Save cookies and restrict their POSIX filesystem permissions."""
        if not self.context:
            raise RuntimeError("Context 未初始化")
        target = Path(path)
        if secure_directory:
            ensure_private_directory(target.parent)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)

        state = await self.context.storage_state(path=target)
        restrict_private_file(target)
        return state

    async def close(self):
        await self.__aexit__(None, None, None)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        owned_process = self._browser_process
        if self.browser and owned_process:
            try:
                cdp_session = await self.browser.new_browser_cdp_session()
                await cdp_session.send("Browser.close")
            except Exception:
                pass
        if owned_process and owned_process.poll() is None:
            try:
                await asyncio.to_thread(owned_process.wait, timeout=5)
            except subprocess.TimeoutExpired:
                owned_process.terminate()
                try:
                    await asyncio.to_thread(owned_process.wait, timeout=5)
                except subprocess.TimeoutExpired:
                    owned_process.kill()
                    await asyncio.to_thread(owned_process.wait, timeout=5)

        # Stopping Playwright disconnects from an externally owned CDP browser.
        # Do not send Browser.close when this instance only attached to it.
        self.browser = None
        self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        self._browser_process = None
        self._cdp_endpoint = None
