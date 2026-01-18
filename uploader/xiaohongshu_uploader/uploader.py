from datetime import datetime
from pathlib import Path
from typing import List, Optional
import time

from playwright.async_api import Page
import asyncio

from utils.base_social_media import set_init_script
from utils.log import create_logger
from uploader.base_uploader import BaseUploader

xiaohongshu_logger = create_logger("xiaohongshu", "logs/xiaohongshu.log")


class XiaoHongShuUploader(BaseUploader):
    """
    小红书视频上传器
    """

    @property
    def platform_name(self) -> str:
        return "xiaohongshu"

    @property
    def login_url(self) -> str:
        return "https://creator.xiaohongshu.com/"

    @property
    def upload_url(self) -> str:
        return "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video"

    @property
    def success_url_pattern(self) -> str:
        return "https://creator.xiaohongshu.com/publish/success"

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
        上传视频到小红书

        Args:
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径
            **kwargs: 其他参数（如location等）

        Returns:
            上传是否成功
        """
        start_time = time.time()
        self.logger.debug(f"[DEBUG] upload_video 开始执行: {start_time}")
        
        try:
            browser = await self._init_browser()
            self.logger.debug(f"[DEBUG] 浏览器初始化完成: {time.time() - start_time:.2f}秒")
            
            context = await self._init_context(browser, use_cookie=True)
            self.logger.debug(f"[DEBUG] 上下文初始化完成: {time.time() - start_time:.2f}秒")
            
            page = await self._init_page(context)
            self.logger.debug(f"[DEBUG] 页面初始化完成: {time.time() - start_time:.2f}秒")

            self.logger.info(f"[-] 正在打开上传页面...")
            await page.goto(self.upload_url)
            try:
                await page.wait_for_url(self.upload_url, timeout=5000)
            except Exception:
                pass
            self.logger.debug(f"[DEBUG] 页面导航完成: {time.time() - start_time:.2f}秒")

            self.logger.info(f"[+] 正在上传视频: {title}")
            upload_start = time.time()
            await self._upload_video_file(page, file_path)
            await self._wait_for_upload_complete(page)
            self.logger.debug(f"[DEBUG] 视频上传完成: {time.time() - upload_start:.2f}秒")

            fill_start = time.time()
            await self._fill_video_info(page, title, content, tags)
            self.logger.debug(f"[DEBUG] 视频信息填充完成: {time.time() - fill_start:.2f}秒")

            thumb_start = time.time()
            await self._set_thumbnail(page, thumbnail_path)
            self.logger.debug(f"[DEBUG] 封面设置完成: {time.time() - thumb_start:.2f}秒")

            if publish_date:
                schedule_start = time.time()
                await self._set_schedule_time(page, publish_date)
                self.logger.debug(f"[DEBUG] 定时发布设置完成: {time.time() - schedule_start:.2f}秒")

            location = kwargs.get("location")
            if location:
                await self._set_location(page, location)

            publish_start = time.time()
            await self._publish_video(page)
            self.logger.debug(f"[DEBUG] 视频发布完成: {time.time() - publish_start:.2f}秒")
            
            total_time = time.time() - start_time
            self.logger.info(f"[DEBUG] upload_video 总耗时: {total_time:.2f}秒")
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
        await page.locator("div[class^='upload-content'] input[class='upload-input']").set_input_files(file_path)

    async def _wait_for_upload_complete(self, page: Page):
        """
        等待视频上传完成

        Args:
            page: 页面实例
        """
        while True:
            try:
                upload_input = await page.wait_for_selector('input.upload-input', timeout=3000)
                preview_new = await upload_input.query_selector('xpath=following-sibling::div[contains(@class, "preview-new")]')
                if preview_new:
                    stage_elements = await preview_new.query_selector_all('div.stage')
                    upload_success = False
                    for stage in stage_elements:
                        text_content = await page.evaluate('(element) => element.textContent', stage)
                        if '上传成功' in text_content:
                            upload_success = True
                            break
                    if upload_success:
                        self.logger.info("[+] 检测到上传成功标识!")
                        break
                    else:
                        self.logger.debug("[-] 未找到上传成功标识，继续等待...")
                else:
                    self.logger.debug("[-] 未找到预览元素，继续等待...")
                    await asyncio.sleep(0.5)
            except Exception as e:
                self.logger.debug(f"[-] 检测过程出错: {str(e)}，重新尝试...")
                await asyncio.sleep(0.3)

    async def _fill_video_info(self, page: Page, title: str, content: str, tags: List[str]):
        """
        填写视频信息

        Args:
            page: 页面实例
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
        """
        await page.wait_for_selector("input[placeholder*='填写标题'], .notranslate", state='visible', timeout=5000)
        self.logger.info("[-] 正在填充标题和话题...")

        title_container = page.locator("input[placeholder*='填写标题']")
        if await title_container.count():
            await title_container.fill(title[:20])
        else:
            title_container2 = page.locator(".notranslate")
            await title_container2.click()
            await page.keyboard.press("Backspace")
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.press("Delete")
            await page.keyboard.type(title)
            await page.keyboard.press("Enter")

        description_selector = "div.tiptap-container div[contenteditable]"
        desc_element = page.locator(description_selector)
        await desc_element.click()

        await desc_element.type(content)
        await desc_element.press("End")
        await desc_element.type("\n")

        for tag in tags:
            clean_tag = tag.lstrip("#")
            await desc_element.type("#")
            await desc_element.type(clean_tag)
            await page.wait_for_timeout(1000)
            await desc_element.press("Enter")
            await desc_element.type(" ")

        self.logger.info("标签已添加到正文描述中")

    async def _click_first_visible_element(self, page: Page, selectors: List[str], description: str = "元素", wait_after: int = 0) -> bool:
        """
        点击第一个可见的元素

        Args:
            page: 页面实例
            selectors: 选择器列表
            description: 元素描述（用于日志）
            wait_after: 点击后等待时间（毫秒）

        Returns:
            是否成功点击
        """
        for selector in selectors:
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    for i in range(await element.count()):
                        btn = element.nth(i)
                        if await btn.is_visible():
                            await btn.click(force=True, timeout=3000)
                            self.logger.info(f"[+] 已点击{description}: {selector}")
                            if wait_after > 0:
                                await asyncio.sleep(wait_after / 1000)
                            return True
            except Exception:
                continue
        return False

    async def _upload_file_to_first_input(self, page: Page, selectors: List[str], file_path: str | Path, accept_type: str = "image") -> bool:
        """
        上传文件到第一个匹配的输入框

        Args:
            page: 页面实例
            selectors: 选择器列表
            file_path: 文件路径
            accept_type: 接受的文件类型

        Returns:
            是否成功上传
        """
        for selector in selectors:
            try:
                file_input = page.locator(selector)
                if await file_input.count() > 0:
                    for i in range(await file_input.count()):
                        input_elem = file_input.nth(i)
                        accept = await input_elem.get_attribute('accept')
                        if accept and (accept_type in accept or accept == '*'):
                            await input_elem.set_input_files(file_path)
                            self.logger.info(f"[+] 已上传{accept_type}文件")
                            return True
            except Exception:
                continue
        return False

    async def _set_thumbnail(self, page: Page, thumbnail_path: Optional[str | Path]):
        """
        设置视频封面

        Args:
            page: 页面实例
            thumbnail_path: 封面图片路径
        """
        if not thumbnail_path:
            self.logger.info("[-] 未指定封面路径，跳过封面设置")
            return

        start_time = time.time()
        self.logger.debug(f"[DEBUG] _set_thumbnail 开始执行: {start_time}")
        
        try:
            self.logger.info("[-] 正在设置视频封面...")
            await page.wait_for_timeout(1000)
            self.logger.debug(f"[DEBUG] 等待1秒后: {time.time() - start_time:.2f}秒")

            cover_selectors = [
                'div[class*="upload"]:has-text("封面")',
                'text="封面"',
                'button:has-text("封面")',
                'div[class*="cover"]:has-text("设置")'
            ]

            click_start = time.time()
            cover_clicked = await self._click_first_visible_element(page, cover_selectors, "封面设置按钮", 1000)
            self.logger.debug(f"[DEBUG] 点击封面按钮耗时: {time.time() - click_start:.2f}秒")

            if not cover_clicked:
                self.logger.warning("[!] 未找到封面设置按钮，跳过封面设置")
                return

            await page.wait_for_selector("input[type='file'], input[class*='upload'], input[class*='file']", state='visible', timeout=5000)
            self.logger.debug(f"[DEBUG] 等待文件输入框后: {time.time() - start_time:.2f}秒")

            file_input_selectors = [
                "input[type='file']",
                "input[class*='upload']",
                "input[class*='file']"
            ]

            upload_start = time.time()
            file_uploaded = await self._upload_file_to_first_input(page, file_input_selectors, thumbnail_path, "image")
            self.logger.debug(f"[DEBUG] 上传封面文件耗时: {time.time() - upload_start:.2f}秒")

            if not file_uploaded:
                self.logger.warning("[!] 未找到文件上传输入框，跳过封面上传")

            finish_selectors = [
                'button:has-text("完成")',
                'button:has-text("确认")',
                'button:has-text("确定")',
                'div[class*="footer"] button:visible'
            ]

            finish_start = time.time()
            await self._click_first_visible_element(page, finish_selectors, "完成按钮", 500)
            self.logger.debug(f"[DEBUG] 点击完成按钮耗时: {time.time() - finish_start:.2f}秒")

            self.logger.info("[+] 封面设置完成")
            self.logger.debug(f"[DEBUG] _set_thumbnail 总耗时: {time.time() - start_time:.2f}秒")

        except Exception as e:
            self.logger.warning(f"[!] 设置封面时出错: {e}，继续执行后续流程")

    async def _set_schedule_time(self, page: Page, publish_date: datetime):
        """
        设置定时发布时间

        Args:
            page: 页面实例
            publish_date: 发布时间
        """
        self.logger.info("[-] 正在设置定时发布时间...")
        try:
            label_element = page.locator("label:has-text('定时发布')")
            await label_element.scroll_into_view_if_needed()
            await label_element.click(timeout=10000)
        except Exception as e:
            self.logger.warning(f"[!] 点击定时发布标签时出错: {e}，尝试其他方式")
            try:
                radio_element = page.locator(".el-radio__label:has-text('定时发布')")
                await radio_element.scroll_into_view_if_needed()
                await radio_element.click(timeout=5000)
            except Exception as e2:
                self.logger.warning(f"[!] 无法点击定时发布标签: {e2}，跳过定时发布设置")
                return
        
        try:
            await page.wait_for_selector('.el-input__inner[placeholder="选择日期和时间"]', state='visible', timeout=5000)
        except Exception as e:
            self.logger.warning(f"[!] 等待日期时间输入框时出错: {e}，跳过定时发布设置")
            return
       
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
        self.logger.info(f"publish_date_hour: {publish_date_hour}")
       
        await page.locator('.el-input__inner[placeholder="选择日期和时间"]').click()
        await page.wait_for_selector('.el-input__inner[placeholder="选择日期和时间"]:focus', state='visible', timeout=3000)
        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)
     



    async def _set_location(self, page: Page, location: str):
        """
        设置地理位置

        Args:
            page: 页面实例
            location: 地理位置
        """
        self.logger.info(f"开始设置位置: {location}")

        loc_ele = await page.wait_for_selector('div.d-text.d-select-placeholder.d-text-ellipsis.d-text-nowrap')
        await loc_ele.click()
        self.logger.info("点击地点输入框完成")

        await page.wait_for_timeout(1000)
        await page.keyboard.type(location)
        self.logger.info(f"位置名称输入完成: {location}")

        await page.wait_for_timeout(3000)

        flexible_xpath = (
            f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
            f'//div[contains(@class, "d-options-wrapper")]'
            f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
            f'//div[contains(@class, "name") and text()="{location}"]'
        )
        await page.wait_for_timeout(3000)

        try:
            location_option = await page.wait_for_selector(flexible_xpath, timeout=3000)

            if location_option:
                self.logger.info("使用灵活选择器定位成功")
            else:
                location_option = await page.wait_for_selector(
                    f'//div[contains(@class, "d-popover") and contains(@class, "d-dropdown")]'
                    f'//div[contains(@class, "d-options-wrapper")]'
                    f'//div[contains(@class, "d-grid") and contains(@class, "d-options")]'
                    f'/div[1]//div[contains(@class, "name") and text()="{location}"]',
                    timeout=2000
                )

            await location_option.scroll_into_view_if_needed()
            is_visible = await location_option.is_visible()
            self.logger.info(f"目标选项是否可见: {is_visible}")

            await location_option.click()
            self.logger.info(f"成功选择位置: {location}")
            return True

        except Exception as e:
            self.logger.error(f"定位位置失败: {e}")
            return False

    async def _publish_video(self, page: Page):
        """
        发布视频

        Args:
            page: 页面实例
        """
        while True:
            try:
                await page.locator('button:has-text("发布")').click()
                await page.wait_for_url(self.success_url_pattern + "?**", timeout=3000)
                self.logger.success("[-] 视频发布成功")
                break
            except:
                self.logger.info("[-] 视频正在发布中...")
                await page.screenshot(full_page=True)
                await page.wait_for_timeout(300)
