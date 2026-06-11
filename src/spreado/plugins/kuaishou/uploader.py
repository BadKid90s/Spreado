from datetime import datetime
from pathlib import Path
from typing import List, Optional
import re

from playwright.async_api import Page, Error

from spreado.core.base_publisher import BasePublisher


class KuaiShouUploader(BasePublisher):
    """
    快手视频上传器
    """

    @property
    def platform_name(self) -> str:
        return "kuaishou"

    @property
    def display_name(self) -> str:
        return "快手"

    @property
    def login_url(self) -> str:
        return "https://passport.kuaishou.com/pc/account/login"

    @property
    def publish_url(self) -> str:
        return "https://cp.kuaishou.com/article/publish/video"

    @property
    def _login_selectors(self) -> List[str]:
        return [
            'text="立即登录"',
            ".platform-switch-tips",
            "button.pl-btn.pl-btn-primary",
            ".login-btn",
        ]

    @property
    def _authed_selectors(self) -> List[str]:
        return ["#work-description-edit", 'text="发布作品"']

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
                    try:
                        await page.wait_for_url(self.publish_url, timeout=5000)
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

    async def _upload_video_file(self, page: Page, file_path: str | Path) -> bool:
        try:
            # 优先尝试直接注入（更可靠）
            file_input_selectors = [
                "input[type='file'][accept*='video']",
                "input[type='file']",
            ]
            if await self._upload_file_to_first(
                page, file_input_selectors, file_path, timeout=10000
            ):
                self.logger.info("视频文件已注入")
                return True

            # 备选：通过上传按钮触发 file chooser
            btn_selectors = [
                "button[class^='_upload-btn']",
                "button[class*='upload-btn']",
                ".ant-upload button",
            ]
            for sel in btn_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await btn.click()
                        await (await fc_info.value).set_files(file_path)
                        self.logger.info("视频文件已通过 file chooser 注入")
                        return True
                except Error:
                    continue

            self.logger.error("未找到上传入口")
            return False
        except Exception as e:
            self.logger.error("视频文件注入失败", reason=str(e)[:200])
            return False

    async def _wait_for_upload_complete(self, page: Page) -> bool:
        complete_selectors = [
            "#work-description-edit",
            "div.upload-success",
        ]

        async def check() -> bool:
            for sel in complete_selectors:
                el = page.locator(sel)
                if await el.count() > 0 and await el.first.is_visible():
                    return True
            return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=2.0, desc="upload_complete"
        )

    async def _fill_video_info(
        self, page: Page, title: str = "", content: str = "", tags: List[str] = None,
    ) -> bool:
        try:
            editor = page.locator("#work-description-edit")
            await editor.click()
            await page.wait_for_timeout(300)

            # 输入标题和正文
            text_content = f"{title}\n{content}\n" if content else f"{title}\n"
            await page.keyboard.insert_text(text_content)

            # 输入标签
            added = 0
            for tag in tags or []:
                topic = tag.lstrip("#")
                try:
                    await page.keyboard.insert_text(f"#{topic}")
                    await page.wait_for_timeout(300)
                    await page.keyboard.press("Enter")
                    added += 1
                except Exception as e:
                    self.logger.warning("标签添加失败", tag=topic, reason=str(e)[:100])
                await page.wait_for_timeout(200)

            self.logger.info("标题与标签已填充", added=added, total=len(tags or []))
            return True
        except Exception as e:
            self.logger.error("填写视频信息失败", reason=str(e)[:200])
            return False

    async def _set_thumbnail(
        self, page: Page, thumbnail_path: Optional[str | Path],
    ) -> bool:
        if not thumbnail_path:
            self.logger.info("未指定封面，跳过")
            return True
        if not Path(thumbnail_path).exists():
            self.logger.warning("封面文件不存在，跳过", path=str(thumbnail_path))
            return True

        try:
            # 1) 点击"封面设置"打开弹窗
            cover_btn = page.get_by_text("封面设置").last
            await cover_btn.wait_for(state="visible", timeout=10000)
            await cover_btn.click()

            # 2) 等待弹窗，点击"上传封面"
            await page.wait_for_selector(
                "div.ant-modal-body", timeout=10000, state="visible"
            )
            upload_btn = page.get_by_text("上传封面")
            await upload_btn.wait_for(state="visible", timeout=5000)
            await upload_btn.click()

            # 3) 注入封面图片
            if not await self._upload_file_to_first(
                page,
                ["div[class*='upload'] input[type='file']", "input[type='file'][accept*='image']"],
                thumbnail_path,
                timeout=10000,
            ):
                self.logger.error("未找到封面图片上传 input")
                return False

            await page.wait_for_timeout(1500)

            # 4) 确认
            confirm_btn = page.get_by_role("button", name="确认")
            await confirm_btn.wait_for(state="visible", timeout=5000)
            await confirm_btn.click()

            await page.wait_for_timeout(1000)
            self.logger.info("封面设置完成")
            return True
        except Exception as e:
            self.logger.error("封面设置失败", reason=str(e)[:200])
            return False

    async def _set_schedule_time(self, page: Page, publish_date: datetime) -> bool:
        try:
            time_str = publish_date.strftime("%Y-%m-%d %H:%M:%S")
            # 点击"定时发布" radio（第二个 .ant-radio-input）
            await page.locator("label:text('发布时间')").locator(
                "xpath=following-sibling::div"
            ).locator(".ant-radio-input").nth(1).click()

            await page.wait_for_selector(
                'div.ant-picker-input input[placeholder="选择日期时间"]',
                state="visible",
                timeout=5000,
            )
            inp = page.locator('div.ant-picker-input input[placeholder="选择日期时间"]')
            await inp.click()
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.insert_text(time_str)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            self.logger.info("定时发布时间设置完成")
            return True
        except Exception as e:
            self.logger.error("定时发布设置失败", reason=str(e)[:200])
            return False

    async def _publish_video(self, page: Page) -> bool:
        success_pattern = re.compile(r"/article/manage/video\?status=2&from=publish")
        try:
            # 点击"发布"按钮
            publish_btn = page.get_by_text("发布", exact=True)
            if await publish_btn.count() > 0:
                await publish_btn.click()
                await page.wait_for_timeout(500)

            # 处理"确认发布"弹窗
            confirm_btn = page.get_by_text("确认发布")
            if await confirm_btn.count() > 0:
                return await self._click_and_wait_for_url(
                    page, confirm_btn, success_pattern, timeout=15000
                )

            # 兜底：检查是否已跳转
            if success_pattern.search(page.url):
                return True

            self.logger.error("未找到确认发布按钮")
            return False
        except Error as e:
            self.logger.error("发布失败", reason=str(e)[:200])
            return False
