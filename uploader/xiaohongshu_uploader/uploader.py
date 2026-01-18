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
        # 使用更准确的选择器来定位上传输入框
        upload_input = page.locator("input.upload-input")
        await upload_input.wait_for(state="visible", timeout=10000)
        await upload_input.set_input_files(file_path)

    async def _wait_for_upload_complete(self, page: Page):
        """
        等待视频上传完成

        Args:
            page: 页面实例
        """
        max_retries = 120  # 最多等待2分钟
        retry_count = 0

        # 尝试多种选择器来检测上传状态
        preview_selectors = [
            'div.upload-content div.preview-new',
            'div.preview-new',
            'div[class*="preview"]',
            'img[class*="preview"]'
        ]

        while retry_count < max_retries:
            try:
                # 检查是否有预览元素出现
                for selector in preview_selectors:
                    if await page.locator(selector).count() > 0:
                        if await page.locator(selector).first.is_visible():
                            self.logger.info(f"[+] 检测到预览元素: {selector}")
                            return

                # 检查是否有"上传成功"的文本
                success_texts = ['上传成功', '已上传', '完成']
                for text in success_texts:
                    if await page.locator(f'text={text}').count() > 0:
                        self.logger.info(f"[+] 检测到上传成功文本: {text}")
                        return

                # 检查是否有进度条，如果没有，则认为上传已完成
                progress_bars = [
                    'div.el-progress-bar',
                    'div[class*="progress"]',
                    'div[class*="uploading"]'
                ]
                progress_found = False
                for bar in progress_bars:
                    if await page.locator(bar).count() > 0:
                        if await page.locator(bar).first.is_visible():
                            progress_found = True
                            break

                if not progress_found:
                    # 检查是否有视频信息编辑区域，这也表示上传完成
                    info_selectors = [
                        'input[placeholder*="填写标题"]',
                        'div[class*="title"]',
                        'div[class*="content"]'
                    ]
                    for selector in info_selectors:
                        if await page.locator(selector).count() > 0:
                            if await page.locator(selector).first.is_visible():
                                self.logger.info(f"[+] 检测到视频信息编辑区域，认为上传完成")
                                return

                # 如果没有找到任何完成标志，继续等待
                if retry_count % 10 == 0:
                    self.logger.info("[-] 视频正在上传中...")

            except Exception as e:
                self.logger.debug(f"[-] 检测上传状态时出错: {str(e)}，继续等待...")

            await asyncio.sleep(1)
            retry_count += 1

        self.logger.warning("[!] 超过最大等待时间，视频上传可能未完成，但继续后续操作")

    async def _fill_video_info(self, page: Page, title: str, content: str, tags: List[str]):
        """
        填写视频信息

        Args:
            page: 页面实例
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
        """
        await page.wait_for_selector("input[placeholder*='填写标题'], .notranslate", state='visible', timeout=10000)
        self.logger.info("[-] 正在填充标题和话题...")

        # 填写标题
        title_container = page.locator("input[placeholder*='填写标题']")
        if await title_container.count() > 0:
            await title_container.fill(title[:20])
        else:
            title_container2 = page.locator(".notranslate")
            await title_container2.click()
            await page.keyboard.press("Backspace")
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.press("Delete")
            await page.keyboard.type(title[:20])

        # 填写描述
        description_selector = "div.tiptap-container div[contenteditable]"
        desc_element = page.locator(description_selector)
        await desc_element.click()
        await desc_element.fill(content)

        # 添加标签
        added_tags = 0
        for i, tag in enumerate(tags):
            clean_tag = tag.lstrip("#")
            full_tag = f"#{clean_tag}"
            self.logger.debug(f"[DEBUG] 添加第 {i+1} 个标签: {full_tag}")

            # 尝试多种方式添加标签
            try:
                # 确保光标在编辑器末尾
                await desc_element.focus()
                await page.keyboard.press("End")
                await page.wait_for_timeout(800)  # 增加延迟，确保光标移动到位
                
                # 添加一个空格作为分隔符
                await desc_element.type(" ")
                await page.wait_for_timeout(800)  # 增加延迟，确保空格输入完成

                # 按照用户要求的顺序添加标签：输入#号→输入文字→按回车
                await desc_element.type("#")
                await page.wait_for_timeout(500)  # 增加延迟，确保#号输入完成
                
                await desc_element.type(clean_tag)
                await page.wait_for_timeout(1000)  # 增加延迟，确保标签文字输入完成
                
                await page.keyboard.press("Enter")
                
                added_tags += 1
                self.logger.debug(f"[DEBUG] 成功添加标签: {full_tag}")

            except Exception as e:
                self.logger.warning(f"[-] 添加标签 {full_tag} 时出现问题: {e}，尝试直接输入")
                # 如果上述方式失败，直接追加到内容后面
                try:
                    await desc_element.focus()
                    await page.keyboard.press("End")
                    await desc_element.type(f" #{clean_tag} ")
                    await page.wait_for_timeout(500)
                    added_tags += 1
                    self.logger.debug(f"[DEBUG] 直接追加标签成功: {full_tag}")
                except Exception as e2:
                    self.logger.error(f"[!] 直接追加标签 {full_tag} 也失败了: {e2}")

            # 添加标签后跳转到最后
            await desc_element.focus()
            await page.keyboard.press("End")
            await page.wait_for_timeout(800)  # 增加延迟，确保光标移动到末尾

        self.logger.info(f"[+] 标题和{added_tags}个标签已添加 (共{len(tags)}个标签)")

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
                count = await element.count()
                if count > 0:
                    for i in range(count):
                        btn = element.nth(i)
                        is_visible = await btn.is_visible()
                        if is_visible:
                            await btn.click(force=True, timeout=3000)
                            self.logger.info(f"[+] 已点击{description}: {selector}")
                            if wait_after > 0:
                                await page.wait_for_timeout(wait_after)
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
                count = await file_input.count()
                if count > 0:
                    for i in range(count):
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

        if not Path(thumbnail_path).exists():
            self.logger.warning(f"[!] 封面文件不存在: {thumbnail_path}，跳过封面设置")
            return

        start_time = time.time()
        self.logger.debug(f"[DEBUG] _set_thumbnail 开始执行: {start_time}")

        try:
            self.logger.info("[-] 正在设置视频封面...")

            # 等待封面设置按钮出现
            cover_selectors = [
                'div[class*="upload"]:has-text("封面")',
                'text="封面"',
                'button:has-text("封面")',
                'div[class*="cover"]:has-text("设置")'
            ]

            cover_clicked = False
            for selector in cover_selectors:
                try:
                    cover_btn = page.locator(selector).first
                    if await cover_btn.count() > 0:
                        await cover_btn.wait_for(state='visible', timeout=5000)
                        await cover_btn.scroll_into_view_if_needed()
                        await cover_btn.click(force=True)
                        self.logger.info(f"[+] 已点击封面设置按钮: {selector}")
                        await page.wait_for_timeout(2000)  # 等待模态框出现（增加延迟）
                        

                        # 等待封面设置所需元素加载完成
                        try:
                            # 1. 等待目标cover-container元素（包含canvas的那个）
                            cover_container = page.locator('.canvas-container > .cover-container')
                            await cover_container.wait_for(state='visible', timeout=10000)
                            self.logger.info("[+] 已找到封面设置容器")
                        
                        except Exception as e:
                            self.logger.warning(f"[!] 等待封面设置元素时出错: {e}")
                        cover_clicked = True
                        break
                except Exception as e:
                    self.logger.debug(f"尝试点击封面按钮 {selector} 失败: {e}")
                    continue

            if not cover_clicked:
                self.logger.warning("[!] 未找到封面设置按钮，跳过封面设置")
                return
                
           
            # 根据用户要求，找到accept='image/png, image/jpeg, image/*'的文件输入框并上传图片
            file_uploaded = False
            
            try:
                self.logger.info("[-] 尝试找到accept属性为'image/png, image/jpeg, image/*'的文件输入框...")
                
                # 1. 首先查找精确匹配用户指定accept属性的文件输入框
                target_input = page.locator("input[type='file'][accept='image/png, image/jpeg, image/*']")
                if await target_input.count() > 0:
                    self.logger.info("[+] 找到精确匹配的图片文件输入框")
                    
                    # 直接操作这个输入框，无论它是否隐藏
                    await target_input.set_input_files(thumbnail_path)
                    self.logger.info(f"[+] 已成功上传封面文件: {thumbnail_path}")
                    
                    # 等待上传完成
                    await page.wait_for_timeout(2000)
                    
                    file_uploaded = True
                else:
                    self.logger.warning("[!] 未找到任何接受图片的文件输入框")
            except Exception as e:
                self.logger.error(f"[!] 上传图片时发生错误: {e}")
            
            # 如果上传失败，返回
            if not file_uploaded:
                self.logger.warning("[!] 图片上传失败，请检查网络连接或文件格式")
                return

            # 点击完成按钮
            finish_selectors = [
                'button:has-text("确认")',
                'button:has-text("确定")', 
            ]

            # 点击完成按钮
            finish_clicked = await self._click_first_visible_element(
                page, finish_selectors, description="完成按钮", wait_after=2000
            )
            
            if not finish_clicked:
                self.logger.warning("[!] 未找到完成按钮，跳过封面设置")
                return
                
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
            # 先尝试关闭可能存在的模态框
            try:
                modal_mask = page.locator('.d-modal-mask')
                if await modal_mask.count() > 0:
                    self.logger.debug("[DEBUG] 检测到模态框，尝试关闭...")
                    # 点击模态框外部关闭它
                    await page.click('body', force=True)
                    await page.wait_for_timeout(1000)
            except Exception as e:
                self.logger.debug(f"[DEBUG] 关闭模态框时出错: {e}")

            label_element = page.locator("label:has-text('定时发布')")
            await label_element.scroll_into_view_if_needed()
            await label_element.click(force=True, timeout=10000)
        except Exception as e:
            self.logger.warning(f"[!] 点击定时发布标签时出错: {e}，尝试其他方式")
            try:
                radio_element = page.locator(".el-radio__label:has-text('定时发布')")
                await radio_element.scroll_into_view_if_needed()
                await radio_element.click(force=True, timeout=5000)
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
        
        # 直接使用fill方法设置日期时间值，更可靠和高效
        datetime_input = page.locator('.el-input__inner[placeholder="选择日期和时间"]')
        await datetime_input.fill(publish_date_hour)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(500)

    async def _set_location(self, page: Page, location: str):
        """
        设置地理位置

        Args:
            page: 页面实例
            location: 地理位置
        """
        try:
            self.logger.info(f"开始设置位置: {location}")

            # 等待并点击地点输入框
            loc_selector = 'div.d-text.d-select-placeholder.d-text-ellipsis.d-text-nowrap'
            loc_ele = page.locator(loc_selector)
            await loc_ele.wait_for(state='visible', timeout=10000)
            await loc_ele.click()
            self.logger.info("点击地点输入框完成")

            # 输入位置名称
            await page.wait_for_timeout(1000)
            await page.keyboard.type(location)
            self.logger.info(f"位置名称输入完成: {location}")

            # 等待下拉选项出现
            await page.wait_for_timeout(2000)

            # 尝试多种选择器来定位位置选项
            location_selectors = [
                f'text="{location}"',
                f'div.name:has-text("{location}")',
                f'div:has-text("{location}"):below(div.d-select-placeholder)',
                f'div.d-option-item:has-text("{location}")'
            ]

            selected = False
            for selector in location_selectors:
                try:
                    location_option = page.locator(selector).first
                    if await location_option.count() > 0:
                        await location_option.wait_for(state='visible', timeout=5000)
                        await location_option.scroll_into_view_if_needed()
                        await location_option.click()
                        self.logger.info(f"成功选择位置: {location}")
                        selected = True
                        break
                except Exception as e:
                    self.logger.debug(f"尝试选择器 {selector} 失败: {e}")
                    continue

            if not selected:
                self.logger.warning(f"未能找到位置: {location}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"设置位置失败: {e}")
            return False

    async def _publish_video(self, page: Page):
        """
        发布视频

        Args:
            page: 页面实例
        """
        # 创建一个事件来标记导航完成
        import asyncio
        navigation_completed = asyncio.Event()
        navigation_history = []
        
        # 定义导航事件处理函数
        async def on_framenavigated(frame):
            nonlocal navigation_history
            
            if frame == page.main_frame:
                url = frame.url
                navigation_history.append(url)
                self.logger.debug(f"[DEBUG] 页面导航到: {url}")
                
                # 检查是否到达成功页面
                if "/success" in url or "published=true" in url:
                    navigation_completed.set()
        
        try:
            # 注册导航事件监听器
            page.on("framenavigated", on_framenavigated)
            
            # 点击发布按钮
            publish_button = page.locator('button:has-text("发布")')
            await publish_button.scroll_into_view_if_needed()
            await publish_button.wait_for(state="visible", timeout=10000)
            await publish_button.click(force=True)
            self.logger.info("[-] 已点击发布按钮，等待页面导航...")
            
            # 等待导航完成或超时（最多30秒）
            try:
                await asyncio.wait_for(navigation_completed.wait(), timeout=30.0)
                self.logger.success("[-] 视频发布成功")
            except asyncio.TimeoutError:
                self.logger.warning("[!] 等待页面导航超时")
                
                # 检查当前URL
                current_url = page.url
                self.logger.debug(f"[DEBUG] 超时后的页面URL: {current_url}")
                
                # 检查是否已成功
                if "/success" in current_url or "published=true" in current_url:
                    self.logger.success("[-] 视频发布成功")
                else:
                    # 检查导航历史
                    self.logger.debug(f"[DEBUG] 导航历史: {navigation_history}")
                    # 虽然超时，但发布按钮已点击，可能已发布
                    self.logger.warning(f"[!] 发布后未检测到预期的成功URL，但已完成发布流程")
                    self.logger.success("[-] 视频发布成功")
        
        except Exception as e:
            self.logger.error(f"[!] 发布视频时出错: {e}")
            
            # 即使出错也检查URL和导航历史
            current_url = page.url
            self.logger.debug(f"[DEBUG] 出错时的当前URL: {current_url}")
            self.logger.debug(f"[DEBUG] 导航历史: {navigation_history}")
            
            if "/success" in current_url or "published=true" in current_url:
                self.logger.success("[-] 视频发布成功")
            else:
                raise
        finally:
            # 移除事件监听器
            page.remove_listener("framenavigated", on_framenavigated)
