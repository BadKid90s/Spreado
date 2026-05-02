"""平台元素健康度检查。

为每个已注册插件验证：
1. login_url 是否可达
2. _login_selectors 是否能在登录页找到（反向 DOM 信号）
3. 若存在 cookie 文件：publish_url 是否可达 + _authed_selectors 是否可见

**严格只读**：从不点击发布、上传或任何写操作。

输出 reports/selector-check-latest.md（覆写）和带时间戳的归档文件，
exit code 非 0 表示存在 critical 失败（login_selectors 全部失效）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.async_api import Error  # noqa: E402

from spreado.core.browser import StealthBrowser  # noqa: E402
from spreado.plugin_loader import get_plugin_loader  # noqa: E402


@dataclass
class SelectorResult:
    selector: str
    found: bool
    visible: bool
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.found and self.visible


@dataclass
class PageResult:
    url: str
    reachable: bool
    nav_error: Optional[str] = None
    selectors: List[SelectorResult] = field(default_factory=list)

    @property
    def any_selector_ok(self) -> bool:
        return any(s.ok for s in self.selectors)


@dataclass
class PlatformResult:
    name: str
    display_name: str
    login: PageResult
    publish: Optional[PageResult] = None  # None = 未跑（无 cookie）

    @property
    def status(self) -> str:
        if not self.login.reachable:
            return "UNREACHABLE"
        if not self.login.any_selector_ok:
            return "BROKEN"
        if self.publish is None:
            return "PARTIAL"
        if not self.publish.reachable or not self.publish.any_selector_ok:
            return "AUTHED_BROKEN"
        return "OK"


async def _check_selectors(
    page, selectors: List[str], *, per_timeout: int = 8000
) -> List[SelectorResult]:
    """对每个 selector 做 wait_for(state='visible', timeout=per_timeout)。

    任一可见即标记为 ok；超时未出现则记 found/visible=False。
    用 wait_for 而非 is_visible 即时检查，能容忍 SPA 渲染延迟。
    """
    out: List[SelectorResult] = []
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=per_timeout)
                out.append(SelectorResult(sel, found=True, visible=True))
            except Error:
                count = 0
                try:
                    count = await page.locator(sel).count()
                except Error:
                    pass
                out.append(SelectorResult(sel, found=count > 0, visible=False))
        except Exception as e:
            out.append(
                SelectorResult(sel, found=False, visible=False, error=str(e)[:120])
            )
    return out


async def _verify_page(browser, url: str, selectors: List[str]) -> PageResult:
    result = PageResult(url=url, reachable=False)
    async with await browser.new_page() as page:
        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            result.reachable = True
        except Exception as e:
            result.nav_error = str(e)[:200]
            return result
        result.selectors = await _check_selectors(page, selectors)
    return result


async def verify_platform(
    name: str,
    *,
    headless: bool = True,
    cookies_dir: Optional[Path] = None,
) -> PlatformResult:
    loader = get_plugin_loader()
    cls = loader.get_publisher_class(name)
    if cookies_dir is not None:
        cookie_path = cookies_dir / f"{name}_uploader" / "account.json"
        inst = cls(cookie_file_path=cookie_path)
    else:
        inst = cls()

    async with await StealthBrowser.create(headless=headless) as browser:
        login_result = await _verify_page(
            browser, inst.login_url, inst._login_selectors
        )

    publish_result: Optional[PageResult] = None
    if inst.cookie_file_path.exists():
        async with await StealthBrowser.create(headless=headless) as browser:
            await browser.load_cookies_from_file(inst.cookie_file_path)
            publish_result = await _verify_page(
                browser, inst.publish_url, inst._authed_selectors
            )

    return PlatformResult(
        name=name,
        display_name=getattr(inst, "display_name", name),
        login=login_result,
        publish=publish_result,
    )


def render_report(results: List[PlatformResult], generated_at: datetime) -> str:
    lines = [
        "# 平台元素健康度报告",
        "",
        f"- 生成时间: `{generated_at.isoformat(timespec='seconds')}`",
        f"- 平台总数: {len(results)}",
        "",
        "## 状态汇总",
        "",
        "| 平台 | 状态 | 登录页 | login_selectors | publish 页 | authed_selectors |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        login_reach = "✓" if r.login.reachable else "✗"
        login_sel = (
            f"{sum(1 for s in r.login.selectors if s.ok)}/{len(r.login.selectors)}"
        )
        if r.publish is None:
            pub_reach = "—"
            pub_sel = "—"
        else:
            pub_reach = "✓" if r.publish.reachable else "✗"
            pub_sel = (
                f"{sum(1 for s in r.publish.selectors if s.ok)}/"
                f"{len(r.publish.selectors)}"
            )
        lines.append(
            f"| {r.display_name} (`{r.name}`) | **{r.status}** | "
            f"{login_reach} | {login_sel} | {pub_reach} | {pub_sel} |"
        )

    lines += ["", "## 详细结果", ""]
    for r in results:
        lines.append(f"### {r.display_name} (`{r.name}`) — {r.status}")
        lines.append("")
        lines.append(f"**登录页** `{r.login.url}` — reachable={r.login.reachable}")
        if r.login.nav_error:
            lines.append(f"  - 导航错误: `{r.login.nav_error}`")
        for s in r.login.selectors:
            mark = "✓" if s.ok else "✗"
            extra = f" (found={s.found}, visible={s.visible})" if not s.ok else ""
            err = f" — {s.error}" if s.error else ""
            lines.append(f"  - {mark} `{s.selector}`{extra}{err}")
        lines.append("")

        if r.publish is None:
            lines.append("**publish 页**: 跳过（未发现 cookie 文件）")
        else:
            lines.append(
                f"**publish 页** `{r.publish.url}` — reachable={r.publish.reachable}"
            )
            if r.publish.nav_error:
                lines.append(f"  - 导航错误: `{r.publish.nav_error}`")
            for s in r.publish.selectors:
                mark = "✓" if s.ok else "✗"
                extra = f" (found={s.found}, visible={s.visible})" if not s.ok else ""
                err = f" — {s.error}" if s.error else ""
                lines.append(f"  - {mark} `{s.selector}`{extra}{err}")
        lines.append("")

    lines += [
        "## 状态说明",
        "",
        "- **OK**: 登录页 + publish 页选择器全通过",
        "- **PARTIAL**: 登录页通过，publish 页因无 cookie 未验证",
        "- **BROKEN**: 登录页选择器全部失效（**需立即修复**）",
        "- **AUTHED_BROKEN**: cookie 有效但 publish 页选择器失效",
        "- **UNREACHABLE**: 登录页无法访问（可能是 GitHub Actions 出口 IP 被封）",
        "",
    ]
    return "\n".join(lines)


def write_reports(report_md: str, generated_at: datetime) -> Path:
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    latest = reports_dir / "selector-check-latest.md"
    archive = (
        reports_dir / f"selector-check-{generated_at.strftime('%Y%m%dT%H%M%S')}.md"
    )
    latest.write_text(report_md, encoding="utf-8")
    archive.write_text(report_md, encoding="utf-8")
    return latest


async def main() -> int:
    parser = argparse.ArgumentParser(description="验证所有平台元素健康度")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="以有头模式运行（默认 headless）",
    )
    parser.add_argument(
        "--platforms",
        nargs="*",
        help="只检查指定平台（默认全部）",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="任何 BROKEN/UNREACHABLE/AUTHED_BROKEN 都返回非 0",
    )
    parser.add_argument(
        "--cookies-dir",
        type=Path,
        default=None,
        help="cookie 根目录；目录下应有 {platform}_uploader/account.json",
    )
    args = parser.parse_args()

    loader = get_plugin_loader()
    names = args.platforms or loader.list_publisher_names()

    results: List[PlatformResult] = []
    for n in names:
        print(f"[verify] 正在检查 {n} ...", flush=True)
        try:
            r = await verify_platform(
                n, headless=not args.headed, cookies_dir=args.cookies_dir
            )
        except Exception as e:
            print(f"[verify] {n} 异常: {e}", flush=True)
            continue
        print(f"[verify] {n} -> {r.status}", flush=True)
        results.append(r)

    _BEIJING_TZ = timezone(timedelta(hours=8))
    generated_at = datetime.now(_BEIJING_TZ)
    report = render_report(results, generated_at)
    path = write_reports(report, generated_at)
    print(f"[verify] 报告已写入 {path}")

    bad_statuses = {"BROKEN", "UNREACHABLE"}
    if args.strict:
        bad_statuses.add("AUTHED_BROKEN")
    failures = [r for r in results if r.status in bad_statuses]
    if failures:
        print(
            f"[verify] {len(failures)} 个平台存在严重失败: "
            f"{[r.name for r in failures]}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
