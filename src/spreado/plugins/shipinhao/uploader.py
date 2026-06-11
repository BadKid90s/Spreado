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
        return await page.evaluate(_SHADOW_EVAL % js.strip())

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

    async def _cdp_set_file(self, page: Page, selector: str, file_path: str) -> bool:
        """向 wujie shadow DOM 内的 file input 注入文件。

        使用 CDP Runtime.callFunctionOn 将文件数据作为独立参数传入，
        构造 File + DataTransfer 写入 input.files 并 dispatch change 事件。
        """
        import base64

        file_path_str = str(Path(file_path).resolve())
        file_bytes = Path(file_path_str).read_bytes()
        b64 = base64.b64encode(file_bytes).decode()
        filename = Path(file_path_str).name

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
                    const file = new File([arr], fname, {{ type: 'video/mp4' }});
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

    # ---------------------------------------------------------------- 主流程

    async def _wait_for_publish_page_ready(
        self, page: Page, timeout: float = 20.0
    ) -> bool:
        """导航到发布页后等待 wujie shadow DOM 渲染完毕。"""
        try:
            await page.wait_for_url(self.publish_url, timeout=5000)
        except Exception:
            pass
        # 等待 file input（视频上传区域）渲染
        if not await self._shadow_wait(page, 'input[type="file"]', timeout=timeout):
            self.logger.error("wujie shadow DOM 未渲染 upload 区域", url=page.url)
            return False
        return True

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
                    await page.goto(self.publish_url)
                    if not await self._wait_for_publish_page_ready(page):
                        raise RuntimeError("发布页未就绪")

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
        ok = await self._cdp_set_file(
            page, 'input[type="file"][accept*="video"]', str(file_path)
        )
        if ok:
            self.logger.info("视频文件已注入")
        else:
            self.logger.error("文件注入失败：未找到 shadow DOM 内的 file input")
        return ok

    async def _wait_for_upload_complete(self, page: Page) -> bool:
        """轮询直到视频上传完成：发表按钮变为可点击状态。"""

        async def check() -> bool:
            try:
                result = await page.evaluate("""
() => {
    const w = document.querySelector('wujie-app');
    const s = w && w.shadowRoot;
    if (!s) return null;
    // 找到"发表"按钮，检查其是否已从 disabled 变为可点击
    const btns = s.querySelectorAll('button.weui-desktop-btn_primary');
    for (const b of btns) {
        if (b.innerText.includes('发表') && !b.className.includes('disabled') && !b.className.includes('weui-desktop-btn_disabled')) {
            return true;
        }
    }
    // 检查视频预览/编辑区是否出现（上传完成的另一个信号）
    const preview = s.querySelector('.input-editor');
    const progress = s.querySelector('.ant-upload-list-progress, [class*="upload"][class*="progress"]');
    if (preview && !progress) return true;
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

            # 输入标题 (insert_text 比 type 更快更可靠)
            await page.keyboard.insert_text(title)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(300)

            # 输入正文
            if content:
                await page.keyboard.insert_text(content)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(300)

            # 输入标签
            if tags:
                for tag in tags:
                    tag_text = tag if tag.startswith("#") else "#" + tag
                    await page.keyboard.insert_text(tag_text)
                    await page.keyboard.press("Space")
                    await page.wait_for_timeout(200)

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
        # 当前 shipinhao 发布页已移除"个人主页卡片"封面入口，
        # 封面仅在发布后通过"修改描述和封面"功能设置。
        self.logger.info(
            "封面设置不支持：shipinhao 发布页已无封面入口，请在发布后通过列表页手动设置"
        )
        return True

    async def _set_schedule_time(self, page: Page, publish_date: datetime) -> bool:
        try:
            # 1) 点击"定时" radio label
            await self._shadow_eval(
                page,
                """
(() => {
    const labels = s.querySelectorAll('label.weui-desktop-form__check-label');
    for (const l of labels) { if (l.innerText.includes('定时')) { l.click(); return; } }
})()
""",
            )
            await page.wait_for_timeout(800)

            # 2) 在日历中选择日期
            day_str = str(publish_date.day)
            await self._shadow_eval(
                page,
                f"""
(() => {{
    const cells = s.querySelectorAll('table a');
    for (const c of cells) {{
        if (!c.className.includes('disabled') && c.innerText.trim() === '{day_str}') {{
            c.click(); return;
        }}
    }}
}})()
""",
            )
            await page.wait_for_timeout(500)

            # 3) 填入时间 — 先尝试直接设置 value，再用键盘作为备选
            time_str = publish_date.strftime("%H:%M")
            set_ok = await self._shadow_eval(
                page,
                f"""
(() => {{
    const inp = s.querySelector('input[placeholder="请选择时间"]');
    if (inp) {{
        inp.focus();
        inp.value = '{time_str}';
        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
        return true;
    }}
    return false;
}})()
""",
            )
            if not set_ok:
                # 备选：通过键盘输入时间
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
    const inp = s.querySelector('input[placeholder*="短标题"]');
    if (inp) {{
        inp.focus();
        inp.value = '{short_title}';
        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
        return;
    }}
    // 备选：通过 .form-item 文本查找
    const items = s.querySelectorAll('.form-item');
    for (const item of items) {{
        if (item.innerText.includes('短标题')) {{
            const input = item.querySelector('input[type="text"]');
            if (input) {{
                input.focus();
                input.value = '{short_title}';
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
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
    const btns = s.querySelectorAll('button.weui-desktop-btn_primary');
    for (const b of btns) {
        if (b.innerText.includes('发表') && !b.className.includes('disabled') && !b.className.includes('weui-desktop-btn_disabled')) {
            b.click(); return true;
        }
    }
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
