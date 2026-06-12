"""小红书视频上传器。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Error, Page

from spreado.core.base_publisher import BasePublisher
from spreado.core.browser import StealthBrowser


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
    def _image_text_upload_url(self) -> str:
        return f"{self.publish_url}?from=tab_switch&target=image"

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
        return ["input.upload-input", 'button:has-text("上传视频")']

    # ---------------------------------------------------------------- 图文发布

    async def _upload_images(self, page: Page, image_paths: List[str | Path]) -> bool:
        """上传图片到图文编辑器。"""
        try:
            inp = page.locator("input.upload-input")
            await inp.wait_for(state="attached", timeout=10000)
            files = [str(Path(p).resolve()) for p in image_paths]
            await inp.set_input_files(files)
            self.logger.info("图片已上传", count=len(files))
            return True
        except Exception as e:
            self.logger.error("图片上传失败", reason=str(e)[:200])
            return False

    async def _wait_for_image_upload_complete(self, page: Page) -> bool:
        """等待图片上传完成：标题输入框出现。"""

        async def check() -> bool:
            title = page.locator("input[placeholder*='填写标题']").first
            if await title.count() > 0 and await title.is_visible():
                return True
            return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=1.5, desc="image_upload_complete"
        )

    async def _upload_image_text(
        self,
        page: Page,
        image_paths: List[str | Path],
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
    ) -> bool:
        """图文发布主流程。"""
        try:
            with self.logger.step(
                "upload_image_text", title=title, images=str(len(image_paths))
            ):
                with self.logger.step("goto_upload_page"):
                    await page.goto(self._image_text_upload_url)
                    try:
                        await page.wait_for_url(
                            self._image_text_upload_url, timeout=5000
                        )
                    except Error:
                        pass

                with self.logger.step("upload_images", count=len(image_paths)):
                    if not await self._upload_images(page, image_paths):
                        return False

                with self.logger.step("wait_for_upload_complete"):
                    if not await self._wait_for_image_upload_complete(page):
                        return False

                with self.logger.step("fill_video_info", title=title):
                    if not await self._fill_video_info(page, title, content, tags):
                        return False

                with self.logger.step(
                    "set_thumbnail", path=str(thumbnail_path or "")
                ):
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
            self.logger.error("upload_image_text 异常", reason=str(e)[:200])
            return False

    async def publish_image_text(self, task) -> bool:
        """基于 Task 模型发布图文。"""
        if not task.media_files:
            self.logger.error("任务缺少图片文件")
            return False

        cookie_ok = await self.verify_cookie_flow(auto_login=False)
        if cookie_ok:
            async with await StealthBrowser.create(
                headless=True
            ) as browser:
                await browser.load_cookies_from_file(self.cookie_file_path)
                async with await browser.new_page() as page:
                    return await self._upload_image_text(
                        page=page,
                        image_paths=task.media_files,
                        title=task.title,
                        content=task.content,
                        tags=task.tags,
                        publish_date=task.publish_date,
                        thumbnail_path=task.thumbnail_path,
                    )

        # cookie 无效，登录并上传
        self.logger.info("cookie 无效，启动登录流程")
        try:
            async with await StealthBrowser.create(
                headless=False, channel=self._browser_channel
            ) as browser:
                page = await browser.new_page()
                await page.goto(self.login_url)
                self.logger.info("等待用户在浏览器内完成登录…")
                if not await self._wait_for_login(page, timeout=120.0):
                    raise RuntimeError("登录超时")
                self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
                await page.context.storage_state(path=self.cookie_file_path)
                self.logger.info("cookie 已保存")
                await page.goto(self._image_text_upload_url)
                await page.wait_for_timeout(3000)
                if await self._check_login_required(page):
                    raise RuntimeError("登录后发布页仍要求登录")
                return await self._upload_image_text(
                    page=page,
                    image_paths=task.media_files,
                    title=task.title,
                    content=task.content,
                    tags=task.tags,
                    publish_date=task.publish_date,
                    thumbnail_path=task.thumbnail_path,
                )
        except Exception as e:
            self.logger.error("登录并上传图文失败", reason=str(e)[:200])
            return False

    # ---------------------------------------------------------------- 视频发布

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
        try:
            import asyncio

            async def _check_success() -> bool:
                cur = page.url
                if re.search(r"/success|published=true|/content/|/manage", cur):
                    return True
                for t in ["发布成功", "笔记已发布", "已发布", "审核中"]:
                    if await page.locator(f'text="{t}"').count() > 0:
                        return True
                return False

            # 1) Ctrl+Enter 快捷键
            await page.keyboard.press("Control+Enter")
            await page.wait_for_timeout(3000)
            if await _check_success():
                self.logger.info("发布成功(快捷键)")
                return True

            # 2) 查找并点击发布按钮
            # 先滚动到底部确保按钮可见
            await page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            await page.wait_for_timeout(300)

            # 优先用 JS click（对 Vue 组件最可靠）
            clicked = await page.evaluate("""
() => {
    const btn = document.querySelector('.publish-page-publish-btn button.ce-btn.bg-red');
    if (btn && btn.offsetParent !== null) {
        btn.scrollIntoView({block: 'center'});
        btn.click();
        return 'js_click';
    }
    return null;
}
""")
            if clicked:
                self.logger.info("已点击发布按钮(JS)", method=clicked)
                await page.wait_for_timeout(3000)
                if await _check_success():
                    self.logger.info("发布成功(JS)")
                    return True
            else:
                # 备选: Playwright locator
                publish_btn = page.locator(
                    '.publish-page-publish-btn button.ce-btn.bg-red'
                ).first
                if await publish_btn.count() > 0 and await publish_btn.is_visible():
                    await publish_btn.scroll_into_view_if_needed()
                    await publish_btn.click(force=True)
                    self.logger.info("已点击发布按钮(locator)")
                    await page.wait_for_timeout(3000)
                    if await _check_success():
                        self.logger.info("发布成功(locator)")
                        return True

            # 3) 等待结果兜底
            for _ in range(10):
                if await _check_success():
                    return True
                await asyncio.sleep(1)

            self.logger.warning("发布结果检测超时", url=page.url)
            return False
        except Exception as e:
            self.logger.error("发布异常", reason=str(e)[:200])
            return False
