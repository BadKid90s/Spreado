from datetime import datetime
from pathlib import Path
from typing import List, Optional
import re

from playwright.async_api import Page, Error

from spreado.core.base_publisher import BasePublisher
from spreado.core.browser import StealthBrowser


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
    def supported_content_types(self) -> List[str]:
        return ["video", "image_text"]

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

    # ---------------------------------------------------------------- 图文发布

    async def _switch_to_image_text_tab(self, page: Page) -> bool:
        """点击"上传图文"标签切换到图文发布模式。"""
        try:
            # 等待 tabs 渲染
            try:
                await page.wait_for_selector(
                    ".ant-tabs-tab-btn", state="visible", timeout=10000
                )
            except Error:
                pass

            # 方式1：Playwright locator
            tab = page.locator('.ant-tabs-tab-btn:has-text("图文")').first
            if await tab.count() > 0:
                await tab.click(force=True)
                await page.wait_for_timeout(500)
                return True

            # 方式2：JS evaluate
            clicked = await page.evaluate("""
() => {
    const tabs = document.querySelectorAll('.ant-tabs-tab-btn');
    for (const t of tabs) {
        if (t.innerText.includes('图文')) { t.click(); return true; }
    }
    return false;
}
""")
            if clicked:
                await page.wait_for_timeout(500)
            return clicked
        except Exception:
            return False

    async def _upload_images(self, page: Page, image_paths: List[str | Path]) -> bool:
        """上传多张图片到图文编辑器（通过"上传图片"按钮触发 file chooser）。"""
        try:
            upload_btn = page.locator('button:has-text("上传图片")')
            if await upload_btn.count() == 0:
                upload_btn = page.locator('[class*="upload-btn"]:has-text("图片")')

            if await upload_btn.count() > 0:
                await upload_btn.wait_for(state="visible", timeout=10000)
                async with page.expect_file_chooser(timeout=5000) as fc_info:
                    await upload_btn.click(force=True)
                file_chooser = await fc_info.value
                files = [str(Path(p).resolve()) for p in image_paths]
                await file_chooser.set_files(files)
                self.logger.info("图片已上传", count=len(files))
                return True

            # 备选：直接注入
            img_input = page.locator('input[type="file"][accept*="image"]').first
            if await img_input.count() > 0:
                files = [str(Path(p).resolve()) for p in image_paths]
                await img_input.set_input_files(files)
                self.logger.info("图片文件已注入", count=len(files))
                return True

            self.logger.error("未找到图片上传入口")
            return False
        except Exception as e:
            self.logger.error("图片上传失败", reason=str(e)[:200])
            return False

    async def _wait_for_image_upload_complete(self, page: Page) -> bool:
        """等待图片上传完成：编辑器出现。"""
        async def check() -> bool:
            editor = page.locator("#work-description-edit")
            if await editor.count() > 0 and await editor.first.is_visible():
                return True
            return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=2.0, desc="image_upload_complete"
        )

    async def _upload_image_text(
        self,
        page: Page,
        image_paths: List[str | Path],
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
    ) -> bool:
        """图文发布主流程。"""
        try:
            with self.logger.step(
                "upload_image_text", title=title, images=str(len(image_paths))
            ):
                with self.logger.step("goto_upload_page"):
                    await page.goto(self.publish_url)
                    try:
                        await page.wait_for_url(self.publish_url, timeout=5000)
                    except Error:
                        pass

                with self.logger.step("switch_to_image_text_tab"):
                    if not await self._switch_to_image_text_tab(page):
                        raise RuntimeError("无法切换到图文发布标签")

                with self.logger.step("upload_images", count=len(image_paths)):
                    if not await self._upload_images(page, image_paths):
                        return False

                with self.logger.step("wait_for_upload_complete"):
                    if not await self._wait_for_image_upload_complete(page):
                        return False

                with self.logger.step("fill_video_info", title=title):
                    if not await self._fill_video_info(page, title, content, tags):
                        return False

                with self.logger.step(
                    "set_thumbnail", path=str(thumbnail_path or "")
                ):
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
            self.logger.error("upload_image_text 异常", reason=str(e)[:200])
            return False

    async def publish_image_text(self, task) -> bool:
        """基于 Task 模型发布图文。"""
        if not task.media_files:
            self.logger.error("任务缺少图片文件")
            return False

        return await self._login_and_upload_image_text(
            image_paths=task.media_files,
            title=task.title,
            content=task.content,
            tags=task.tags,
            publish_date=task.publish_date,
            thumbnail_path=task.thumbnail_path,
        )

    async def _login_and_upload_image_text(
        self,
        image_paths: List[str | Path],
        title: str = "",
        content: str = "",
        tags: List[str] = None,
        publish_date: Optional[datetime] = None,
        thumbnail_path: Optional[str | Path] = None,
    ) -> bool:
        """登录 + 图文上传（同一浏览器，解决 fingerprint 兼容）。"""
        cookie_ok = await self.verify_cookie_flow(auto_login=False)
        if cookie_ok:
            async with await StealthBrowser.create(
                headless=True
            ) as browser:
                await browser.load_cookies_from_file(self.cookie_file_path)
                async with await browser.new_page() as page:
                    return await self._upload_image_text(
                        page=page,
                        image_paths=image_paths,
                        title=title,
                        content=content,
                        tags=tags,
                        publish_date=publish_date,
                        thumbnail_path=thumbnail_path,
                    )

        # cookie 无效，登录并上传
        self.logger.info("cookie 无效，启动登录流程")
        try:
            async with await StealthBrowser.create(
                headless=False, channel=self._browser_channel
            ) as browser:
                page = await browser.new_page()
                await page.goto(self.login_url)
                self.logger.info("等待用户在浏览器内完成登录…")
                if not await self._wait_for_login(page, timeout=120.0):
                    raise RuntimeError("登录超时")
                self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
                await page.context.storage_state(path=self.cookie_file_path)
                self.logger.info("cookie 已保存")
                await page.goto(self.publish_url)
                await page.wait_for_timeout(3000)
                if await self._check_login_required(page):
                    raise RuntimeError("登录后发布页仍要求登录")
                return await self._upload_image_text(
                    page=page,
                    image_paths=image_paths,
                    title=title,
                    content=content,
                    tags=tags,
                    publish_date=publish_date,
                    thumbnail_path=thumbnail_path,
                )
        except Exception as e:
            self.logger.error("登录并上传图文失败", reason=str(e)[:200])
            return False

    # ---------------------------------------------------------------- 视频发布

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
            # 先等 upload 区域挂载（CI headless 下页面渲染较慢）
            try:
                await page.wait_for_selector(
                    "button[class*='upload'], div[class*='upload'], input[type='file']",
                    state="attached",
                    timeout=15000,
                )
            except Error:
                pass

            # 依次尝试多个上传按钮选择器，每个超时 3s
            btn_selectors = [
                "button[class^='_upload-btn']",
                "button[class*='upload-btn']",
                "button[class*='upload']",
                "div[class*='upload'] button",
                ".ant-upload button",
            ]
            upload_button = None
            for sel in btn_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        await btn.wait_for(state="visible", timeout=3000)
                        upload_button = btn
                        break
                except Error:
                    continue

            if upload_button:
                try:
                    async with page.expect_file_chooser(timeout=5000) as fc_info:
                        await upload_button.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(file_path)
                except Error:
                    # file chooser 未触发，降级到直注入
                    upload_button = None

            if upload_button is None:
                # 降级：直接向隐藏 file input 注入文件
                file_input_selectors = [
                    "input[type='file'][accept*='video']",
                    "input[type='file']",
                    "div[class*='upload'] input[type='file']",
                ]
                if not await self._upload_file_to_first(
                    page, file_input_selectors, file_path, timeout=15000
                ):
                    self.logger.error("未找到上传入口（按钮及 file input 均未命中）")
                    return False

            await page.wait_for_timeout(300)
            skip_btn = page.get_by_role("button", name="Skip")
            if await skip_btn.count() > 0:
                await skip_btn.click()

            self.logger.info("视频文件上传成功")
            return True
        except Exception as e:
            self.logger.error(f"上传视频文件时出错: {e}")
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
                        self.logger.warning(f"添加标签 {topic_name} 失败: {e}")
                        # 标签添加失败不影响整体上传
                        continue

            self.logger.info(f"成功添加内容和Tag: {added_tags_count}/{len(tags or [])}")
            return True
        except Exception as e:
            self.logger.error(f"填写视频信息时出错: {e}")
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
            self.logger.info("未指定封面路径，跳过封面设置")
            return True

        if not Path(thumbnail_path).exists():
            self.logger.warning(f"封面文件不存在: {thumbnail_path}，跳过封面设置")
            return True

        try:
            self.logger.info("正在设置视频封面...")

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
            self.logger.info("封面图片上传成功")

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
                self.logger.warning("获取原始封面图片URL失败")
                original_img_url = ""
            self.logger.info(f"原始封面图片URL: {original_img_url[:50]}...")

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
            self.logger.info("等待封面图片URL变化...")

            # 等待封面图片URL变化
            max_url_checks = 20
            url_check_count = 0
            cover_set_success = False

            while url_check_count < max_url_checks:
                try:
                    current_img_url = await cover_img_locator.get_attribute("src")
                    if current_img_url:
                        self.logger.debug(f"当前封面图片URL: {current_img_url[:50]}...")
                    else:
                        self.logger.debug("当前封面图片URL: None")

                    # 判断URL是否发生变化
                    if current_img_url and current_img_url != original_img_url:
                        self.logger.info("封面图片URL已变化，封面设置成功！")
                        cover_set_success = True
                        break

                    await page.wait_for_timeout(500)
                    url_check_count += 1
                except Exception as e:
                    self.logger.warning(f"检查封面图片URL时出错: {e}")
                    await page.wait_for_timeout(500)
                    url_check_count += 1

            if not cover_set_success:
                self.logger.warning("封面图片URL未发生变化，封面设置可能未成功")
                return False
            else:
                self.logger.info("封面设置成功！")
                return True

        except Exception as e:
            self.logger.error(f"设置封面时出错: {e}")
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
            self.logger.info(f"设置定时发布时间为: {publish_date_hour}")
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

            self.logger.info("定时发布时间设置完成")
            return True
        except Exception as e:
            self.logger.error(f"设置定时发布时间时出错: {e}")
            return False

    async def _publish_video(self, page: Page) -> bool:
        success_pattern = re.compile(r"/article/manage/video\?.*from=publish")
        try:
            # "发布"是自定义 div，用 JS click 最可靠
            clicked = await page.evaluate("""
() => {
    const btns = document.querySelectorAll('[class*="_button-primary"]');
    for (const b of btns) {
        if (b.innerText && b.innerText.includes('发布')) { b.click(); return true; }
    }
    return false;
}
""")
            if not clicked:
                self.logger.error("未找到发布按钮")
                return False
            await page.wait_for_timeout(1500)

            # 处理"确认发布"弹窗
            confirm_btn = page.locator(
                'button:has-text("确认发布"), div:has-text("确认发布")'
            ).first
            try:
                await confirm_btn.wait_for(state="visible", timeout=5000)
            except Error:
                pass
            if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
                return await self._click_and_wait_for_url(
                    page, confirm_btn, success_pattern, timeout=15000
                )

            # 无确认弹窗 = 直接发布成功，等待跳转
            try:
                await page.wait_for_url(success_pattern, timeout=10000)
                return True
            except Error:
                pass

            if success_pattern.search(page.url):
                return True

            self.logger.error("发布未跳转到管理页", url=page.url[:80])
            return False
        except Exception as e:
            self.logger.error("发布失败", reason=str(e)[:200])
            return False
