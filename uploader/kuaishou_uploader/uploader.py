from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page
import asyncio

from utils.base_social_media import set_init_script
from utils.log import create_logger
from uploader.base_uploader import BaseUploader

kuaishou_logger = create_logger("kuaishou", "logs/kuaishou.log")


class KuaiShouUploader(BaseUploader):
    """
    快手视频上传器
    """

    @property
    def platform_name(self) -> str:
        return "kuaishou"

    @property
    def login_url(self) -> str:
        return "https://cp.kuaishou.com"

    @property
    def upload_url(self) -> str:
        return "https://cp.kuaishou.com/article/publish/video"

    @property
    def success_url_pattern(self) -> str:
        return "https://cp.kuaishou.com/article/manage/video?status=2&from=publish"

    @property
    def login_selectors(self) -> List[str]:
        return [
            'text="立即登录"',
            'text="扫码登录"',
            'text="登录"',
            '.login-btn'
        ]

    async def upload_video(
        self,
        file_path: str | Path,
        title: str,
        content: str,
        tags: List[str],
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
        **kwargs
    ) -> bool:
        """
        上传视频到快手

        Args:
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径
            **kwargs: 其他参数

        Returns:
            上传是否成功
        """
        try:
            browser = await self._init_browser()
            context = await self._init_context(browser, use_cookie=True)
            page = await self._init_page(context)

            await page.goto(self.upload_url)
            self.logger.info("[-] 正在打开上传页面...")
            await page.wait_for_url(self.upload_url)

            self.logger.info(f"[+] 正在上传视频: {title}")
            await self._upload_video_file(page, file_path)
            await self._wait_for_upload_complete(page)

            await self._fill_video_info(page, title, content, tags)
            await self._set_thumbnail(page, thumbnail_path)

            if publish_date:
                await self._set_schedule_time(page, publish_date)

            await self._publish_video(page)
            self.logger.success("[-] 视频发布成功")

            return True

        except Exception as e:
            self.logger.error(f"[!] 上传视频时出错: {e}")
            return False

    async def _upload_video_file(self, page: Page, file_path: str | Path):
        """
        上传视频文件

        Args:
            page: 页面实例
            file_path: 视频文件路径
        """
        upload_button = page.locator("button[class^='_upload-btn']")
        await upload_button.wait_for(state='visible')

        async with page.expect_file_chooser() as fc_info:
            await upload_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(file_path)

        await page.wait_for_timeout(300)

        new_feature_button = page.get_by_role("button", name="Skip")
        if await new_feature_button.count() > 0:
            await new_feature_button.click()

    async def _wait_for_upload_complete(self, page: Page):
        """
        等待视频上传完成

        Args:
            page: 页面实例
        """
        max_retries = 60
        retry_count = 0

        while retry_count < max_retries:
            try:
                number = await page.locator("text=上传中").count()

                if number == 0:
                    self.logger.success("视频上传完毕")
                    break
                else:
                    if retry_count % 5 == 0:
                        self.logger.info("正在上传视频中...")
                    await page.wait_for_timeout(1000)
            except Exception as e:
                self.logger.error(f"检查上传状态时发生错误: {e}")
                await page.wait_for_timeout(1000)
            retry_count += 1

        if retry_count == max_retries:
            self.logger.warning("超过最大重试次数，视频上传可能未完成。")

    async def _fill_video_info(self, page: Page, title: str, content: str, tags: List[str]):
        """
        填写视频信息

        Args:
            page: 页面实例
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
        """
        await page.locator("#work-description-edit").click()

        text_content = f"{title}\n{content}\n"
        await page.keyboard.type(text_content)

        for tag in tags:
            topic_name = tag.lstrip("#")

            await page.keyboard.down("Shift")
            await page.keyboard.press("Digit3")
            await page.keyboard.up("Shift")

            await page.wait_for_timeout(300)
            await page.keyboard.type(topic_name, delay=100)
            await page.wait_for_timeout(500)
            await page.keyboard.press("Enter")

        self.logger.info(f"成功添加内容和hashtag: {len(tags)}")

    async def _set_thumbnail(self, page: Page, thumbnail_path: Optional[str | Path]):
        """
        设置视频封面

        Args:
            page: 页面实例
            thumbnail_path: 封面图片路径
        """
        if not thumbnail_path:
            return

        self.logger.info("[-] 正在设置视频封面...")
        await page.get_by_text("封面设置").nth(1).click()
        await page.wait_for_selector("div.ant-modal-body:has(*:text('上传封面'))")
        await page.wait_for_timeout(300)
        await page.get_by_text("上传封面").click()

        file_input = page.locator("div[class*='upload'] input[type='file']")
        await file_input.set_input_files(thumbnail_path)

        await page.get_by_role("button", name="确认").click()

        self.logger.info("[+] 视频封面设置完成！")
        await page.wait_for_selector("div.ant-modal", state='detached')

    async def _set_schedule_time(self, page: Page, publish_date: datetime):
        """
        设置定时发布时间

        Args:
            page: 页面实例
            publish_date: 发布时间
        """
        self.logger.info("click schedule")
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M:%S")
        await page.locator("label:text('发布时间')").locator('xpath=following-sibling::div').locator('.ant-radio-input').nth(1).click()
        await page.wait_for_selector('div.ant-picker-input input[placeholder="选择日期时间"]', state='visible', timeout=5000)
        
        await page.locator('div.ant-picker-input input[placeholder="选择日期时间"]').click()
        await page.wait_for_selector('div.ant-picker-input input[placeholder="选择日期时间"]:focus', state='visible', timeout=3000)
        
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)

    async def _publish_video(self, page: Page):
        """
        发布视频

        Args:
            page: 页面实例
        """
        while True:
            try:
                publish_button = page.get_by_text("发布", exact=True)
                if await publish_button.count() > 0:
                    await publish_button.click()

                await page.wait_for_timeout(500)
                confirm_button = page.get_by_text("确认发布")
                if await confirm_button.count() > 0:
                    await confirm_button.click()

                await page.wait_for_url(self.success_url_pattern, timeout=5000)
                self.logger.success("视频发布成功")
                break
            except Exception as e:
                self.logger.info(f"视频正在发布中... 错误: {e}")
                await page.screenshot(full_page=True)
                await page.wait_for_timeout(500)
