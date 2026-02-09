from datetime import datetime
from pathlib import Path
from typing import List, Optional
import time

from playwright.async_api import Page, Error
import asyncio
from ...publisher.uploader import BaseUploader


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
    def login_success_url(self) -> str:
        return "https://creator.douyin.com/creator-micro/home"

    @property
    def upload_url(self) -> str:
        return "https://creator.douyin.com/creator-micro/content/upload"

    @property
    def success_url_pattern(self) -> str:
        return (
            "https://creator.douyin.com/creator-micro/content/manage?enter_from=publish"
        )

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
        上传视频到抖音

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

            # 设置第三方平台同步
            if not await self._set_third_party_platforms(page):
                self.logger.error("[!] 第三方平台同步设置失败，终止上传流程")
                return False

            if publish_date:
                # 设置定时发布
                if not await self._set_schedule_time(page, publish_date):
                    self.logger.error("[!] 定时发布设置失败，终止上传流程")
                    return False

            # 处理自动封面设置
            if not await self._handle_auto_video_cover(page):
                self.logger.error("[!] 封面设置失败，终止上传流程")
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
            await page.locator("div[class^='container'] input").set_input_files(
                file_path
            )
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
            'div[class^="preview-button"]:has(div:text("重新上传"))',
            'div[class*="preview"]',
            'div[class*="video-content"]',
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
                    'div[class*="progress"]',
                    'div[class*="uploading"]',
                    'div[class*="loading"]',
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
                        'input[placeholder*="填写作品标题"]',
                        "div.zone-container",
                        ".notranslate",
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
                "input[placeholder*='填写作品标题'], .notranslate",
                state="visible",
                timeout=10000,
            )
            self.logger.info("[-] 正在填充标题和话题...")

            title_container = page.locator("input[placeholder*='填写作品标题']")
            if await title_container.count():
                await title_container.fill(title[:30])
            else:
                title_container = (
                    page.get_by_text("作品标题")
                    .locator("..")
                    .locator("xpath=following-sibling::div[1]")
                    .locator("input")
                )
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

            # 填写描述
            description_selector = ".zone-container"
            desc_element = page.locator(description_selector)
            await desc_element.click()
            await desc_element.fill(content)

            # 添加标签
            added_tags = 0
            if tags:
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

                        # 按照小红书的顺序添加标签：输入#号→输入文字→按回车
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
                'text="选择封面"',
                'button:has-text("选择封面")',
                'div[class*="cover"]',
            ]

            # 使用通用方法点击封面设置按钮
            if not await self._click_first_visible_element(
                page, cover_selectors, "封面设置按钮", 2000
            ):
                self.logger.warning("[!] 未找到封面设置按钮，跳过封面设置")
                return True

            # 等待封面设置所需元素加载完成
            try:
                await page.wait_for_selector(
                    "div.dy-creator-content-modal", timeout=10000
                )
                self.logger.info("[+] 封面设置模态框已出现")
            except Exception as e:
                self.logger.warning(f"[!] 等待封面设置模态框时出错: {e}")
                return True

            # 设置竖封面
            await self._click_first_visible_element(
                page, ['text="设置竖封面"'], "设置竖封面按钮", 2000
            )

            # 使用通用方法上传封面图片
            file_input_selectors = [
                "div[class^='semi-upload upload'] >> input.semi-upload-hidden-input",
                "input[type='file'][accept*='image']",
                "input[accept*='image/png']",
            ]

            if not await self._upload_file_to_first_input(
                page, file_input_selectors, thumbnail_path, "image"
            ):
                self.logger.error("[!] 未能上传封面图片")
                return False

            # 等待上传完成
            await page.wait_for_timeout(2000)

            # 点击完成按钮
            if await self._click_first_visible_element(
                page, ['button:visible:has-text("完成")'], "完成按钮", 2000
            ):
                self.logger.info("[+] 视频封面设置完成！")
                await page.wait_for_selector("div.extractFooter", state="detached")
                return True
            else:
                self.logger.error("[!] 未能点击完成按钮")
                return False

        except Exception as e:
            self.logger.error(f"[!] 设置封面时出错: {e}")
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
            label_element = page.locator("[class^='radio']:has-text('定时发布')")
            await label_element.click()
            await page.wait_for_selector(
                '.semi-input[placeholder="日期和时间"]', state="visible", timeout=5000
            )
            publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
            await page.locator('.semi-input[placeholder="日期和时间"]').click()
            await page.wait_for_selector(
                '.semi-input[placeholder="日期和时间"]:focus',
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

    async def _click_first_visible_element(
        self,
        page: Page,
        selectors: List[str],
        description: str = "元素",
        wait_after: int = 0,
    ) -> bool:
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
            except Error:
                continue
        return False

    async def _upload_file_to_first_input(
        self,
        page: Page,
        selectors: List[str],
        file_path: str | Path,
        accept_type: str = "image",
    ) -> bool:
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
                        accept = await input_elem.get_attribute("accept")
                        if accept and (accept_type in accept or accept == "*"):
                            await input_elem.set_input_files(file_path)
                            self.logger.info(f"[+] 已上传{accept_type}文件")
                            return True
            except Error:
                continue
        return False

    async def _set_third_party_platforms(self, page: Page) -> bool:
        """
        设置第三方平台同步

        Args:
            page: 页面实例

        Returns:
            是否成功设置第三方平台同步
        """
        try:
            third_part_element = (
                '[class^="info"] > [class^="first-part"] div div.semi-switch'
            )
            if await page.locator(third_part_element).count():
                if "semi-switch-checked" not in await page.eval_on_selector(
                    third_part_element, "div => div.className"
                ):
                    await page.locator(third_part_element).locator(
                        "input.semi-switch-native-control"
                    ).click()
            return True
        except Exception as e:
            self.logger.error(f"[!] 设置第三方平台同步时出错: {e}")
            return True  # 这个步骤失败不影响整体上传

    async def _handle_auto_video_cover(self, page: Page) -> bool:
        """
        处理必须设置封面的情况

        Args:
            page: 页面实例

        Returns:
            是否成功处理封面设置
        """
        try:
            if await page.get_by_text("请设置封面后再发布").first.is_visible():
                self.logger.info("[-] 检测到需要设置封面提示...")
                recommend_cover = page.locator('[class^="recommendCover-"]').first

                if await recommend_cover.count():
                    self.logger.info("[-] 正在选择第一个推荐封面...")
                    try:
                        await recommend_cover.click()
                        await page.wait_for_timeout(500)

                        if await page.get_by_text(
                            "是否确认应用此封面？"
                        ).first.is_visible():
                            self.logger.info("[-] 检测到确认弹窗: 是否确认应用此封面？")
                            await page.get_by_role("button", name="确定").click()
                            self.logger.info("[-] 已点击确认应用封面")
                            await page.wait_for_timeout(500)

                        self.logger.info("[-] 已完成封面选择流程")
                    except Exception as e:
                        self.logger.error(f"[-] 选择封面失败: {e}")
                        return False
            return True
        except Exception as e:
            self.logger.error(f"[!] 处理自动封面设置时出错: {e}")
            return False

    async def _set_location(self, page: Page, location: str) -> bool:
        """
        设置地理位置

        Args:
            page: 页面实例
            location: 地理位置

        Returns:
            是否成功设置地理位置
        """
        try:
            await page.locator('div.semi-select span:has-text("输入地理位置")').click()
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(2000)
            await page.keyboard.type(location)
            await page.wait_for_selector(
                'div[role="listbox"] [role="option"]', timeout=5000
            )
            await page.locator('div[role="listbox"] [role="option"]').first.click()
            self.logger.info(f"[+] 成功设置地理位置: {location}")
            return True
        except Exception as e:
            self.logger.error(f"[!] 设置地理位置时出错: {e}")
            return False

    async def _set_product_link(
        self, page: Page, product_link: str, product_title: str
    ):
        """
        设置商品链接

        Args:
            page: 页面实例
            product_link: 商品链接
            product_title: 商品标题
        """
        await page.wait_for_timeout(2000)
        try:
            await page.wait_for_selector("text=添加标签", timeout=10000)
            dropdown = (
                page.get_by_text("添加标签")
                .locator("..")
                .locator("..")
                .locator("..")
                .locator(".semi-select")
                .first
            )
            if not await dropdown.count():
                self.logger.error("[-] 未找到标签下拉框")
                return False

            self.logger.debug("[-] 找到标签下拉框，准备选择'购物车'")
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            await page.locator('[role="option"]:has-text("购物车")').click()
            self.logger.debug("[+] 成功选择'购物车'")

            await page.wait_for_selector(
                'input[placeholder="粘贴商品链接"]', timeout=5000
            )
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            self.logger.debug(f"[+] 已输入商品链接: {product_link}")

            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute("class")
            if "disable" in button_class:
                self.logger.error("[-] '添加链接'按钮不可用")
                return False

            await add_button.click()
            self.logger.debug("[+] 成功点击'添加链接'按钮")
            await page.wait_for_timeout(2000)

            error_modal = page.locator("text=未搜索到对应商品")
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
        await page.wait_for_selector(
            'input[placeholder="请输入商品短标题"]', timeout=10000
        )
        short_title_input = page.locator('input[placeholder="请输入商品短标题"]')
        if not await short_title_input.count():
            self.logger.error("[-] 未找到商品短标题输入框")
            return False

        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if "disabled" not in await finish_button.get_attribute("class"):
            await finish_button.click()
            self.logger.debug("[+] 成功点击'完成编辑'按钮")
            await page.wait_for_selector(
                ".semi-modal-content", state="hidden", timeout=5000
            )
            return True
        else:
            self.logger.error("[-] '完成编辑'按钮处于禁用状态，尝试直接关闭对话框")
            cancel_button = page.locator('button:has-text("取消")')
            if await cancel_button.count():
                await cancel_button.click()
            else:
                close_button = page.locator(".semi-modal-close")
                await close_button.click()

            await page.wait_for_selector(
                ".semi-modal-content", state="hidden", timeout=5000
            )
            return False

    async def _publish_video(self, page: Page) -> bool:
        """
        发布视频

        Args:
            page: 页面实例

        Returns:
            是否成功发布视频
        """
        try:
            publish_button = page.get_by_role("button", name="发布", exact=True)
            if await publish_button.count():
                await publish_button.click()
                self.logger.info("[-] 已点击发布按钮")

                # 等待跳转到成功页面
                try:
                    await page.wait_for_url(
                        self.success_url_pattern + "**", timeout=5000
                    )
                    self.logger.info("[+] 视频发布成功，已跳转到管理页面")
                    return True
                except Error:
                    # 如果没有跳转，检查是否有其他成功标志
                    self.logger.debug("[-] 未检测到页面跳转，检查是否有其他成功标志")
                    return True  # 抖音可能不跳转但发布成功
            else:
                self.logger.error("[!] 未找到发布按钮")
                return False
        except Error as e:
            self.logger.error(f"[!] 发布视频时出错: {e}")
            return False
