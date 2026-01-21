from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page, Error

from ...publisher.uploader import BaseUploader


def _format_str_for_short_title(origin_title: str) -> str:
    """
    格式化短标题

    Args:
        origin_title: 原始标题

    Returns:
        格式化后的短标题
    """
    allowed_special_chars = "《》“”:+?%°"
    filtered_chars = [
        (
            char
            if char.isalnum() or char in allowed_special_chars
            else " " if char == "," else ""
        )
        for char in origin_title
    ]
    formatted_string = "".join(filtered_chars)

    if len(formatted_string) > 16:
        formatted_string = formatted_string[:16]
    elif len(formatted_string) < 6:
        formatted_string += " " * (6 - len(formatted_string))

    return formatted_string


class ShiPinHaoUploader(BaseUploader):
    """
    视频号上传器
    """

    @property
    def platform_name(self) -> str:
        return "shipinhao"

    @property
    def login_url(self) -> str:
        return "https://channels.weixin.qq.com/login.html"

    @property
    def login_success_url(self) -> str:
        return "https://channels.weixin.qq.com/platform/"

    @property
    def upload_url(self) -> str:
        return "https://channels.weixin.qq.com/platform/post/create"

    @property
    def success_url_pattern(self) -> str:
        return "https://channels.weixin.qq.com/platform/post/list"

    @property
    def _login_selectors(self) -> List[str]:
        return [
            "div.qrcode-wrap",
            'text="登录"',
            ':has-text("微信扫码登录")',
            ".login-btn",
        ]

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
        上传视频到腾讯视频

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
        try:

            await page.goto(self.upload_url)
            self.logger.info("[-] 正在打开上传页面...")
            await page.wait_for_url(self.upload_url)

            # 等待发布界面的加载元素隐藏（隐藏说明加载成功）
            self.logger.info("[-] 正在等待发布界面加载完成...")
            loading_element = page.locator(
                ".finder-page.PostCreate #container-wrap div.wrap"
            )
            await loading_element.wait_for(state="hidden", timeout=30000)
            self.logger.info("[-] 发布界面已加载完成")

            self.logger.info(f"[+] 正在处理视频: {title}")

            # 上传视频文件
            if not await self._upload_video_file(page, file_path):
                self.logger.error("[!] 视频文件上传失败，终止上传流程")
                return False

            # 等待上传完成
            if not await self._wait_for_upload_complete(page):
                self.logger.error("[!] 视频上传未完成，终止上传流程")
                return False

            # 填充视频信息
            if not await self._fill_video_info(page, title, content, tags):
                self.logger.error("[!] 视频信息填充失败，终止上传流程")
                return False

            # 设置封面
            if not await self._set_thumbnail(page, thumbnail_path):
                self.logger.error("[!] 封面设置失败，终止上传流程")
                return False

            if publish_date:
                # 设置定时发布
                if not await self._set_schedule_time(page, publish_date):
                    self.logger.error("[!] 定时发布设置失败，终止上传流程")
                    return False

            # 添加短标题
            if not await self._add_short_title(page, title):
                self.logger.error("[!] 添加短标题失败，终止上传流程")
                return False

            # 发布视频
            if not await self._publish_video(page, False):
                self.logger.error("[!] 视频发布失败，终止上传流程")
                return False

            self.logger.info("[+] 视频发布成功")

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
        # 保存文件路径用于错误处理
        self.file_path = file_path

        # 首先尝试找到并点击上传按钮
        upload_button_selectors = [
            ".finder-card.wrap",
            "div.upload",
            "div.upload-area",
            'button:has-text("上传")',
            'div:has-text("点击上传")',
            'div:has-text("选择视频")',
        ]

        # 尝试点击上传按钮
        for upload_selector in upload_button_selectors:
            try:
                self.logger.info(f"[+] 尝试点击上传按钮: {upload_selector}")
                upload_element = page.locator(upload_selector)
                if await upload_element.count() > 0:
                    # 如果找到多个元素，只点击第一个
                    if await upload_element.count() > 1:
                        self.logger.warning(
                            f"[!] 找到多个匹配元素，点击第一个: {upload_selector}"
                        )
                        await upload_element.first.click()
                    else:
                        await upload_element.click()
                    self.logger.info(f"[+] 已点击上传按钮: {upload_selector}")
                    await page.wait_for_timeout(2000)  # 等待可能的弹窗或文件选择器
                    break
            except Exception as e:
                self.logger.warning(f"[!] 点击上传按钮 {upload_selector} 失败: {e}")

        # 尝试多种定位方式查找文件输入框
        file_input_selectors = [
            'input[type="file"][accept="video/*"]',
        ]

        for selector in file_input_selectors:
            try:
                self.logger.info(f"[+] 尝试使用选择器查找文件输入框: {selector}")
                file_input = page.locator(selector)

                # 对于可能隐藏的输入框，使用attached状态而不是visible
                await file_input.wait_for(state="attached", timeout=5000)

                # 尝试直接设置文件
                await file_input.set_input_files(file_path)
                self.logger.info(f"[+] 文件上传输入框找到并上传成功: {selector}")
                return True
            except Exception as e:
                self.logger.warning(f"[!] 选择器 {selector} 查找失败: {e}")
                continue

        self.logger.error("[!] 选择器查找失败，无法上传视频文件")
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
            await page.locator("div.input-editor").click()
            await page.keyboard.type(title)
            await page.keyboard.press("Enter")

            await page.keyboard.type(content)
            await page.keyboard.press("Enter")

            if tags:
                for tag in tags:
                    if not tag.startswith("#"):
                        await page.keyboard.type("#" + tag)
                    else:
                        await page.keyboard.type(tag)
                    await page.keyboard.press("Space")

            self.logger.info(f"[+] 成功添加hashtag: {len(tags)}")
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
        """
        if not thumbnail_path:
            return True

        self.logger.info("[-] 正在设置视频封面...")

        # 1. 点击个人主页卡片
        await page.click('div.tips-wrap:has(div.cover-tips:has-text("个人主页卡片"))')
        self.logger.info("[-] 已点击个人主页卡片")

        # 2. 等待模态框出现和上传封面元素可见
        await page.wait_for_selector("div.single-cover-uploader-wrap", timeout=10000)
        await page.wait_for_selector(
            'div.single-cover-uploader-wrap div.text-wrap:has-text("上传封面")',
            timeout=5000,
        )
        self.logger.info("[-] 模态框已打开，上传封面元素可见")

        # 3. 找到文件input元素并设置图片
        try:

            # 找到隐藏的文件输入框
            file_input_selector = 'div.single-cover-uploader-wrap input[type="file"][accept="image/jpeg,image/jpg,image/png"]'
            await page.locator(file_input_selector).set_input_files(thumbnail_path)
            self.logger.info("[-] 封面图片已选择")

            # 等待裁剪对话框出现
            await page.wait_for_selector(
                'div.weui-desktop-dialog__wrp:has(h3:has-text("裁剪封面图"))',
                state="visible",
                timeout=10000,
            )
            self.logger.info("[-] 裁剪封面图对话框已打开")

        except Exception as e:
            self.logger.error(f"[!] 选择封面图片时出错: {e}")
            return False

        # 4. 点击确认按钮关闭模态框
        try:
            # 更精确地定位裁剪封面图对话框中的确认按钮
            confirm_button_selector = 'div.cover-set-footer button:has-text("确认")'
            await page.locator(confirm_button_selector).click()
            self.logger.info("[-] 已点击确认按钮")

            # 等待模态框关闭
            await page.wait_for_selector(
                'div.weui-desktop-dialog__wrp:has(h3:has-text("裁剪封面图"))',
                state="hidden",
                timeout=10000,
            )
            self.logger.info("[-] 裁剪封面图对话框已关闭")

        except Exception as e:
            self.logger.error(f"[!] 点击确认按钮时出错: {e}")
            return False

        # 5. 监听图片URL发生变化，确认封面设置成功
        try:
            # 等待封面图片加载完成
            await page.wait_for_selector(
                "div.vertical-cover-wrap img.cover-img-horizontal[src]", timeout=10000
            )

            # 获取封面图片的URL
            cover_image_url = await page.locator(
                "div.vertical-cover-wrap img.cover-img-horizontal"
            ).get_attribute("src")
            if cover_image_url:
                self.logger.info(
                    f"[+] 视频封面设置完成！封面图片URL: {cover_image_url[:50]}..."
                )
                return True
            else:
                self.logger.error("[!] 封面图片URL为空")
                return False

        except Exception as e:
            self.logger.error(f"[!] 验证封面图片设置时出错: {e}")
            return False

    async def _wait_for_upload_complete(self, page: Page) -> bool:
        """
        等待视频上传完成

        Args:
            page: 页面实例

        Returns:
            是否成功等待视频上传完成
        """
        max_wait_time = 300  # 最大等待时间，单位秒
        wait_time = 0
        retry_count = 0
        max_retries = 3  # 最大重试次数

        while wait_time < max_wait_time:
            try:
                try:
                    publish_button = page.get_by_role("button", name="发表")
                    button_class = await publish_button.get_attribute("class")

                    if button_class and "weui-desktop-btn_disabled" not in button_class:
                        self.logger.info("[+] 视频上传完毕")
                        return True
                    else:
                        self.logger.info("[-] 正在上传视频中...")
                except Error:
                    self.logger.info("[-] 正在上传视频中...")

                # 检查是否有上传错误
                if (
                    await page.locator("div.status-msg.error").count()
                    and await page.locator(
                        'div.media-status-content div.tag-inner:has-text("删除")'
                    ).count()
                ):
                    if retry_count < max_retries:
                        self.logger.error("[-] 发现上传出错了...准备重试")
                        await self._handle_upload_error(page)
                        retry_count += 1
                        self.logger.info(f"[-] 重试次数: {retry_count}")
                    else:
                        self.logger.error("[-] 上传错误超过最大重试次数")
                        return False

                await page.wait_for_timeout(1000)
                wait_time += 1

            except Exception as e:
                self.logger.error(f"[-] 等待上传完成时出错: {e}")
                await page.wait_for_timeout(1000)
                wait_time += 1

        self.logger.error("[-] 视频上传超时")
        return False

    async def _handle_upload_error(self, page: Page):
        """
        处理上传错误

        Args:
            page: 页面实例
        """
        self.logger.info("视频出错了，重新上传中")
        await page.locator(
            'div.media-status-content div.tag-inner:has-text("删除")'
        ).click()
        await page.get_by_role("button", name="删除", exact=True).click()
        file_input = page.locator('input[type="file"]')
        await file_input.set_input_files(self.file_path)

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
            self.logger.info(f"[-] 设置定时发布时间为: {publish_date}")

            # 点击定时选项
            label_element = page.locator("label").filter(has_text="定时").nth(1)
            await label_element.click()
            self.logger.info("[-] 已点击定时选项")

            # 打开日期选择器
            await page.click('input[placeholder="请选择发表时间"]')
            self.logger.info("[-] 已打开日期选择器")

            # 设置月份
            str_month = (
                str(publish_date.month)
                if publish_date.month > 9
                else "0" + str(publish_date.month)
            )
            current_month = str_month + "月"
            page_month = await page.inner_text(
                'span.weui-desktop-picker__panel__label:has-text("月")'
            )

            if page_month != current_month:
                await page.click("button.weui-desktop-btn__icon__right")
                self.logger.info(f"[-] 已将月份切换到: {current_month}")

            # 设置日期
            elements = await page.query_selector_all(
                "table.weui-desktop-picker__table a"
            )
            day_set = False
            for element in elements:
                if "weui-desktop-picker__disabled" in await element.evaluate(
                    "el => el.className"
                ):
                    continue
                text = await element.inner_text()
                if text.strip() == str(publish_date.day):
                    await element.click()
                    day_set = True
                    self.logger.info(f"[-] 已选择日期: {publish_date.day}")
                    break

            if not day_set:
                self.logger.error(f"[-] 无法找到日期: {publish_date.day}")
                return False

            # 设置时间
            await page.click('input[placeholder="请选择时间"]')
            await page.keyboard.press("Control+KeyA")
            # 格式化时间为HH:MM
            time_str = publish_date.strftime("%H:%M")
            await page.keyboard.type(time_str)
            await page.locator("div.input-editor").click()
            self.logger.info(f"[-] 已设置时间: {time_str}")

            self.logger.info("[+] 定时发布时间设置完成")
            return True

        except Exception as e:
            self.logger.error(f"[!] 设置定时发布时间时出错: {e}")
            return False

    async def _add_short_title(self, page: Page, title: str) -> bool:
        """
        添加短标题

        Args:
            page: 页面实例
            title: 视频标题

        Returns:
            是否成功添加短标题
        """
        try:
            short_title_element = (
                page.get_by_text("短标题", exact=True)
                .locator("..")
                .locator("xpath=following-sibling::div")
                .locator('span input[type="text"]')
            )
            if await short_title_element.count():
                short_title = _format_str_for_short_title(title)
                await short_title_element.fill(short_title)
                self.logger.info(f"[+] 已添加短标题: {short_title}")
            return True
        except Exception as e:
            self.logger.error(f"[!] 添加短标题时出错: {e}")
            return False

    async def _publish_video(self, page: Page, is_draft: bool = False) -> bool:
        """
        发布视频

        Args:
            page: 页面实例
            is_draft: 是否保存为草稿

        Returns:
            是否成功发布视频或保存草稿
        """
        max_retries = 10  # 最大重试次数
        retry_count = 0

        while retry_count < max_retries:
            try:
                if is_draft:
                    self.logger.info("[-] 正在保存为草稿...")
                    draft_button = page.locator(
                        'div.form-btns button:has-text("保存草稿")'
                    )
                    if await draft_button.count():
                        await draft_button.click()
                        self.logger.info("[-] 已点击保存草稿按钮")

                    try:
                        await page.wait_for_url("**/post/list**", timeout=5000)
                        self.logger.info("[+] 视频草稿保存成功")
                        return True
                    except Error:
                        # 检查当前URL是否包含成功标志
                        current_url = page.url
                        if "post/list" in current_url or "draft" in current_url:
                            self.logger.info("[+] 视频草稿保存成功")
                            return True

                        self.logger.debug(f"[-] 当前URL: {current_url}")
                        self.logger.debug("[-] 等待草稿保存完成...")

                else:
                    self.logger.info("[-] 正在发布视频...")
                    publish_button = page.locator(
                        'div.form-btns button:has-text("发表")'
                    )
                    if await publish_button.count():
                        await publish_button.click()
                        self.logger.info("[-] 已点击发表按钮")

                    try:
                        await page.wait_for_url(self.success_url_pattern, timeout=5000)
                        self.logger.info("[+] 视频发布成功")
                        return True
                    except Error:
                        # 检查当前URL是否包含成功标志
                        current_url = page.url
                        if self.success_url_pattern in current_url:
                            self.logger.info("[+] 视频发布成功")
                            return True

                        self.logger.debug(f"[-] 当前URL: {current_url}")
                        self.logger.debug("[-] 等待视频发布完成...")

            except Error as e:
                self.logger.warning(f"[!] 发布视频时出错: {e}")

                # 检查当前URL是否包含成功标志
                current_url = page.url
                if is_draft:
                    if "post/list" in current_url or "draft" in current_url:
                        self.logger.info("[+] 视频草稿保存成功")
                        return True
                else:
                    if self.success_url_pattern in current_url:
                        self.logger.info("[+] 视频发布成功")
                        return True

            await page.wait_for_timeout(1000)
            retry_count += 1

        self.logger.error("[!] 超过最大重试次数，视频发布失败")
        return False
