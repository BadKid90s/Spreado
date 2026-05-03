"""视频号上传器。

wujie 微前端将内容放在 shadow DOM 内，Playwright CSS locator 无法穿透。
本模块通过 CDP + evaluate 在 shadow root 内操作所有元素。
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from playwright.async_api import Page

from spreado.core.base_publisher import BasePublisher

_SHADOW_EVAL = """
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return null;
    return %s;
}
"""


def _format_str_for_short_title(origin_title: str) -> str:
    allowed_special_chars = "《》" ":+?%°"
    filtered_chars = [
        (
            char
            if char.isalnum() or char in allowed_special_chars
            else " " if char == "," else ""
        )
        for char in origin_title
    ]
    s = "".join(filtered_chars)
    if len(s) > 16:
        s = s[:16]
    elif len(s) < 6:
        s += " " * (6 - len(s))
    return s


class ShiPinHaoUploader(BasePublisher):
    """视频号上传器。"""

    @property
    def _upload_headless(self) -> bool:
        return True

    @property
    def platform_name(self) -> str:
        return "shipinhao"

    @property
    def display_name(self) -> str:
        return "视频号"

    @property
    def login_url(self) -> str:
        return "https://channels.weixin.qq.com/login.html"

    @property
    def publish_url(self) -> str:
        return "https://channels.weixin.qq.com/platform/post/create"

    @property
    def _login_selectors(self) -> List[str]:
        return [
            ".login-view",
            ".login-content",
            "iframe.display",
            'link:has-text("视频号助手")',
        ]

    @property
    def _authed_selectors(self) -> List[str]:
        return ["div.input-editor", 'button:has-text("发表")']

    # ---------------------------------------------------------------- shadow DOM helpers

    async def _shadow_eval(self, page: Page, js: str) -> Any:
        """在 wujie shadow root 上下文执行 JS 并返回结果。"""
        return await page.evaluate(_SHADOW_EVAL % js)

    async def _shadow_wait(
        self, page: Page, selector: str, timeout: float = 20.0
    ) -> bool:
        """轮询等待 shadow DOM 内出现 selector 对应的元素。"""
        deadline = time.monotonic() + timeout
        expr = f"!!s.querySelector('{selector}')"
        while time.monotonic() < deadline:
            try:
                if await self._shadow_eval(page, expr):
                    return True
            except Exception:
                pass
            await page.wait_for_timeout(500)
        return False

    # ---------------------------------------------------------------- CDP file injection

    _MIME_MAP = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    async def _cdp_set_file(
        self,
        page: Page,
        selector: str,
        file_path: str,
        mime_type: Optional[str] = None,
    ) -> bool:
        """向 wujie shadow DOM 内的 file input 注入文件。

        使用 CDP Runtime.callFunctionOn 将文件数据作为独立参数传入，
        构造 File + DataTransfer 写入 input.files 并 dispatch change 事件。
        """
        import base64

        file_path_str = str(Path(file_path).resolve())
        file_bytes = Path(file_path_str).read_bytes()
        b64 = base64.b64encode(file_bytes).decode()
        filename = Path(file_path_str).name
        if mime_type is None:
            ext = Path(file_path_str).suffix.lower()
            mime_type = self._MIME_MAP.get(ext, "application/octet-stream")

        cdp = await page.context.new_cdp_session(page)
        try:
            # 获取全局对象引用作为 callFunctionOn 的 receiver
            global_result = await cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "globalThis",
                    "returnByValue": False,
                },
            )
            object_id = global_result["result"].get("objectId")
            if not object_id:
                return False

            result = await cdp.send(
                "Runtime.callFunctionOn",
                {
                    "objectId": object_id,
                    "functionDeclaration": f"""function(b64Data, fname) {{
                    const w = document.querySelector('wujie-app');
                    const s = w && w.shadowRoot;
                    if (!s) return {{ ok: false, reason: 'no_shadow' }};
                    const input = s.querySelector('{selector}');
                    if (!input) return {{ ok: false, reason: 'no_input' }};
                    const byteStr = atob(b64Data);
                    const arr = new Uint8Array(byteStr.length);
                    for (let i = 0; i < byteStr.length; i++) arr[i] = byteStr.charCodeAt(i);
                    const file = new File([arr], fname, {{ type: '{mime_type}' }});
                    const dt = new DataTransfer();
                    dt.items.add(file);
                    input.files = dt.files;
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return {{ ok: true, count: input.files.length }};
                }}""",
                    "arguments": [
                        {"type": "string", "value": b64},
                        {"type": "string", "value": filename},
                    ],
                    "returnByValue": True,
                },
            )
            value = result.get("result", {}).get("value", {})
            return value.get("ok") is True
        finally:
            await cdp.detach()

    # ---------------------------------------------------------------- 发布页就绪（微前端偶发「页面加载失败」）

    async def _try_click_reload_on_failed_shell(self, page: Page) -> bool:
        """助手外壳常见文案「页面加载失败」+「重新加载」，点击后子 iframe 会重拉。"""
        targets = [page]
        try:
            targets.extend(list(page.frames))
        except Exception:
            pass
        for target in targets:
            try:
                txt = await target.evaluate(
                    "() => (document.body && document.body.innerText) || ''"
                )
            except Exception:
                continue
            if "页面加载失败" not in txt:
                continue
            try:
                btn = target.get_by_text("重新加载", exact=True)
                if await btn.count() > 0:
                    await btn.first.click(timeout=8000)
                    self.logger.info("视频号助手 shell：已点击重新加载")
                    await page.wait_for_timeout(4000)
                    return True
            except Exception:
                continue
        return False

    async def _wait_publish_shell_ready(self, page: Page) -> bool:
        """goto 之后等待 shadow 内出现上传 input；必要时点击 shell 的重新加载并重试。"""
        for cycle in range(4):
            await self._try_click_reload_on_failed_shell(page)
            try:
                await page.wait_for_selector(
                    "wujie-app",
                    state="attached",
                    timeout=15000,
                )
            except Exception:
                pass
            if await self._shadow_wait(page, 'input[type="file"]', timeout=45):
                return True
            if cycle < 3:
                self.logger.warning(
                    "视频号发布页未就绪，整页刷新重试",
                    cycle=cycle + 1,
                )
                await page.goto(
                    self.publish_url,
                    timeout=60000,
                    wait_until="load",
                )
                await page.wait_for_timeout(5000)
        return False

    # ---------------------------------------------------------------- 主流程

    async def _upload_video(
        self,
        page: Page,
        file_path: str | Path,
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
    ) -> bool:
        try:
            with self.logger.step("upload_video", title=title, file=str(file_path)):
                with self.logger.step("goto_upload_page"):
                    await page.goto(
                        self.publish_url,
                        timeout=60000,
                        wait_until="load",
                    )
                    try:
                        await page.wait_for_url(self.publish_url, timeout=5000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(5000)
                    if not await self._wait_publish_shell_ready(page):
                        raise RuntimeError("wujie shadow DOM 未渲染 upload 区域")

                with self.logger.step("upload_video_file", file=str(file_path)):
                    if not await self._upload_video_file(page, file_path):
                        return False

                with self.logger.step("wait_for_upload_complete"):
                    if not await self._wait_for_upload_complete(page):
                        return False

                with self.logger.step("fill_video_info", title=title):
                    if not await self._fill_video_info(page, title, content, tags):
                        return False

                with self.logger.step("set_thumbnail", path=str(thumbnail_path or "")):
                    if not await self._set_thumbnail(page, thumbnail_path):
                        return False

                if publish_date:
                    with self.logger.step(
                        "set_schedule_time", at=publish_date.isoformat()
                    ):
                        if not await self._set_schedule_time(page, publish_date):
                            return False

                with self.logger.step("add_short_title"):
                    if not await self._add_short_title(page, title):
                        return False

                with self.logger.step("publish_video"):
                    if not await self._publish_video(page):
                        return False
            return True
        except Exception as e:
            self.logger.error("upload_video 异常", reason=str(e)[:200])
            return False

    # ---------------------------------------------------------------- 子步骤

    async def _upload_video_file(self, page: Page, file_path: str | Path) -> bool:
        ok = await self._cdp_set_file(page, 'input[type="file"]', str(file_path))
        if ok:
            self.logger.info("视频文件已注入")
        else:
            self.logger.error("文件注入失败：未找到 shadow DOM 内的 file input")
        return ok

    async def _wait_for_upload_complete(self, page: Page) -> bool:
        """轮询直到发表按钮可点击（非 disabled），且封面区域就绪。"""

        async def check() -> bool:
            try:
                result = await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return null;
    const btn = s.querySelector('button.weui-desktop-btn_primary');
    const progress = s.querySelector('[class*="progress"]');
    const editor = s.querySelector('.input-editor');
    const coverReady = !!s.querySelector('div.tips-wrap');
    if (btn && !btn.className.includes('disabled') && coverReady) return true;
    if (editor && !progress && coverReady) return true;
    return false;
}
""")
                return result is True
            except Exception:
                return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=2.0, desc="upload_complete"
        )

    async def _fill_video_info(
        self, page: Page, title: str = "", content: str = "", tags: List[str] = None
    ) -> bool:
        try:
            # 点击编辑器获取焦点
            await self._shadow_eval(
                page,
                """
(() => { s.querySelector('.input-editor').click(); })()
""",
            )
            await page.wait_for_timeout(500)

            # 输入标题
            await page.keyboard.type(title)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(300)

            # 输入正文
            await page.keyboard.type(content)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(300)

            # 输入标签
            if tags:
                for tag in tags:
                    tag_text = tag if tag.startswith("#") else "#" + tag
                    await page.keyboard.type(tag_text)
                    await page.keyboard.press("Space")
                    await page.wait_for_timeout(300)

            self.logger.info("标题与标签已填充", total=len(tags or []))
            return True
        except Exception as e:
            self.logger.error("填写视频信息失败", reason=str(e)[:200])
            return False

    async def _set_thumbnail(
        self, page: Page, thumbnail_path: Optional[str | Path]
    ) -> bool:
        if not thumbnail_path:
            self.logger.info("无封面，跳过")
            return True
        if not Path(thumbnail_path).exists():
            self.logger.warning("封面文件不存在，跳过", path=str(thumbnail_path))
            return True

        try:
            # 1) 等待封面区域渲染（无头模式下可能较慢）
            await self._shadow_wait(page, "div.tips-wrap", timeout=15)

            # 2) 点击个人主页卡片（重试：无头模式下可能需要滚动或等待）
            clicked = False
            for attempt in range(4):
                clicked = await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return false;
    const el = s.querySelector('div.tips-wrap div.cover-tips');
    if (el && el.innerText.includes('个人主页卡片')) {
        el.closest('.tips-wrap').click();
        return true;
    }
    return false;
}
""")
                if clicked:
                    break
                if attempt < 3:
                    # 无头模式下封面区域可能需要滚动才可见
                    await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return;
    const el = s.querySelector('div.tips-wrap');
    if (el) el.scrollIntoView({ block: 'center' });
}
""")
                    await page.wait_for_timeout(2000)
            if not clicked:
                self.logger.warning("未找到个人主页卡片入口，跳过封面")
                return True
            self.logger.info("已点击个人主页卡片")

            # 3) 等待上传封面元素
            await self._shadow_wait(page, "div.single-cover-uploader-wrap", timeout=15)

            # 3) 通过 CDP 注入封面图片
            ok = await self._cdp_set_file(
                page,
                'div.single-cover-uploader-wrap input[type="file"][accept*="image"]',
                str(thumbnail_path),
            )
            if not ok:
                self.logger.error("封面图片注入失败")
                return False
            self.logger.info("封面图片已选择")

            # 4) 等待裁剪对话框出现
            await self._shadow_wait(page, "div.weui-desktop-dialog__wrp", timeout=15)
            # 确认对话框实际可见（querySelector 不支持 :visible）
            for _ in range(6):
                visible = await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return false;
    const d = s.querySelector('div.weui-desktop-dialog__wrp');
    if (!d) return false;
    const st = getComputedStyle(d);
    return st.display !== 'none' && st.visibility !== 'hidden' && st.opacity !== '0';
}
""")
                if visible:
                    break
                await page.wait_for_timeout(500)

            # 5) 点击确认按钮
            confirmed = await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return false;
    const btns = s.querySelectorAll('div.cover-set-footer button');
    for (const b of btns) { if (b.innerText.includes('确认')) { b.click(); return true; } }
    return false;
}
""")
            if not confirmed:
                # 无头模式下对话框渲染慢，等一下再试
                await page.wait_for_timeout(3000)
                await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return;
    const btns = s.querySelectorAll('div.cover-set-footer button');
    for (const b of btns) { if (b.innerText.includes('确认')) { b.click(); return; } }
}
""")
            self.logger.info("封面设置完成")
            await page.wait_for_timeout(2000)
            return True

        except Exception as e:
            self.logger.error("封面设置失败", reason=str(e)[:200])
            return False

    async def _set_schedule_time(self, page: Page, publish_date: datetime) -> bool:
        try:
            # 点击定时选项
            await self._shadow_eval(
                page,
                """
(() => {
    const labels = s.querySelectorAll('label');
    for (const l of labels) { if (l.innerText.includes('定时')) { l.click(); break; } }
})()
""",
            )
            await page.wait_for_timeout(500)

            # 日期选择
            day_str = str(publish_date.day)
            await self._shadow_eval(
                page,
                f"""
(() => {{
    const cells = s.querySelectorAll('table a');
    for (const c of cells) {{
        if (!c.className.includes('disabled') && c.innerText.trim() === '{day_str}') {{
            c.click(); break;
        }}
    }}
}})()
""",
            )
            await page.wait_for_timeout(500)

            # 时间输入
            time_str = publish_date.strftime("%H:%M")
            await self._shadow_eval(
                page,
                """
(() => {
    const inp = s.querySelector('input[placeholder*="时间"]');
    if (inp) { inp.click(); }
})()
""",
            )
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.type(time_str)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)

            self.logger.info("定时发布时间设置完成")
            return True
        except Exception as e:
            self.logger.error("定时发布设置失败", reason=str(e)[:200])
            return False

    async def _add_short_title(self, page: Page, title: str) -> bool:
        try:
            short_title = _format_str_for_short_title(title)
            await self._shadow_eval(
                page,
                f"""
(() => {{
    const els = s.querySelectorAll('span input[type="text"]');
    for (const inp of els) {{
        const wrap = inp.closest('.form-item');
        if (wrap && wrap.innerText.includes('短标题')) {{
            inp.focus(); inp.value = '{short_title}';
            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
            return;
        }}
    }}
}})()
""",
            )
            self.logger.info("短标题已添加", title=short_title)
            return True
        except Exception as e:
            self.logger.error("添加短标题失败", reason=str(e)[:200])
            return False

    async def _publish_video(self, page: Page) -> bool:
        try:
            clicked = await self._shadow_eval(
                page,
                """
(() => {
    const btns = s.querySelectorAll('div.form-btns button');
    for (const b of btns) { if (b.innerText.includes('发表') && !b.className.includes('disabled')) {
        b.click(); return true;
    }}
    return false;
})()
""",
            )
            if not clicked:
                self.logger.error("未找到可点击的发表按钮")
                return False

            # 等待跳转到 /post/list（发布成功）
            pattern = re.compile(r"/post/list")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if pattern.search(page.url):
                    self.logger.info("视频发布成功")
                    return True
                await page.wait_for_timeout(1000)

            self.logger.warning("发布跳转超时，检查 URL", url=page.url)
            return bool(pattern.search(page.url))

        except Exception as e:
            self.logger.error("发布异常", reason=str(e)[:200])
            return False
