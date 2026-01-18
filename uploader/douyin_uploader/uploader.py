from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page
import asyncio

from utils.base_social_media import set_init_script
from utils.log import create_logger
from uploader.base_uploader import BaseUploader

douyin_logger = create_logger("douyin", "logs/douyin.log")


class DouYinUploader(BaseUploader):
    """
    抖音视频上传器
    """

    @property
    def platform_name(self) -> str:
        return "douyin"

    @property
    def login_url(self) -> str:
        return "https://creator.douyin.com/"

    @property
    def upload_url(self) -> str:
        return "https://creator.douyin.com/creator-micro/content/upload"

    @property
    def success_url_pattern(self) -> str:
        return "https://creator.douyin.com/creator-micro/content/manage"

    @property
    def login_selectors(self) -> List[str]:
        return [
            'text="手机号登录"',
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
        上传视频到抖音

        Args:
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径
            **kwargs: 其他参数（如location, product_link, product_title等）

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
            await self._wait_for_upload_complete(page)

            await self._fill_video_info(page, title, content, tags)
            await self._set_thumbnail(page, thumbnail_path)
            await self._set_third_party_platforms(page)

            if publish_date:
                await self._set_schedule_time(page, publish_date)

            await self._handle_auto_video_cover(page)

            location = kwargs.get("location")
            if location:
                await self._set_location(page, location)

            product_link = kwargs.get("product_link")
            product_title = kwargs.get("product_title")
            if product_link and product_title:
                await self._set_product_link(page, product_link, product_title)

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
        await page.locator("div[class^='container'] input").set_input_files(file_path)

    async def _wait_for_upload_complete(self, page: Page):
        """
        等待视频上传完成

        Args:
            page: 页面实例
        """
        while True:
            try:
                await page.locator("div[class*='preview-button-']:has(div:text('重新上传'))").wait_for(timeout=3000)
                self.logger.info("视频上传完成...")
                break
            except Exception:
                self.logger.info("等待视频上传完成...")
                await page.wait_for_timeout(500)

    async def _fill_video_info(self, page: Page, title: str, content: str, tags: List[str]):
        """
        填写视频信息

        Args:
            page: 页面实例
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
        """
        await page.wait_for_selector("input[placeholder*='填写作品标题'], .notranslate", state='visible', timeout=5000)
        self.logger.info("[-] 正在填充标题和话题...")

        title_container = page.locator("input[placeholder*='填写作品标题']")
        if await title_container.count():
            await title_container.fill(title[:30])
        else:
            title_container = page.get_by_text('作品标题').locator("..").locator("xpath=following-sibling::div[1]").locator("input")
            if await title_container.count():
                await title_container.fill(title[:30])
            else:
                titlecontainer = page.locator(".notranslate")
                await titlecontainer.click()
                await page.keyboard.press("Backspace")
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.keyboard.type(title)
                await page.keyboard.press("Enter")

        css_selector = ".zone-container"
        await page.type(css_selector, content)

        for tag in tags:
            if not tag.startswith("#"):
                await page.type(css_selector, "#" + tag)
            else:
                await page.type(css_selector, tag)
            await page.press(css_selector, "Space")

        self.logger.info(f"总共添加{len(tags)}个话题")

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
        await page.click('text="选择封面"')
        await page.wait_for_selector("div.dy-creator-content-modal")
        await page.click('text="设置竖封面"')
        await page.wait_for_timeout(2000)
        await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
        await page.wait_for_timeout(2000)
        await page.locator("button:visible:has-text('完成')").click()
        self.logger.info("[+] 视频封面设置完成！")
        await page.wait_for_selector("div.extractFooter", state='detached')

    async def _set_schedule_time(self, page: Page, publish_date: datetime):
        """
        设置定时发布时间

        Args:
            page: 页面实例
            publish_date: 发布时间
        """
        label_element = page.locator("[class^='radio']:has-text('定时发布')")
        await label_element.click()
        await page.wait_for_selector('.semi-input[placeholder="日期和时间"]', state='visible', timeout=5000)
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        await page.locator('.semi-input[placeholder="日期和时间"]').click()
        await page.wait_for_selector('.semi-input[placeholder="日期和时间"]:focus', state='visible', timeout=3000)
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)

    async def _set_third_party_platforms(self, page: Page):
        """
        设置第三方平台同步

        Args:
            page: 页面实例
        """
        third_part_element = '[class^="info"] > [class^="first-part"] div div.semi-switch'
        if await page.locator(third_part_element).count():
            if 'semi-switch-checked' not in await page.eval_on_selector(third_part_element, 'div => div.className'):
                await page.locator(third_part_element).locator('input.semi-switch-native-control').click()

    async def _handle_auto_video_cover(self, page: Page):
        """
        处理必须设置封面的情况

        Args:
            page: 页面实例
        """
        if await page.get_by_text("请设置封面后再发布").first.is_visible():
            self.logger.info("[-] 检测到需要设置封面提示...")
            recommend_cover = page.locator('[class^="recommendCover-"]').first

            if await recommend_cover.count():
                self.logger.info("[-] 正在选择第一个推荐封面...")
                try:
                    await recommend_cover.click()
                    await page.wait_for_timeout(500)

                    if await page.get_by_text("是否确认应用此封面？").first.is_visible():
                        self.logger.info("[-] 检测到确认弹窗: 是否确认应用此封面？")
                        await page.get_by_role("button", name="确定").click()
                        self.logger.info("[-] 已点击确认应用封面")
                        await page.wait_for_timeout(500)

                    self.logger.info("[-] 已完成封面选择流程")
                except Exception as e:
                    self.logger.error(f"[-] 选择封面失败: {e}")

    async def _set_location(self, page: Page, location: str):
        """
        设置地理位置

        Args:
            page: 页面实例
            location: 地理位置
        """
        await page.locator('div.semi-select span:has-text("输入地理位置")').click()
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(2000)
        await page.keyboard.type(location)
        await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
        await page.locator('div[role="listbox"] [role="option"]').first.click()

    async def _set_product_link(self, page: Page, product_link: str, product_title: str):
        """
        设置商品链接

        Args:
            page: 页面实例
            product_link: 商品链接
            product_title: 商品标题
        """
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector('text=添加标签', timeout=10000)
            dropdown = page.get_by_text('添加标签').locator("..").locator("..").locator("..").locator(".semi-select").first
            if not await dropdown.count():
                self.logger.error("[-] 未找到标签下拉框")
                return False

            self.logger.debug("[-] 找到标签下拉框，准备选择'购物车'")
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            await page.locator('[role="option"]:has-text("购物车")').click()
            self.logger.debug("[+] 成功选择'购物车'")

            await page.wait_for_selector('input[placeholder="粘贴商品链接"]', timeout=5000)
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            self.logger.debug(f"[+] 已输入商品链接: {product_link}")

            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute('class')
            if 'disable' in button_class:
                self.logger.error("[-] '添加链接'按钮不可用")
                return False

            await add_button.click()
            self.logger.debug("[+] 成功点击'添加链接'按钮")
            await page.wait_for_timeout(2000)

            error_modal = page.locator('text=未搜索到对应商品')
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                self.logger.error("[-] 商品链接无效")
                return False

            if not await self._handle_product_dialog(page, product_title):
                return False

            self.logger.debug("[+] 成功设置商品链接")
            return True

        except Exception as e:
            self.logger.error(f"[-] 设置商品链接时出错: {str(e)}")
            return False

    async def _handle_product_dialog(self, page: Page, product_title: str) -> bool:
        """
        处理商品编辑弹窗

        Args:
            page: 页面实例
            product_title: 商品标题

        Returns:
            是否成功处理
        """
        await page.wait_for_timeout(2000)
        await page.wait_for_selector('input[placeholder="请输入商品短标题"]', timeout=10000)
        short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
        if not await short_title_input.count():
            self.logger.error("[-] 未找到商品短标题输入框")
            return False

        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if 'disabled' not in await finish_button.get_attribute('class'):
            await finish_button.click()
            self.logger.debug("[+] 成功点击'完成编辑'按钮")
            await page.wait_for_selector('.semi-modal-content', state='hidden', timeout=5000)
            return True
        else:
            self.logger.error("[-] '完成编辑'按钮处于禁用状态，尝试直接关闭对话框")
            cancel_button = page.locator('button:has-text("取消")')
            if await cancel_button.count():
                await cancel_button.click()
            else:
                close_button = page.locator('.semi-modal-close')
                await close_button.click()

            await page.wait_for_selector('.semi-modal-content', state='hidden', timeout=5000)
            return False

    async def _publish_video(self, page: Page):
        """
        发布视频

        Args:
            page: 页面实例
        """
        publish_button = page.get_by_role('button', name="发布", exact=True)
        if await publish_button.count():
            await publish_button.click()
        await page.wait_for_url(self.success_url_pattern + "**", timeout=3000)
