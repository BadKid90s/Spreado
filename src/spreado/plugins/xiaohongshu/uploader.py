"""小红书视频上传器。"""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Error, Page

from spreado.core.base_publisher import BasePublisher


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
        """轮询直到视频上传完成：出现标题输入框或预览。"""

        async def check() -> bool:
            # 标题输入框出现 = 上传完成
            if (
                await page.locator("input[placeholder*='填写标题']").count() > 0
                and await page.locator(
                    "input[placeholder*='填写标题']"
                ).first.is_visible()
            ):
                return True
            # 预览区出现
            for sel in [
                "div.upload-content div.preview-new",
                "div.preview-new",
                '[class*="preview"]',
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            # 成功文案
            for txt in ["上传成功", "已上传"]:
                if await page.locator(f"text={txt}").count() > 0:
                    return True
            # 进度条存在 = 仍在传输中
            for sel in [
                ".el-progress-bar",
                '[class*="progress"]',
                '[class*="uploading"]',
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return False
            return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=1.5, desc="upload_complete"
        )

    async def _fill_video_info(
        self,
        page: Page,
        title: str = "",
        content: str = "",
        tags: List[str] = None,
    ) -> bool:
        try:
            # 等待标题输入框出现（视频上传后渲染）
            await page.wait_for_selector(
                "input[placeholder*='填写标题']",
                state="visible",
                timeout=15000,
            )

            # 填写标题
            title_input = page.locator("input[placeholder*='填写标题']")
            if await title_input.count() > 0:
                await title_input.fill(title[:20])

            # 填写正文 — TipTap/ProseMirror contenteditable 编辑器
            if content:
                desc = page.locator("#post-textarea")
                if await desc.count() == 0:
                    desc = page.locator("div.tiptap-container div[contenteditable]")
                if await desc.count() > 0:
                    await desc.click()
                    await page.wait_for_timeout(300)
                    await desc.fill(content)

            # 填写标签 — 通过 TipTap 编辑器输入
            added = 0
            for tag in tags or []:
                clean_tag = tag.lstrip("#")
                try:
                    # 聚焦编辑器末尾
                    await desc.focus()
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(200)
                    # 输入标签
                    await page.keyboard.insert_text(f" #{clean_tag} ")
                    await page.wait_for_timeout(300)
                    await page.keyboard.press("Enter")
                    added += 1
                except Exception as e:
                    self.logger.warning(
                        "标签添加失败", tag=clean_tag, reason=str(e)[:100]
                    )
                await page.wait_for_timeout(200)

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
            # 1) 打开封面编辑弹窗 — UI 已变更为智能推荐封面 + PK封面
            cover_trigger_selectors = [
                ".cover-plugin-preview .cover-image.row",
                ".cover-plugin-preview .cover",
                ".cover-plugin-preview",
                '.publish-page-content-cover [class*="cover"]',
                '[class*="cover-plugin"]',
            ]
            if not await self._click_first_visible(
                page, cover_trigger_selectors, force=True
            ):
                self.logger.error("未找到封面入口")
                return False

            # 等待封面设置弹窗出现
            try:
                await page.wait_for_selector(
                    ".d-modal:has-text('设置封面'), .d-modal:has-text('封面')",
                    state="visible",
                    timeout=10000,
                )
            except Error:
                self.logger.warning("封面弹窗未出现，继续尝试上传")

            # 2) 弹窗内上传自定义封面图片
            upload_input_selectors = [
                '.d-modal input[type="file"][accept*="image"]',
                'input[type="file"][accept*="image"]',
                '.d-modal input[type="file"]',
                'input[type="file"]',
            ]
            if not await self._upload_file_to_first(
                page, upload_input_selectors, thumbnail_path, timeout=10000
            ):
                self.logger.error("未找到封面图片上传 input")
                return False

            await page.wait_for_timeout(2000)

            # 3) 确认封面选择
            if not await self._click_first_visible(
                page,
                [
                    '.d-modal button:has-text("确定")',
                    '.d-modal button:has-text("确认")',
                    'button:has-text("确定")',
                    'button:has-text("确认")',
                ],
                force=True,
            ):
                self.logger.error("未找到确定按钮")
                return False

            # 等待弹窗关闭
            try:
                await page.wait_for_selector(
                    ".d-modal:has-text('设置封面')",
                    state="hidden",
                    timeout=10000,
                )
            except Error:
                pass

            self.logger.info("封面设置完成")
            return True
        except Exception as e:
            self.logger.error("封面设置失败", reason=str(e)[:200])
            return False

    async def _set_schedule_time(self, page: Page, publish_date: datetime) -> bool:
        try:
            publish_date_str = publish_date.strftime("%Y-%m-%d %H:%M")

            # 1) 开启定时发布开关
            switch_container = page.locator(".post-time-switch-container")
            if await switch_container.count() == 0:
                switch_container = page.locator(
                    ".custom-switch-wrapper:has-text('定时发布')"
                )

            # 找到 .d-switch 组件（兼容新旧 UI）
            switch = switch_container.locator(".d-switch").first
            if await switch.count() == 0:
                switch = page.locator(
                    ".custom-switch-wrapper:has-text('定时发布') .d-switch"
                ).first

            if await switch.count() > 0:
                await switch.scroll_into_view_if_needed()
                try:
                    checked = await switch.locator("input").evaluate("el => el.checked")
                except Error:
                    checked = False
                if not checked:
                    await switch.locator(".d-switch-simulator").click(force=True)
                    await page.wait_for_timeout(800)
            else:
                self.logger.warning("未找到定时发布开关")

            # 2) 等待日期选择器渲染
            try:
                await page.wait_for_selector(
                    ".date-picker-container, .d-datepicker, [class*='datepicker']",
                    state="visible",
                    timeout=5000,
                )
            except Error:
                self.logger.warning("日期选择器未出现")

            # 3) 填入发布时间
            datetime_selectors = [
                ".date-picker-container .d-text",
                ".d-datepicker-input-filter input",
                ".d-datepicker-input-filter",
                "input[placeholder*='时间']",
                "input[placeholder*='日期']",
            ]
            datetime_elem = None
            for sel in datetime_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    datetime_elem = loc
                    break

            if datetime_elem is None:
                self.logger.error("未找到日期输入框")
                return False

            await datetime_elem.wait_for(state="visible", timeout=5000)
            # 判断是否为 INPUT 元素
            is_input = await datetime_elem.evaluate("el => el.tagName === 'INPUT'")
            if not is_input:
                datetime_elem = datetime_elem.locator("input").first
                if await datetime_elem.count() == 0:
                    self.logger.error("日期输入框内无 input 元素")
                    return False

            await datetime_elem.click(force=True)
            await datetime_elem.fill(publish_date_str)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            self.logger.info("定时发布时间设置完成")
            return True
        except Exception as e:
            self.logger.error("定时发布设置失败", reason=str(e)[:200])
            return False

    async def _publish_video(self, page: Page) -> bool:
        try:
            import asyncio

            # 检测发布成功
            async def _check_publish_success() -> bool:
                cur = page.url
                if re.search(r"/success|published=true|/content/|/manage", cur):
                    return True
                for t in ["发布成功", "笔记已发布", "已发布", "审核中"]:
                    if await page.locator(f'text="{t}"').count() > 0:
                        return True
                return False

            # 先滚动到底部，触发 Vue 懒加载渲染发布按钮
            await page.evaluate("""() => {
                const containers = document.querySelectorAll(
                    '.publish-page-content, .publish-page-container, .publish-vue-container, .outarea'
                );
                for (const c of containers) { c.scrollTop = c.scrollHeight; }
                window.scrollTo(0, document.body.scrollHeight);
            }""")
            await page.wait_for_timeout(500)

            # 1) 尝试键盘快捷键 Ctrl+Enter（最可靠）
            self.logger.info("尝试 Ctrl+Enter 发布...")
            await page.keyboard.press("Control+Enter")
            await page.wait_for_timeout(3000)
            if await _check_publish_success():
                self.logger.info("发布成功(快捷键)")
                return True

            # 2) 检查确认弹窗（发布时常有二次确认）
            for t in ["确认发布", "确认", "发布"]:
                btn = page.locator(f'button:has-text("{t}")').last
                if await btn.count() > 0 and await btn.is_visible():
                    self.logger.info("发现确认弹窗按钮", text=t)
                    await btn.click(force=True)
                    await page.wait_for_timeout(3000)
                    if await _check_publish_success():
                        self.logger.info("发布成功(确认弹窗)")
                        return True
                    break

            # 3) 查找并点击发布按钮（Vue 动态渲染）
            self.logger.info("查找发布按钮...")
            publish_btn_selectors = [
                'button:has-text("发布"):visible',
                '[class*="publish-btn"] button:visible',
                'button:has-text("发布笔记"):visible',
            ]
            for sel in publish_btn_selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.scroll_into_view_if_needed()
                        await loc.click(timeout=5000)
                        self.logger.info("已点击发布按钮", selector=sel)
                        await page.wait_for_timeout(3000)
                        if await _check_publish_success():
                            self.logger.info("发布成功(按钮点击)")
                            return True
                        break
                except Exception:
                    continue

            # 4) 等待结果（兜底）
            success = False
            start = time.monotonic()
            while time.monotonic() - start < 15:
                if await _check_publish_success():
                    success = True
                    break
                await asyncio.sleep(1)

            if not success:
                self.logger.warning("发布结果检测超时", url=page.url)
            return success
        except Exception as e:
            self.logger.error("发布异常", reason=str(e)[:200])
            return False
