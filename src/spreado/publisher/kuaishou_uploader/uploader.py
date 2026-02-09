from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import Page, Error

from ...publisher.uploader import BaseUploader


class KuaiShouUploader(BaseUploader):
    """
    快手视频上传器
    """

    @property
    def platform_name(self) -> str:
        return "kuaishou"

    @property
    def login_url(self) -> str:
        return "https://passport.kuaishou.com/pc/account/login"

    @property
    def login_success_url(self) -> str:
        return "https://www.kuaishou.com/new-reco"

    @property
    def upload_url(self) -> str:
        return "https://cp.kuaishou.com/article/publish/video"

    @property
    def success_url_pattern(self) -> str:
        return "https://cp.kuaishou.com/article/manage/video?status=2&from=publish"

    @property
    def _login_selectors(self) -> List[str]:
        return ['text="立即登录"', 'text="扫码登录"', 'text="登录"', ".login-btn"]

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
        上传视频到快手

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

            self.logger.info(f"[+] 正在上传视频: {title}")

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

            # 发布视频
            if not await self._publish_video(page):
                self.logger.error("[!] 视频发布失败，终止上传流程")
                return False

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
            upload_button = page.locator("button[class^='_upload-btn']")
            await upload_button.wait_for(state="visible")

            async with page.expect_file_chooser() as fc_info:
                await upload_button.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(file_path)

            await page.wait_for_timeout(300)

            new_feature_button = page.get_by_role("button", name="Skip")
            if await new_feature_button.count() > 0:
                await new_feature_button.click()

            self.logger.info("[+] 视频文件上传成功")
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
        max_retries = 60
        retry_count = 0

        # 使用更精确的选择器和多种检测方法
        upload_complete_selectors = [
            "#work-description-edit",  # 视频信息编辑区域
            "div.upload-success",  # 上传成功标记
            "button.publish-btn:visible",  # 发布按钮可见
        ]

        while retry_count < max_retries:
            try:
                # 方法1: 检查"上传中"文本是否消失
                uploading_count = await page.locator("text=上传中").count()
                if uploading_count == 0:
                    # 方法2: 检查上传完成的标记是否出现
                    for selector in upload_complete_selectors:
                        try:
                            element = page.locator(selector)
                            if (
                                await element.count() > 0
                                and await element.first.is_visible()
                            ):
                                self.logger.info("[+] 视频上传完毕")
                                return True
                        except Error:
                            continue

                    # 如果"上传中"消失但其他标记未出现，继续等待
                    if retry_count % 10 == 0:
                        self.logger.info("[+] 正在上传视频中...")

                # 动态调整等待时间，减少资源占用
                if retry_count < 20:
                    await page.wait_for_timeout(500)  # 前20秒每秒检查一次
                else:
                    await page.wait_for_timeout(1000)  # 20秒后每2秒检查一次

            except Exception as e:
                self.logger.warning(f"[-] 检查上传状态时发生错误: {e}")
                await page.wait_for_timeout(1500)

            retry_count += 1

        if retry_count == max_retries:
            self.logger.warning("[-] 超过最大重试次数，视频上传可能未完成。")
            return False

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
            await page.locator("#work-description-edit").click()

            text_content = f"{title}\n{content}\n"
            await page.keyboard.type(text_content)

            added_tags_count = 0
            if tags:
                for tag in tags:
                    topic_name = tag.lstrip("#")

                    try:
                        # 优化shift+3输入#号
                        await page.keyboard.down("Shift")  # 按下 Shift
                        await page.keyboard.press("Digit3")  # 按下主键盘区的 3
                        await page.keyboard.up("Shift")  # 松开 Shift

                        # 减少等待时间
                        await page.wait_for_timeout(100)

                        # 减少输入延迟
                        await page.keyboard.type(topic_name, delay=50)

                        # 减少等待时间
                        await page.wait_for_timeout(500)

                        await page.keyboard.press("Enter")
                        added_tags_count += 1
                    except Exception as e:
                        self.logger.warning(f"[!] 添加标签 {topic_name} 失败: {e}")
                        # 标签添加失败不影响整体上传
                        continue

            self.logger.info(f"[+] 成功添加内容和Tag: {added_tags_count}/{len(tags)}")
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

        try:
            self.logger.info("[-] 正在设置视频封面...")

            # 等待封面设置按钮加载完成并可点击
            cover_setting_button = page.get_by_text("封面设置").nth(1)
            await cover_setting_button.wait_for(state="visible", timeout=10000)

            # 检查按钮是否可点击
            max_retries = 10
            retry_count = 0
            while retry_count < max_retries:
                if await cover_setting_button.is_enabled():
                    break
                await page.wait_for_timeout(500)
                retry_count += 1

            await cover_setting_button.click()

            # 等待封面设置模态框加载完成
            await page.wait_for_selector(
                "div.ant-modal-body:has(*:text('上传封面'))",
                timeout=10000,
                state="visible",
            )

            # 等待上传封面按钮加载完成并可点击
            upload_cover_button = page.get_by_text("上传封面")
            await upload_cover_button.wait_for(state="visible", timeout=10000)

            # 检查按钮是否可点击
            retry_count = 0
            while retry_count < max_retries:
                if await upload_cover_button.is_enabled():
                    break
                await page.wait_for_timeout(500)
                retry_count += 1

            await upload_cover_button.click()

            # 等待文件输入框加载完成 - 可能是隐藏的，所以使用attached状态
            file_input_selector = "div[class*='upload'] input[type='file']"
            await page.wait_for_selector(
                file_input_selector, timeout=10000, state="attached"
            )
            file_input = page.locator(file_input_selector)
            await file_input.set_input_files(thumbnail_path)
            self.logger.info("[+] 封面图片上传成功")

            # 获取第二个具有"封面设置"文本的元素
            cover_setting_element = page.get_by_text("封面设置").nth(1)
            await cover_setting_element.wait_for(state="visible", timeout=10000)

            # 获取该元素后的img元素
            cover_img_locator = cover_setting_element.locator(
                "xpath=following::img"
            ).first
            await cover_img_locator.wait_for(state="visible", timeout=10000)

            # 记录确认前的封面图片URL
            original_img_url = await cover_img_locator.get_attribute("src")
            if not original_img_url:
                self.logger.warning("[-] 获取原始封面图片URL失败")
                original_img_url = ""
            self.logger.info(f"[+] 原始封面图片URL: {original_img_url[:50]}...")

            # 等待确认按钮加载完成并可点击
            confirm_button = page.get_by_role("button", name="确认")
            await confirm_button.wait_for(state="visible", timeout=10000)

            # 检查按钮是否可点击
            retry_count = 0
            while retry_count < max_retries:
                if await confirm_button.is_enabled():
                    break
                await page.wait_for_timeout(500)
                retry_count += 1

            await confirm_button.click()

            # 通过检查封面图片URL是否变化来判断封面是否设置成功
            self.logger.info("[+] 等待封面图片URL变化...")

            # 等待封面图片URL变化
            max_url_checks = 20
            url_check_count = 0
            cover_set_success = False

            while url_check_count < max_url_checks:
                try:
                    current_img_url = await cover_img_locator.get_attribute("src")
                    if current_img_url:
                        self.logger.debug(
                            f"[+] 当前封面图片URL: {current_img_url[:50]}..."
                        )
                    else:
                        self.logger.debug("[+] 当前封面图片URL: None")

                    # 判断URL是否发生变化
                    if current_img_url and current_img_url != original_img_url:
                        self.logger.info("[+] 封面图片URL已变化，封面设置成功！")
                        cover_set_success = True
                        break

                    await page.wait_for_timeout(500)
                    url_check_count += 1
                except Exception as e:
                    self.logger.warning(f"[-] 检查封面图片URL时出错: {e}")
                    await page.wait_for_timeout(500)
                    url_check_count += 1

            if not cover_set_success:
                self.logger.warning("[-] 封面图片URL未发生变化，封面设置可能未成功")
                return False
            else:
                self.logger.info("[+] 封面设置成功！")
                return True

        except Exception as e:
            self.logger.error(f"[!] 设置封面时出错: {e}")
            return False

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
            publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(f"[+] 设置定时发布时间为: {publish_date_hour}")
            await page.locator("label:text('发布时间')").locator(
                "xpath=following-sibling::div"
            ).locator(".ant-radio-input").nth(1).click()
            await page.wait_for_selector(
                'div.ant-picker-input input[placeholder="选择日期时间"]',
                state="visible",
                timeout=5000,
            )

            await page.locator(
                'div.ant-picker-input input[placeholder="选择日期时间"]'
            ).click()
            await page.wait_for_selector(
                'div.ant-picker-input input[placeholder="选择日期时间"]:focus',
                state="visible",
                timeout=3000,
            )

            await page.keyboard.press("Control+KeyA")
            await page.keyboard.type(str(publish_date_hour))
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
        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            try:
                publish_button = page.get_by_text("发布", exact=True)
                if await publish_button.count() > 0:
                    await publish_button.click()
                    self.logger.info("[-] 已点击发布按钮")

                await page.wait_for_timeout(500)
                confirm_button = page.get_by_text("确认发布")
                if await confirm_button.count() > 0:
                    await confirm_button.click()
                    self.logger.info("[-] 已点击确认发布按钮")

                try:
                    await page.wait_for_url(self.success_url_pattern, timeout=5000)
                    self.logger.info("[+] 视频发布成功，已跳转到管理页面")
                    return True
                except Error:
                    # 如果没有跳转，检查当前页面URL是否包含成功标志
                    current_url = page.url
                    if self.success_url_pattern in current_url:
                        self.logger.info("[+] 视频发布成功")
                        return True

                    self.logger.debug(f"[-] 当前URL: {current_url}")
                    self.logger.debug("[-] 等待视频发布完成...")

            except Error as e:
                self.logger.warning(f"[!] 发布视频时出错: {e}")

            await page.wait_for_timeout(1000)
            retry_count += 1

        self.logger.error("[!] 超过最大重试次数，视频发布失败")
        return False
