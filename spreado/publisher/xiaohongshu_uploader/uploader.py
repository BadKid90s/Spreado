import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import time

from playwright.async_api import Page, Error
import asyncio

from ...publisher.uploader import BaseUploader


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
    def login_success_url(self) -> str:
        return "https://creator.xiaohongshu.com/new/home"

    @property
    def upload_url(self) -> str:
        return (
            "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video"
        )

    @property
    def success_url_pattern(self) -> str:
        return "https://creator.xiaohongshu.com/publish/success"

    @property
    def _login_selectors(self) -> List[str]:
        return ['text="手机号登录"', 'text="扫码登录"', 'text="登录"', ".login-btn"]

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
        """
        上传视频到小红书

        Args:
            page: 页面
            file_path: 视频文件路径
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表
            publish_date: 定时发布时间
            thumbnail_path: 封面图片路径
        Returns:
            上传是否成功
        """
        start_time = time.time()
        self.logger.debug(f"[DEBUG] upload_video 开始执行: {start_time}")

        try:
            self.logger.debug(
                f"[DEBUG] 页面初始化完成: {time.time() - start_time:.2f}秒"
            )

            self.logger.info("[-] 正在打开上传页面...")
            await page.goto(self.upload_url)
            try:
                await page.wait_for_url(self.upload_url, timeout=5000)
            except Error:
                pass
            self.logger.debug(f"[DEBUG] 页面导航完成: {time.time() - start_time:.2f}秒")

            self.logger.info(f"[+] 正在上传视频: {title}")
            upload_start = time.time()

            # 上传视频文件
            if not await self._upload_video_file(page, file_path):
                self.logger.error("[!] 视频文件上传失败，终止上传流程")
                return False

            # 等待上传完成
            if not await self._wait_for_upload_complete(page):
                self.logger.error("[!] 视频上传未完成，终止上传流程")
                return False

            self.logger.debug(
                f"[DEBUG] 视频上传完成: {time.time() - upload_start:.2f}秒"
            )

            fill_start = time.time()
            # 填充视频信息
            if not await self._fill_video_info(page, title, content, tags):
                self.logger.error("[!] 视频信息填充失败，终止上传流程")
                return False

            self.logger.debug(
                f"[DEBUG] 视频信息填充完成: {time.time() - fill_start:.2f}秒"
            )

            thumb_start = time.time()
            # 设置封面
            if not await self._set_thumbnail(page, thumbnail_path):
                self.logger.error("[!] 封面设置失败，终止上传流程")
                return False

            self.logger.debug(
                f"[DEBUG] 封面设置完成: {time.time() - thumb_start:.2f}秒"
            )

            if publish_date:
                schedule_start = time.time()
                # 设置定时发布
                if not await self._set_schedule_time(page, publish_date):
                    self.logger.error("[!] 定时发布设置失败，终止上传流程")
                    return False

                self.logger.debug(
                    f"[DEBUG] 定时发布设置完成: {time.time() - schedule_start:.2f}秒"
                )

            publish_start = time.time()
            # 发布视频
            if not await self._publish_video(page):
                self.logger.error("[!] 视频发布失败，终止上传流程")
                return False

            self.logger.debug(
                f"[DEBUG] 视频发布完成: {time.time() - publish_start:.2f}秒"
            )

            total_time = time.time() - start_time
            self.logger.info(f"[DEBUG] upload_video 总耗时: {total_time:.2f}秒")
            self.logger.info("[-] 视频发布成功")

            return True

        except Exception as e:
            self.logger.error(f"[!] 上传视频时出错: {e}")
            return False

    async def _upload_video_file(self, page: Page, file_path: str | Path) -> bool:
        """
        上传视频文件

        Args:
            page: 页面实例
            file_path: 视频文件路径

        Returns:
            是否成功上传视频文件
        """
        try:
            # 使用更准确的选择器来定位上传输入框
            upload_input = page.locator("input.upload-input")
            await upload_input.wait_for(state="visible", timeout=10000)
            await upload_input.set_input_files(file_path)
            return True
        except Exception as e:
            self.logger.error(f"[!] 上传视频文件时出错: {e}")
            return False

    async def _wait_for_upload_complete(self, page: Page) -> bool:
        """
        等待视频上传完成

        Args:
            page: 页面实例

        Returns:
            是否成功完成视频上传
        """
        max_retries = 120  # 最多等待2分钟
        retry_count = 0

        # 尝试多种选择器来检测上传状态
        preview_selectors = [
            "div.upload-content div.preview-new",
            "div.preview-new",
            'div[class*="preview"]',
            'img[class*="preview"]',
        ]

        while retry_count < max_retries:
            try:
                # 检查是否有预览元素出现
                for selector in preview_selectors:
                    if await page.locator(selector).count() > 0:
                        if await page.locator(selector).first.is_visible():
                            self.logger.info(f"[+] 检测到预览元素: {selector}")
                            return True

                # 检查是否有"上传成功"的文本
                success_texts = ["上传成功", "已上传", "完成"]
                for text in success_texts:
                    if await page.locator(f"text={text}").count() > 0:
                        self.logger.info(f"[+] 检测到上传成功文本: {text}")
                        return True

                # 检查是否有进度条，如果没有，则认为上传已完成
                progress_bars = [
                    "div.el-progress-bar",
                    'div[class*="progress"]',
                    'div[class*="uploading"]',
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
                        'div[class*="content"]',
                    ]
                    for selector in info_selectors:
                        if await page.locator(selector).count() > 0:
                            if await page.locator(selector).first.is_visible():
                                self.logger.info(
                                    "[+] 检测到视频信息编辑区域，认为上传完成"
                                )
                                return True

                # 如果没有找到任何完成标志，继续等待
                if retry_count % 10 == 0:
                    self.logger.info("[-] 视频正在上传中...")

            except Exception as e:
                self.logger.debug(f"[-] 检测上传状态时出错: {str(e)}，继续等待...")

            await asyncio.sleep(1)
            retry_count += 1

        self.logger.warning("[!] 超过最大等待时间，视频上传可能未完成")
        return False

    async def _fill_video_info(
        self, page: Page, title: str = "", content: str = "", tags: List[str] = None
    ) -> bool:
        """
        填写视频信息

        Args:
            page: 页面实例
            title: 视频标题
            content: 视频描述
            tags: 视频标签列表

        Returns:
            是否成功填写视频信息
        """
        try:
            await page.wait_for_selector(
                "input[placeholder*='填写标题'], .notranslate",
                state="visible",
                timeout=10000,
            )
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
            if tags:
                for i, tag in enumerate(tags):
                    clean_tag = tag.lstrip("#")
                    full_tag = f"#{clean_tag}"
                    self.logger.debug(f"[DEBUG] 添加第 {i + 1} 个标签: {full_tag}")

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
                        await page.wait_for_timeout(
                            1000
                        )  # 增加延迟，确保标签文字输入完成

                        await page.keyboard.press("Enter")

                        added_tags += 1
                        self.logger.debug(f"[DEBUG] 成功添加标签: {full_tag}")

                    except Exception as e:
                        self.logger.warning(
                            f"[-] 添加标签 {full_tag} 时出现问题: {e}，尝试直接输入"
                        )
                        # 如果上述方式失败，直接追加到内容后面
                        try:
                            await desc_element.focus()
                            await page.keyboard.press("End")
                            await desc_element.type(f" #{clean_tag} ")
                            await page.wait_for_timeout(500)
                            added_tags += 1
                            self.logger.debug(f"[DEBUG] 直接追加标签成功: {full_tag}")
                        except Exception as e2:
                            self.logger.error(
                                f"[!] 直接追加标签 {full_tag} 也失败了: {e2}"
                            )
                            # 标签添加失败不影响整体上传

                    # 添加标签后跳转到最后
                    await desc_element.focus()
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(800)  # 增加延迟，确保光标移动到末尾

            self.logger.info(
                f"[+] 标题和{added_tags}个标签已添加 (共{len(tags)}个标签)"
            )
            return True

        except Exception as e:
            self.logger.error(f"[!] 填写视频信息时出错: {e}")
            return False

    async def _set_thumbnail(
        self, page: Page, thumbnail_path: Optional[str | Path]
    ) -> bool:
        """
        设置视频封面

        Args:
            page: 页面实例
            thumbnail_path: 封面图片路径

        Returns:
            是否成功设置视频封面
        """
        if not thumbnail_path:
            self.logger.info("[-] 未指定封面路径，跳过封面设置")
            return True

        if not Path(thumbnail_path).exists():
            self.logger.warning(f"[!] 封面文件不存在: {thumbnail_path}，跳过封面设置")
            return True

        start_time = time.time()
        self.logger.debug(f"[DEBUG] _set_thumbnail 开始执行: {start_time}")

        try:
            self.logger.info("[-] 正在设置视频封面...")

            # 等待封面设置按钮出现
            cover_selectors = [
                'div[class*="upload"]:has-text("封面")',
                'text="封面"',
                'button:has-text("封面")',
                'div[class*="cover"]:has-text("设置")',
            ]

            cover_element = await self._find_first_element(page, cover_selectors)
            if cover_element is None:
                self.logger.error("[-] 未找到封面设置按钮")
                return False

            await cover_element.click(force=True)
            self.logger.info("[+] 已点击封面元素")
            await page.wait_for_selector(
                ".d-modal:has-text('设置封面')", state="visible", timeout=10000
            )

            upload_element = page.get_by_text("上传封面", exact=True)
            if upload_element is None:
                self.logger.error("[-] 未找上传封面按钮")
                return False
            await upload_element.wait_for(state="visible", timeout=10_000)
            await upload_element.click(force=True, timeout=10000)

            upload_input_selectors = [
                'input.upload-input[type="file"][accept*="image"]'
            ]
            upload_input_element = await self._find_first_element(
                page, upload_input_selectors, state="attached"
            )
            if upload_input_element is None:
                self.logger.error("[-] 未找上传封面文件输入元素")
                return False

            # 直接操作这个输入框，无论它是否隐藏
            await upload_input_element.set_input_files(thumbnail_path)
            self.logger.info(f"[+] 已成功上传封面文件: {thumbnail_path}")

            # 等待上传完成
            await page.wait_for_timeout(2000)

            # 点击完成按钮
            finish_selectors = [
                'button:has-text("确认")',
                'button:has-text("确定")',
            ]
            finish_element = await self._find_first_element(page, finish_selectors)
            # 点击完成按钮
            await finish_element.click(force=True, timeout=3000)
            self.logger.info("[+] 已点击完成按钮")
            self.logger.info("[+] 封面设置完成")
            self.logger.debug(
                f"[DEBUG] _set_thumbnail 总耗时: {time.time() - start_time:.2f}秒"
            )
            return True

        except Exception as e:
            self.logger.warning(f"[!] 设置封面时出错: {e}，继续执行后续流程")
            return True

    async def _set_schedule_time(self, page: Page, publish_date: datetime) -> bool:
        """
        设置定时发布时间

        Args:
            page: 页面实例
            publish_date: 发布时间

        Returns:
            是否成功设置定时发布时间
        """
        try:
            self.logger.info("[-] 正在设置定时发布时间...")
            # 先尝试关闭可能存在的模态框
            try:
                modal_mask = page.locator(".d-modal-mask")
                if await modal_mask.count() > 0:
                    self.logger.debug("[DEBUG] 检测到模态框，尝试关闭...")
                    # 点击模态框外部关闭它
                    await page.click("body", force=True)
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
                return True

        try:
            await page.wait_for_selector(
                '.el-input__inner[placeholder="选择日期和时间"]',
                state="visible",
                timeout=5000,
            )
        except Exception as e:
            self.logger.warning(f"[!] 等待日期时间输入框时出错: {e}，跳过定时发布设置")
            return True

        try:
            publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
            self.logger.info(f"publish_date_hour: {publish_date_hour}")

            # 直接使用fill方法设置日期时间值，更可靠和高效
            datetime_input = page.locator(
                '.el-input__inner[placeholder="选择日期和时间"]'
            )
            await datetime_input.fill(publish_date_hour)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)

            self.logger.info("[+] 定时发布时间设置完成")
            return True
        except Exception as e:
            self.logger.error(f"[!] 设置定时发布时间时出错: {e}")
            return False

    async def _publish_video(self, page: Page) -> bool:
        """
        发布视频

        Args:
            page: 页面实例

        Returns:
            是否成功发布视频
        """
        is_published = False
        success_pattern = re.compile(r"/success|published=true")

        # 精确定位发布按钮
        publish_button = page.locator("button.publishBtn")

        try:
            # 确保按钮可见
            await publish_button.scroll_into_view_if_needed()
            await publish_button.wait_for(state="visible", timeout=10_000)

            self.logger.info("[-] 已点击发布按钮，等待页面导航...")

            try:
                # 点击并等待 URL 导航到成功页（推荐写法）
                async with page.expect_navigation(
                    url=success_pattern,  # 也可以直接用字符串／通配符
                    wait_until="load",  # 或 "networkidle"，视页面情况而定
                    timeout=30_000,
                ):
                    await publish_button.click(force=True)

                self.logger.info("[-] 视频发布成功")
                is_published = True

            except Error:
                # 超时：检查当前 URL 是否其实已经是成功页
                self.logger.warning("[!] 等待页面导航超时")
                current_url = page.url
                self.logger.debug(f"[DEBUG] 超时后的页面URL: {current_url}")

                if success_pattern.search(current_url):
                    self.logger.info("[-] 视频发布成功（超时后检查到成功URL）")
                    is_published = True
                else:
                    self.logger.error("[-] 视频发布失败，未检测到成功URL")

        except Exception as e:
            # 捕获其它异常，同样最后兜底检查 URL
            self.logger.exception(f"[!] 发布视频时出错: {e}")
            current_url = page.url
            self.logger.debug(f"[DEBUG] 出错时的当前URL: {current_url}")

            if success_pattern.search(current_url):
                self.logger.info("[-] 视频发布成功（异常后检查到成功URL）")
                is_published = True

        return is_published
