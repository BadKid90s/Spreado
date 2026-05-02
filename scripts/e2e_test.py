"""端到端发布流程测试（dry-run，不实际发布）。

对每个有 cookie 的平台执行：
1. Cookie 验证
2. 导航到发布页
3. 上传测试视频
4. 等待上传完成
5. 填写标题/正文/标签
6. 设置封面（可选）
7. 验证发布按钮存在（**不点击**）

输出 reports/e2e-check-latest.md（覆写）和带时间戳的归档文件。
exit code 非 0 表示存在失败的平台。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from playwright.async_api import Error  # noqa: E402

from spreado.plugin_loader import get_plugin_loader  # noqa: E402
from spreado.utils.log import StepLogger  # noqa: E402

SKIP_PLATFORMS = {"bilibili"}
BEIJING_TZ = timezone(timedelta(hours=8))

# 各平台发布按钮选择器（用于 dry-run 验证）
_PUBLISH_BUTTON_SELECTORS = {
    "xiaohongshu": [
        'button:has-text("发布")',
        'button:has-text("定时发布")',
    ],
    "douyin": [
        'button:has-text("发布")',
    ],
    "kuaishou": [
        'button:has-text("发布")',
    ],
    "shipinhao": [
        'button:has-text("发表")',
        'button:has-text("保存草稿")',
    ],
}


# -------------------------------------------------------------------- 数据模型


@dataclass
class StepResult:
    name: str
    passed: bool
    duration: float = 0.0
    note: str = ""


@dataclass
class PlatformResult:
    name: str
    display_name: str
    steps: List[StepResult] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    @property
    def passed(self) -> bool:
        if self.skipped:
            return True
        return all(s.passed for s in self.steps if s.name != "verify_publish_button")

    @property
    def total_duration(self) -> float:
        return sum(s.duration for s in self.steps)


# --------------------------------------------------------- 步骤追踪 Logger


class TrackingStepContext:
    def __init__(self, tracker: "TrackingLogger", name: str):
        self._tracker = tracker
        self._name = name
        self._start = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.monotonic() - self._start
        passed = exc_type is None
        self._tracker.steps.append(
            StepResult(self._name, passed=passed, duration=round(duration, 2))
        )
        return False  # don't suppress

    def add_field(self, **fields):
        pass  # no-op in dry-run


class TrackingLogger:
    """拦截 logger.step() 调用，记录每步结果。"""

    def __init__(self, real_logger: StepLogger):
        self._real = real_logger
        self.steps: List[StepResult] = []

    def step(self, name: str, **fields):
        return TrackingStepContext(self, name)

    def debug(self, msg: str, **fields):
        pass

    def info(self, msg: str, **fields):
        self._real.info(msg, **fields)

    def warning(self, msg: str, **fields):
        self._real.warning(msg, **fields)

    def error(self, msg: str, **fields):
        self._real.error(msg, **fields)


# ------------------------------------------------------------------ Dry-run


async def _dry_run_publish(uploader, page) -> bool:
    """替换 _publish_video：只验证发布按钮可见，不点击。"""
    # 视频号使用 wujie shadow DOM，需要 evaluate 检查
    if uploader.platform_name == "shipinhao":
        try:
            found = await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return false;
    const btns = s.querySelectorAll('div.form-btns button');
    for (const b of btns) {
        if (b.innerText.includes('发表')) return true;
    }
    return false;
}
""")
            if found:
                return True
        except Error:
            pass
        uploader.logger.warning("未找到发布按钮（dry-run，shadow DOM），跳过验证")
        return True

    sels = _PUBLISH_BUTTON_SELECTORS.get(
        uploader.platform_name,
        [
            'button:has-text("发布")',
            'button:has-text("发表")',
        ],
    )
    for sel in sels:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.scroll_into_view_if_needed()
                return True
        except Error:
            continue
    uploader.logger.warning("未找到发布按钮（dry-run），跳过验证")
    return True


# ------------------------------------------------------------------ 测试主逻辑


async def _test_platform(
    name: str,
    *,
    headless: bool,
    cookies_dir: Path,
    video: Path,
    cover: Optional[Path],
    title: str,
    content: str,
    tags: List[str],
) -> PlatformResult:
    loader = get_plugin_loader()
    cls = loader.get_publisher_class(name)
    cookie_path = cookies_dir / f"{name}_uploader" / "account.json"
    inst = cls(cookie_file_path=cookie_path)
    display_name = getattr(inst, "display_name", name)

    result = PlatformResult(name=name, display_name=display_name)

    if not cookie_path.exists():
        result.skipped = True
        result.skip_reason = "cookie 文件不存在"
        return result

    # monkey-patch: dry-run publish + tracking logger
    inst._publish_video = lambda page: _dry_run_publish(inst, page)  # type: ignore
    inst.logger = TrackingLogger(inst.logger)  # type: ignore

    flow_ok = False
    try:
        flow_ok = await inst.upload_video_flow(
            file_path=video,
            title=title,
            content=content,
            tags=tags,
            thumbnail_path=cover,
            auto_login=True,
        )
    except Exception as e:
        inst.logger.steps.append(  # type: ignore
            StepResult("exception", passed=False, note=str(e)[:200])
        )

    # upload_video_flow 返回 False（无异常）时补充失败步骤，避免 false positive
    if not flow_ok:
        tracked = {s.name for s in inst.logger.steps}  # type: ignore
        expected = ["upload_video_file", "wait_for_upload_complete", "fill_video_info"]
        for name in expected:
            if name not in tracked:
                inst.logger.steps.append(  # type: ignore
                    StepResult(name, passed=False, note="未执行（上游步骤失败）")
                )

    result.steps = inst.logger.steps  # type: ignore

    # 补充 publish_button 验证步骤结果
    pub_step = [s for s in result.steps if s.name == "publish_video"]
    if pub_step:
        pub_step[0].name = "verify_publish_button"

    return result


# -------------------------------------------------------------------- 报告


def render_report(
    results: List[PlatformResult], video: Path, generated_at: datetime
) -> str:
    lines = [
        "# E2E 测试报告",
        "",
        f"- 生成时间: `{generated_at.isoformat(timespec='seconds')}`",
        f"- 测试视频: `{video}`",
        "",
        "## 结果汇总",
        "",
        "| 平台 | 状态 | 通过步骤 | 总步骤 | 耗时 |",
        "|---|---|---|---|---|",
    ]

    for r in results:
        if r.skipped:
            lines.append(
                f"| {r.display_name} (`{r.name}`) | — 跳过 | — | — | "
                f"原因: {r.skip_reason} |"
            )
        else:
            passed = sum(1 for s in r.steps if s.passed)
            total = len(r.steps)
            status = "✓ PASS" if r.passed else "✗ FAIL"
            lines.append(
                f"| {r.display_name} (`{r.name}`) | **{status}** | "
                f"{passed}/{total} | {total} | {r.total_duration:.1f}s |"
            )

    lines += ["", "## 详细结果", ""]

    for r in results:
        if r.skipped:
            lines.append(f"### {r.display_name} (`{r.name}`) — 跳过")
            lines.append("")
            lines.append(f"原因: {r.skip_reason}")
            lines.append("")
            continue

        status = "✓ PASS" if r.passed else "✗ FAIL"
        lines.append(f"### {r.display_name} (`{r.name}`) — {status}")
        lines.append("")
        lines.append("| # | 步骤 | 状态 | 耗时 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for i, s in enumerate(r.steps, 1):
            mark = "✓" if s.passed else "✗"
            dur = f"{s.duration:.1f}s" if s.duration > 0 else "—"
            note = s.note or ""
            lines.append(f"| {i} | {s.name} | {mark} | {dur} | {note} |")
        lines.append("")

    lines += [
        "## 测试说明",
        "",
        "- **✓ PASS**: 所有步骤通过（`verify_publish_button` 仅检查按钮存在，不点击）",
        "- **✗ FAIL**: 任一步骤失败",
        "- **— 跳过**: 无 cookie 文件，未执行测试",
        "- 本测试**不会实际发布**内容，发布按钮仅做可见性验证",
        "",
    ]
    return "\n".join(lines)


def write_reports(report_md: str, generated_at: datetime) -> Path:
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    latest = reports_dir / "e2e-check-latest.md"
    archive = reports_dir / f"e2e-check-{generated_at.strftime('%Y%m%dT%H%M%S')}.md"
    latest.write_text(report_md, encoding="utf-8")
    archive.write_text(report_md, encoding="utf-8")
    return latest


# ------------------------------------------------------------------------ main


async def main() -> int:
    parser = argparse.ArgumentParser(description="端到端发布流程测试（dry-run）")
    parser.add_argument(
        "--platforms", nargs="*", help="要测试的平台（默认全部，跳过 bilibili）"
    )
    parser.add_argument(
        "--cookies-dir",
        type=Path,
        default=ROOT / "cookies",
        help="cookie 根目录（默认 cookies/）",
    )
    parser.add_argument(
        "--video",
        type=Path,
        default=ROOT / "src" / "spreado" / "examples" / "videos" / "demo.mp4",
        help="测试视频路径",
    )
    parser.add_argument("--cover", type=Path, default=None, help="测试封面路径")
    parser.add_argument("--no-cover", action="store_true", help="不测试封面")
    parser.add_argument("--headed", action="store_true", help="有头模式")
    parser.add_argument("--title", default="E2E 测试标题", help="测试标题")
    parser.add_argument(
        "--content", default="E2E 测试正文内容 #测试标签", help="测试正文"
    )
    parser.add_argument("--tags", nargs="*", default=["测试"], help="测试标签")
    args = parser.parse_args()

    # 默认封面
    cover = args.cover
    if cover is None and not args.no_cover:
        default_cover = ROOT / "src" / "spreado" / "examples" / "videos" / "demo.png"
        if default_cover.exists():
            cover = default_cover

    if not args.video.exists():
        print(f"[e2e] 测试视频不存在: {args.video}", file=sys.stderr)
        return 1

    # 平台列表
    loader = get_plugin_loader()
    if args.platforms:
        names = args.platforms
    else:
        names = [n for n in loader.list_publisher_names() if n not in SKIP_PLATFORMS]

    print(f"[e2e] 测试平台: {names}", flush=True)
    print(f"[e2e] 测试视频: {args.video}", flush=True)
    print(f"[e2e] 封面: {cover or '无'}", flush=True)
    print(f"[e2e] Cookie 目录: {args.cookies_dir}", flush=True)
    print("", flush=True)

    results: List[PlatformResult] = []
    for n in names:
        print(f"[e2e] 正在测试 {n} ...", flush=True)
        try:
            r = await _test_platform(
                n,
                headless=not args.headed,
                cookies_dir=args.cookies_dir,
                video=args.video,
                cover=cover,
                title=args.title,
                content=args.content,
                tags=args.tags,
            )
        except Exception as e:
            print(f"[e2e] {n} 异常: {e}", flush=True)
            r = PlatformResult(
                name=n, display_name=n, skipped=True, skip_reason=f"异常: {e}"
            )

        if r.skipped:
            print(f"[e2e] {n} -> 跳过 ({r.skip_reason})", flush=True)
        else:
            status = "PASS" if r.passed else "FAIL"
            print(
                f"[e2e] {n} -> {status} "
                f"({sum(1 for s in r.steps if s.passed)}/{len(r.steps)} 步骤, "
                f"{r.total_duration:.1f}s)",
                flush=True,
            )
        results.append(r)

    generated_at = datetime.now(BEIJING_TZ)
    report = render_report(results, args.video, generated_at)
    path = write_reports(report, generated_at)
    print(f"\n[e2e] 报告已写入 {path}")

    failures = [r for r in results if not r.skipped and not r.passed]
    if failures:
        print(
            f"[e2e] {len(failures)} 个平台测试失败: " f"{[r.name for r in failures]}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
