"""小红书视频上传器。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Error, Page

from spreado.core.base_publisher import BasePublisher
from spreado.core.browser import StealthBrowser
from spreado.models.task import Task


class XiaoHongShuUploader(BasePublisher):
    """小红书视频上传器。"""

    @property
    def platform_name(self) -> str:
        return "xiaohongshu"

    @property
    def display_name(self) -> str:
        return "小红书"

    @property
    def login_url(self) -> str:
        return "https://creator.xiaohongshu.com/"

    @property
    def publish_url(self) -> str:
        return "https://creator.xiaohongshu.com/publish/publish"

    @property
    def _video_upload_url(self) -> str:
        return f"{self.publish_url}?from=homepage&target=video"

    @property
    def _image_upload_url(self) -> str:
        return f"{self.publish_url}?from=menu&target=image"

    @property
    def supported_content_types(self) -> List[str]:
        return ["video", "image_text"]

    @property
    def _login_selectors(self) -> List[str]:
        return [
            'text="短信登录"',
            'text="扫码登录"',
            'button:has-text("登")',
            ".login-btn",
        ]

    @property
    def _authed_selectors(self) -> List[str]:
        # 上传页才会渲染的元素：视频上传 input + 顶部的"上传视频"按钮
        return ["input.upload-input", 'button:has-text("上传视频")']

    # ---------------------------------------------------------------- 主流程

    async def publish_image_text(self, task: Task) -> bool:
        if not task.media_files:
            self.logger.error("[!] 图文任务缺少图片素材")
            return False

        return await self.upload_image_text_flow(
            image_paths=task.media_files,
            title=task.title,
            content=task.content,
            tags=task.tags,
            publish_date=task.publish_date,
        )

    async def upload_image_text_flow(
        self,
        image_paths: List[str | Path],
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        auto_login: bool = False,
    ) -> bool:
        try:
            with self.logger.step("upload_image_text_flow", title=title) as step:
                paths = [Path(path) for path in image_paths]
                missing = [str(path) for path in paths if not path.exists()]
                if missing:
                    self.logger.error("图片文件不存在", files=missing)
                    return False

                cookie_ok = await self.verify_cookie_flow(auto_login=auto_login)
                if not cookie_ok:
                    raise RuntimeError("cookie 无效")

                async with await StealthBrowser.create(
                    headless=self._upload_headless
                ) as browser:
                    await browser.load_cookies_from_file(self.cookie_file_path)
                    async with await browser.new_page() as page:
                        await page.goto(self.publish_url)
                        ok = await self._upload_image_text(
                            page=page,
                            image_paths=paths,
                            title=title,
                            content=content,
                            tags=tags,
                            publish_date=publish_date,
                        )
                        step.add_field(result="success" if ok else "failure")
                        return ok
        except Exception as e:
            self.logger.error("图文上传流程异常", reason=str(e)[:200])
            return False

    async def _upload_image_text(
        self,
        page: Page,
        image_paths: List[str | Path],
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
    ) -> bool:
        try:
            with self.logger.step(
                "upload_image_text", title=title, images=len(image_paths)
            ):
                with self.logger.step("goto_image_upload_page"):
                    await page.goto(self._image_upload_url)
                    try:
                        await page.wait_for_url(self._image_upload_url, timeout=5000)
                    except Error:
                        pass

                with self.logger.step("upload_image_files"):
                    if not await self._upload_image_files(page, image_paths):
                        return False

                with self.logger.step("wait_for_images_ready"):
                    if not await self._wait_for_images_ready(page):
                        return False

                with self.logger.step("fill_image_text_info", title=title):
                    if not await self._fill_image_text_info(
                        page, title, content, tags
                    ):
                        return False

                if publish_date:
                    with self.logger.step(
                        "set_schedule_time", at=publish_date.isoformat()
                    ):
                        if not await self._set_schedule_time(page, publish_date):
                            return False

                with self.logger.step("publish_image_text"):
                    if not await self._publish_image_text(page):
                        return False
            return True
        except Exception as e:
            self.logger.error("upload_image_text 异常", reason=str(e)[:200])
            return False

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
                    await page.goto(self._video_upload_url)
                    try:
                        await page.wait_for_url(self._video_upload_url, timeout=5000)
                    except Error:
                        pass

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

                with self.logger.step("publish_video"):
                    if not await self._publish_video(page):
                        return False
            return True
        except Exception as e:
            self.logger.error("upload_video 异常", reason=str(e)[:200])
            return False

    # ---------------------------------------------------------------- 子步骤

    async def _upload_image_files(
        self, page: Page, image_paths: List[str | Path]
    ) -> bool:
        try:
            await page.wait_for_selector(
                'button:has-text("上传图片"), input[type="file"][accept*="image"], input.upload-input',
                state="attached",
                timeout=15000,
            )

            upload_button = page.get_by_role("button", name=re.compile("上传图片"))
            if await upload_button.count() > 0:
                try:
                    await upload_button.first.set_input_files(image_paths)
                    return True
                except Exception as e:
                    self.logger.debug(
                        "按钮 set_input_files 失败，降级到 input",
                        reason=str(e)[:100],
                    )

            input_selectors = [
                'input[type="file"][accept*="image"]',
                'input.upload-input[type="file"]',
                'input[type="file"]',
            ]
            if not await self._wait_until_attached(
                page, input_selectors, timeout=10000
            ):
                self.logger.error("未找到图片上传 input")
                return False

            for selector in input_selectors:
                try:
                    inp = page.locator(selector).first
                    if await inp.count() == 0:
                        continue
                    await inp.wait_for(state="attached", timeout=3000)
                    await inp.set_input_files(image_paths)
                    return True
                except Exception as e:
                    self.logger.debug(
                        "图片 input 注入失败",
                        selector=selector,
                        reason=str(e)[:100],
                    )
                    continue

            self.logger.error("图片文件注入失败")
            return False
        except Exception as e:
            self.logger.error("图片文件上传失败", reason=str(e)[:200])
            return False

    async def _wait_for_images_ready(self, page: Page) -> bool:
        preview_selectors = [
            'img[src^="blob:"]',
            'div[class*="image"] img',
            'div[class*="preview"] img',
            'div[class*="upload"] img',
        ]
        editor_selectors = [
            "input[placeholder*='填写标题']",
            "textarea[placeholder*='正文']",
            "div[contenteditable='true']",
            ".tiptap-container",
        ]
        progress_selectors = [
            "div.el-progress-bar",
            'div[class*="progress"]',
            'div[class*="uploading"]',
            'div[class*="loading"]',
        ]

        async def check() -> bool:
            for selector in preview_selectors:
                el = page.locator(selector)
                if await el.count() > 0 and await el.first.is_visible():
                    return True

            has_progress = False
            for selector in progress_selectors:
                el = page.locator(selector)
                if await el.count() > 0 and await el.first.is_visible():
                    has_progress = True
                    break
            if has_progress:
                return False

            for selector in editor_selectors:
                el = page.locator(selector)
                if await el.count() > 0 and await el.first.is_visible():
                    return True
            return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=1.0, desc="images_ready"
        )

    async def _fill_image_text_info(
        self,
        page: Page,
        title: str = "",
        content: str = "",
        tags: List[str] = None,
    ) -> bool:
        try:
            await page.wait_for_selector(
                "input[placeholder*='填写标题'], textarea, div[contenteditable='true']",
                state="visible",
                timeout=15000,
            )

            title_input = page.get_by_role(
                "textbox", name=re.compile("填写标题")
            ).first
            if await title_input.count() == 0:
                title_input = page.locator("input[placeholder*='填写标题']").first
            if await title_input.count() > 0:
                await title_input.click()
                await title_input.fill(title[:20])
            elif title:
                self.logger.warning("未找到标题输入框，跳过标题")

            body_text = self._build_image_text_content(content, tags)
            if not body_text:
                return True

            body_candidates = [
                "div.tiptap-container div[contenteditable='true']",
                "div[contenteditable='true']",
                "textarea[placeholder*='正文']",
                "textarea",
            ]
            body = None
            for selector in body_candidates:
                candidate = page.locator(selector).first
                if await candidate.count() == 0:
                    continue
                try:
                    await candidate.wait_for(state="visible", timeout=3000)
                    body = candidate
                    break
                except Error:
                    continue

            if body is None:
                textboxes = page.get_by_role("textbox")
                if await textboxes.count() > 1:
                    body = textboxes.nth(1)

            if body is None:
                self.logger.error("未找到正文输入框")
                return False

            await body.click()
            try:
                await body.fill(body_text)
            except Exception:
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.keyboard.type(body_text)

            return True
        except Exception as e:
            self.logger.error("填写图文信息失败", reason=str(e)[:200])
            return False

    def _build_image_text_content(self, content: str = "", tags: List[str] = None) -> str:
        parts = []
        if content:
            parts.append(content)
        for tag in tags or []:
            clean_tag = tag.strip().lstrip("#")
            if clean_tag:
                parts.append(f"#{clean_tag}[话题]#")
        return " ".join(parts)

    async def _upload_video_file(self, page: Page, file_path: str | Path) -> bool:
        try:
            inp = page.locator("input.upload-input")
            await inp.wait_for(state="attached", timeout=10000)
            await inp.set_input_files(file_path)
            return True
        except Exception as e:
            self.logger.error("视频文件注入失败", reason=str(e)[:200])
            return False

    async def _wait_for_upload_complete(self, page: Page) -> bool:
        """轮询直到出现预览/编辑区/成功文案中的任一信号。"""
        preview_selectors = [
            "div.upload-content div.preview-new",
            "div.preview-new",
            'div[class*="preview"]',
            'img[class*="preview"]',
        ]
        success_texts = ["上传成功", "已上传", "完成"]
        info_selectors = [
            "input[placeholder*='填写标题']",
            'div[class*="title"]',
            'div[class*="content"]',
        ]
        progress_selectors = [
            "div.el-progress-bar",
            'div[class*="progress"]',
            'div[class*="uploading"]',
        ]

        async def check() -> bool:
            for sel in preview_selectors:
                if (
                    await page.locator(sel).count() > 0
                    and await page.locator(sel).first.is_visible()
                ):
                    return True
            for txt in success_texts:
                if await page.locator(f"text={txt}").count() > 0:
                    return True
            # 没有进度条时，编辑区出现也视为完成
            for sel in progress_selectors:
                if (
                    await page.locator(sel).count() > 0
                    and await page.locator(sel).first.is_visible()
                ):
                    return False
            for sel in info_selectors:
                if (
                    await page.locator(sel).count() > 0
                    and await page.locator(sel).first.is_visible()
                ):
                    return True
            return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=1.0, desc="upload_complete"
        )

    async def _fill_video_info(
        self,
        page: Page,
        title: str = "",
        content: str = "",
        tags: List[str] = None,
    ) -> bool:
        try:
            await page.wait_for_selector(
                "input[placeholder*='填写标题'], .notranslate",
                state="visible",
                timeout=10000,
            )

            title_container = page.locator("input[placeholder*='填写标题']")
            if await title_container.count() > 0:
                await title_container.fill(title[:20])
            else:
                fallback = page.locator(".notranslate")
                await fallback.click()
                await page.keyboard.press("Backspace")
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.keyboard.type(title[:20])

            desc = page.locator("div.tiptap-container div[contenteditable]")
            await desc.click()
            await desc.fill(content)

            added = 0
            for tag in tags or []:
                clean_tag = tag.lstrip("#")
                try:
                    await desc.focus()
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(800)
                    await desc.type(" ")
                    await page.wait_for_timeout(800)
                    await desc.type("#")
                    await page.wait_for_timeout(500)
                    await desc.type(clean_tag)
                    await page.wait_for_timeout(1000)
                    await page.keyboard.press("Enter")
                    added += 1
                except Exception as e:
                    self.logger.warning(
                        "标签添加失败，回退到纯文本",
                        tag=clean_tag,
                        reason=str(e)[:100],
                    )
                    try:
                        await desc.focus()
                        await page.keyboard.press("End")
                        await desc.type(f" #{clean_tag} ")
                        added += 1
                    except Exception as e2:
                        self.logger.error(
                            "标签直接追加也失败",
                            tag=clean_tag,
                            reason=str(e2)[:100],
                        )
                await desc.focus()
                await page.keyboard.press("End")
                await page.wait_for_timeout(800)

            self.logger.info("标题与标签已填充", added=added, total=len(tags or []))
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
            # 1) 打开封面编辑弹窗（点击封面预览本身）
            cover_trigger_selectors = [
                ".cover-plugin-preview .cover .default.row",
                ".cover-plugin-preview .cover",
                'div[class*="cover"]:has-text("设置封面")',
                'text="封面"',
            ]
            if not await self._click_first_visible(
                page, cover_trigger_selectors, force=True
            ):
                self.logger.error("未找到封面入口")
                return False

            await page.wait_for_selector(
                ".d-modal:has-text('设置封面')", state="visible", timeout=10000
            )

            # 2) 弹窗内 file input 是异步挂载的，先等再注入
            upload_input_selectors = [
                '.d-modal .cover-container input[type="file"][accept*="image"]',
                '.d-modal input[type="file"][accept*="image"]',
                'input.upload-input[type="file"][accept*="image"]',
            ]
            if not await self._upload_file_to_first(
                page, upload_input_selectors, thumbnail_path, timeout=10000
            ):
                self.logger.error("未找到封面图片上传 input")
                return False

            await page.wait_for_timeout(2000)

            # 3) 确认
            if not await self._click_first_visible(
                page,
                [
                    '.d-modal button:has-text("确定")',
                    '.d-modal button:has-text("确认")',
                    'button:has-text("确定")',
                ],
                force=True,
            ):
                self.logger.error("未找到确定按钮")
                return False

            try:
                await page.wait_for_selector(
                    ".d-modal:has-text('设置封面')",
                    state="hidden",
                    timeout=10000,
                )
            except Error:
                pass

            return True
        except Exception as e:
            self.logger.error("封面设置失败", reason=str(e)[:200])
            return False

    async def _set_schedule_time(self, page: Page, publish_date: datetime) -> bool:
        try:
            publish_date_str = publish_date.strftime("%Y-%m-%d %H:%M")

            # 1) 开启定时发布开关
            switch_container = page.locator(
                ".post-time-switch-container:has-text('定时发布')"
            )
            switch = switch_container.locator(".d-switch").first
            if await switch.count() == 0:
                switch = page.locator("div:has-text('定时发布') >> .d-switch").first

            if await switch.count() > 0:
                await switch.scroll_into_view_if_needed()
                checked = await switch.locator("input").evaluate("el => el.checked")
                if not checked:
                    await switch.locator(".d-switch-simulator").click(force=True)
                    await page.wait_for_timeout(1000)
            else:
                self.logger.warning("未找到定时发布开关")

            # 2) 等日期选择器渲染
            try:
                await page.wait_for_selector(
                    ".date-picker-container", state="visible", timeout=5000
                )
            except Error:
                self.logger.warning("date-picker-container 未出现")

            # 3) 设置时间
            datetime_elem = page.locator(
                ".date-picker-container .d-text, .d-datepicker-input-filter input,"
                " .d-datepicker-input-filter"
            ).first
            if await datetime_elem.count() == 0:
                self.logger.error("未找到日期输入框")
                return False
            await datetime_elem.wait_for(state="visible", timeout=5000)
            target_input = (
                datetime_elem
                if await datetime_elem.evaluate("el => el.tagName === 'INPUT'")
                else datetime_elem.locator("input").first
            )
            await target_input.click(force=True)
            await target_input.fill(publish_date_str)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            return True
        except Exception as e:
            self.logger.error("定时发布设置失败", reason=str(e)[:200])
            return False

    async def _publish_video(self, page: Page) -> bool:
        return await self._click_publish_button(page)

    async def _publish_image_text(self, page: Page) -> bool:
        return await self._click_publish_button(page)

    async def _click_publish_button(self, page: Page) -> bool:
        try:
            button = page.get_by_role("button", name=re.compile("发布|定时发布")).first
            if await button.count() > 0:
                await button.scroll_into_view_if_needed()
                await button.wait_for(state="visible", timeout=10000)
                return await self._click_and_wait_for_url(
                    page,
                    button,
                    re.compile(r"/success|published=true"),
                    timeout=30000,
                )

            if await self._click_xhs_publish_host(page):
                return True

            self.logger.error("未找到发布按钮")
            return False
        except Exception as e:
            self.logger.error("发布异常", reason=str(e)[:200])
            return False

    async def _click_xhs_publish_host(self, page: Page) -> bool:
        try:
            host = page.locator('xhs-publish-btn[submit-disabled="false"]').first
            if await host.count() == 0:
                return False
            await host.scroll_into_view_if_needed()
            await host.wait_for(state="visible", timeout=10000)
            box = await host.bounding_box()
            if not box:
                self.logger.error("未找到发布按钮")
                return False

            # xhs-publish-btn 使用 closed shadow DOM，无法定位内部 button。
            # shadow 内两个 120px 按钮居中排列，gap 24px；发布按钮中心在宿主中心右侧 72px。
            x = box["x"] + box["width"] * 0.5 + 72
            y = box["y"] + box["height"] * 0.5
            await page.mouse.click(x, y)

            try:
                await page.wait_for_url(
                    re.compile(r"/success|published=true"), timeout=30000
                )
            except Error:
                current = page.url
                if not re.search(r"/success|published=true", current):
                    self.logger.error("点击发布宿主后 URL 未匹配", url=current)
                    return False
            return True
        except Exception as e:
            self.logger.error("点击小红书发布宿主失败", reason=str(e)[:200])
            return False
