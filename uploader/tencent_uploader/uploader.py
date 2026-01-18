from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page
import asyncio

from utils.base_social_media import set_init_script
from utils.log import create_logger
from uploader.base_uploader import BaseUploader
from .constants import TencentZoneTypes

tencent_logger = create_logger("tencent", "logs/tencent.log")


class TencentUploader(BaseUploader):
    """
    腾讯视频上传器
    """

    @property
    def platform_name(self) -> str:
        return "tencent"

    @property
    def login_url(self) -> str:
        return "https://channels.weixin.qq.com"

    @property
    def upload_url(self) -> str:
        return "https://channels.weixin.qq.com/platform/post/create"

    @property
    def success_url_pattern(self) -> str:
        return "https://channels.weixin.qq.com/platform/post/list"

    @property
    def login_selectors(self) -> List[str]:
        return [
            'div.title-name:has-text("微信小店")',
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
        上传视频到腾讯视频

        Args:
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径
            **kwargs: 其他参数（如category, is_draft等）

        Returns:
            上传是否成功
        """
        try:
            browser = await self._init_browser()
            context = await self._init_context(browser, use_cookie=True)
            page = await self._init_page(context)

            await page.goto(self.upload_url)
            self.logger.info(f"[-] 正在打开上传页面...")
            await page.wait_for_url(self.upload_url)

            self.logger.info(f"[+] 正在上传视频: {title}")
            await self._upload_video_file(page, file_path)

            await self._fill_video_info(page, title, content, tags)
            await self._set_thumbnail(page, thumbnail_path)
            await self._add_collection(page)
            await self._add_original(page, kwargs.get("category"))

            await self._wait_for_upload_complete(page)

            if publish_date:
                await self._set_schedule_time(page, publish_date)

            await self._add_short_title(page)

            is_draft = kwargs.get("is_draft", False)
            await self._publish_video(page, is_draft)
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
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(file_path)

    async def _fill_video_info(self, page: Page, title: str, content: str, tags: List[str]):
        """
        填写视频信息

        Args:
            page: 页面实例
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
        """
        await page.locator("div.input-editor").click()
        await page.keyboard.type(title)
        await page.keyboard.press("Enter")

        await page.keyboard.type(content)
        await page.keyboard.press("Enter")

        for tag in tags:
            if not tag.startswith("#"):
                await page.keyboard.type("#" + tag)
            else:
                await page.keyboard.type(tag)
            await page.keyboard.press("Space")

        self.logger.info(f"成功添加hashtag: {len(tags)}")

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
        await page.click('text="个人主页卡片"')
        await page.wait_for_selector("div.weui-desktop-dialog:has(*:text('编辑个人主页卡片'))")
        await page.locator('div:has-text("上传封面"):visible').first.click()
        await page.wait_for_timeout(1000)
        await page.locator('div.single-cover-uploader-wrap input[type="file"]').set_input_files(thumbnail_path)
        await page.wait_for_timeout(1000)
        await page.locator("button:visible:has-text('确认')").click()
        self.logger.info("[+] 视频封面设置完成！")
        await page.wait_for_selector("div.extractFooter", state='detached')

    async def _add_collection(self, page: Page):
        """
        添加到合集

        Args:
            page: 页面实例
        """
        collection_elements = page.get_by_text("添加到合集").locator("xpath=following-sibling::div").locator('.option-list-wrap > div')
        if await collection_elements.count() > 1:
            await page.get_by_text("添加到合集").locator("xpath=following-sibling::div").click()
            await collection_elements.first.click()

    async def _add_original(self, page: Page, category: Optional[str] = None):
        """
        添加原创声明

        Args:
            page: 页面实例
            category: 原创类型
        """
        if await page.get_by_label("视频为原创").count():
            await page.get_by_label("视频为原创").check()

        label_locator = await page.locator('label:has-text("我已阅读并同意 《视频号原创声明使用条款》")').is_visible()
        if label_locator:
            await page.get_by_label("我已阅读并同意 《视频号原创声明使用条款》").check()
            await page.get_by_role("button", name="声明原创").click()

        if await page.locator('div.label span:has-text("声明原创")').count() and category:
            if not await page.locator('div.declare-original-checkbox input.ant-checkbox-input').is_disabled():
                await page.locator('div.declare-original-checkbox input.ant-checkbox-input').click()
                if not await page.locator('div.declare-original-dialog label.ant-checkbox-wrapper.ant-checkbox-wrapper-checked:visible').count():
                    await page.locator('div.declare-original-dialog input.ant-checkbox-input:visible').click()

            if await page.locator('div.original-type-form > div.form-label:has-text("原创类型"):visible').count():
                await page.locator('div.form-content:visible').click()
                await page.locator(f'div.form-content:visible ul.weui-desktop-dropdown__list li.weui-desktop-dropdown__list-ele:has-text("{category}")').first.click()
                await page.wait_for_timeout(1000)

            if await page.locator('button:has-text("声明原创"):visible').count():
                await page.locator('button:has-text("声明原创"):visible').click()

    async def _wait_for_upload_complete(self, page: Page):
        """
        等待视频上传完成

        Args:
            page: 页面实例
        """
        while True:
            try:
                if "weui-desktop-btn_disabled" not in await page.get_by_role("button", name="发表").get_attribute('class'):
                    self.logger.info("[-] 视频上传完毕")
                    break
                else:
                    self.logger.info("[-] 正在上传视频中...")
                    await page.wait_for_timeout(1000)

                    if await page.locator('div.status-msg.error').count() and await page.locator('div.media-status-content div.tag-inner:has-text("删除")').count():
                        self.logger.error("[-] 发现上传出错了...准备重试")
                        await self._handle_upload_error(page)
            except:
                self.logger.info("[-] 正在上传视频中...")
                await page.wait_for_timeout(1000)

    async def _handle_upload_error(self, page: Page):
        """
        处理上传错误

        Args:
            page: 页面实例
        """
        self.logger.info("视频出错了，重新上传中")
        await page.locator('div.media-status-content div.tag-inner:has-text("删除")').click()
        await page.get_by_role('button', name="删除", exact=True).click()
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(self.file_path)

    async def _set_schedule_time(self, page: Page, publish_date: datetime):
        """
        设置定时发布时间

        Args:
            page: 页面实例
            publish_date: 发布时间
        """
        label_element = page.locator("label").filter(has_text="定时").nth(1)
        await label_element.click()

        await page.click('input[placeholder="请选择发表时间"]')

        str_month = str(publish_date.month) if publish_date.month > 9 else "0" + str(publish_date.month)
        current_month = str_month + "月"
        page_month = await page.inner_text('span.weui-desktop-picker__panel__label:has-text("月")')

        if page_month != current_month:
            await page.click('button.weui-desktop-btn__icon__right')

        elements = await page.query_selector_all('table.weui-desktop-picker__table a')

        for element in elements:
            if 'weui-desktop-picker__disabled' in await element.evaluate('el => el.className'):
                continue
            text = await element.inner_text()
            if text.strip() == str(publish_date.day):
                await element.click()
                break

        await page.click('input[placeholder="请选择时间"]')
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date.hour))
        await page.locator("div.input-editor").click()

    async def _add_short_title(self, page: Page):
        """
        添加短标题

        Args:
            page: 页面实例
        """
        short_title_element = page.get_by_text("短标题", exact=True).locator("..").locator("xpath=following-sibling::div").locator('span input[type="text"]')
        if await short_title_element.count():
            short_title = self._format_str_for_short_title(self.title)
            await short_title_element.fill(short_title)

    def _format_str_for_short_title(self, origin_title: str) -> str:
        """
        格式化短标题

        Args:
            origin_title: 原始标题

        Returns:
            格式化后的短标题
        """
        allowed_special_chars = "《》“”:+?%°"
        filtered_chars = [char if char.isalnum() or char in allowed_special_chars else ' ' if char == ',' else '' for char in origin_title]
        formatted_string = ''.join(filtered_chars)

        if len(formatted_string) > 16:
            formatted_string = formatted_string[:16]
        elif len(formatted_string) < 6:
            formatted_string += ' ' * (6 - len(formatted_string))

        return formatted_string

    async def _publish_video(self, page: Page, is_draft: bool = False):
        """
        发布视频

        Args:
            page: 页面实例
            is_draft: 是否保存为草稿
        """
        while True:
            try:
                if is_draft:
                    draft_button = page.locator('div.form-btns button:has-text("保存草稿")')
                    if await draft_button.count():
                        await draft_button.click()
                    await page.wait_for_url("**/post/list**", timeout=5000)
                    self.logger.success("[-] 视频草稿保存成功")
                else:
                    publish_button = page.locator('div.form-btns button:has-text("发表")')
                    if await publish_button.count():
                        await publish_button.click()
                    await page.wait_for_url(self.success_url_pattern, timeout=5000)
                    self.logger.success("[-] 视频发布成功")
                break
            except Exception as e:
                current_url = page.url
                if is_draft:
                    if "post/list" in current_url or "draft" in current_url:
                        self.logger.success("[-] 视频草稿保存成功")
                        break
                else:
                    if self.success_url_pattern in current_url:
                        self.logger.success("[-] 视频发布成功")
                        break
                self.logger.exception(f"[-] Exception: {e}")
                self.logger.info("[-] 视频正在发布中...")
                await page.wait_for_timeout(300)
