from datetime import datetime
from pathlib import Path
from typing import List, Optional
import re

from playwright.async_api import Page, Error
from spreado.core.base_publisher import BasePublisher


class DouYinUploader(BasePublisher):
    """
    抖音视频上传器
    """

    @property
    def platform_name(self) -> str:
        return "douyin"

    @property
    def display_name(self) -> str:
        return "抖音"

    @property
    def login_url(self) -> str:
        return "https://creator.douyin.com/"

    @property
    def publish_url(self) -> str:
        return "https://creator.douyin.com/creator-micro/content/upload"

    @property
    def _login_selectors(self) -> List[str]:
        return ['text="手机号登录"', 'text="扫码登录"', 'text="登录"', ".login-btn"]

    @property
    def _authed_selectors(self) -> List[str]:
        return [
            "div[class^='container']",
            "div[class*='upload']",
            "input[placeholder*='作品标题']",
            "div.semi-upload",
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

                with self.logger.step("set_third_party_platforms"):
                    if not await self._set_third_party_platforms(page):
                        return False

                if publish_date:
                    with self.logger.step(
                        "set_schedule_time", at=publish_date.isoformat()
                    ):
                        if not await self._set_schedule_time(page, publish_date):
                            return False

                with self.logger.step("handle_auto_video_cover"):
                    if not await self._handle_auto_video_cover(page):
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
            inp = page.locator("input[type='file'][accept*='video']").first
            if await inp.count() == 0:
                inp = page.locator("div[class^='container'] input[type='file']").first
            await inp.wait_for(state="attached", timeout=10000)
            await inp.set_input_files(file_path)
            return True
        except Exception as e:
            self.logger.error("视频文件注入失败", reason=str(e)[:200])
            return False

    async def _wait_for_upload_complete(self, page: Page) -> bool:
        """轮询直到视频上传完成：出现标题输入框或预览区。"""

        async def check() -> bool:
            # 标题输入框出现 = 上传完成
            title_input = page.locator("input[placeholder*='填写作品标题']").first
            if await title_input.count() > 0 and await title_input.is_visible():
                return True
            # 预览区出现
            for sel in [
                'div[class^="preview-button"]',
                'div[class*="preview"]',
                'div[class*="video-content"]',
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            # 成功文案
            for txt in ["上传成功", "已上传"]:
                if await page.locator(f"text={txt}").count() > 0:
                    return True
            # 进度条存在 = 仍在传输中
            for sel in [
                'div[class*="progress"]',
                'div[class*="uploading"]',
                'div[class*="loading"]',
            ]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return False
            # 编辑区出现也视为完成
            for sel in ["div.zone-container", ".notranslate"]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    return True
            return False

        return await self._wait_for_condition(
            check, timeout=120.0, interval=1.5, desc="upload_complete"
        )

    async def _fill_video_info(
        self,
        page: Page,
        title: str = "",
        content: str = "",
        tags: List[str] = None,
    ) -> bool:
        try:
            await page.wait_for_selector(
                "input[placeholder*='填写作品标题']", state="visible", timeout=15000
            )

            # 填写标题
            title_input = page.locator("input[placeholder*='填写作品标题']").first
            if await title_input.count() > 0:
                await title_input.fill(title[:30])
            else:
                # 备选：通过 .notranslate 定位
                fallback = page.locator(".notranslate").first
                if await fallback.count() > 0:
                    await fallback.click()
                    await page.keyboard.press("Control+KeyA")
                    await page.keyboard.insert_text(title[:30])

            # 填写描述
            desc = page.locator(".zone-container").first
            if await desc.count() > 0:
                await desc.click()
                if content:
                    await desc.fill(content)

            # 填写标签
            added = 0
            for tag in tags or []:
                clean_tag = tag.lstrip("#")
                try:
                    await desc.focus()
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(200)
                    await page.keyboard.insert_text(f" #{clean_tag} ")
                    await page.wait_for_timeout(300)
                    await page.keyboard.press("Enter")
                    added += 1
                except Exception as e:
                    self.logger.warning(
                        "标签添加失败", tag=clean_tag, reason=str(e)[:100]
                    )
                await page.wait_for_timeout(200)

            self.logger.info("标题与标签已填充", added=added, total=len(tags or []))
            return True
        except Exception as e:
            self.logger.error("填写视频信息失败", reason=str(e)[:200])
            return False

    async def _set_thumbnail(
        self,
        page: Page,
        thumbnail_path: Optional[str | Path],
    ) -> bool:
        if not thumbnail_path:
            self.logger.info("未指定封面，跳过")
            return True
        if not Path(thumbnail_path).exists():
            self.logger.warning("封面文件不存在，跳过", path=str(thumbnail_path))
            return True

        try:
            # 1) 点击"选择封面"按钮
            if not await self._click_first_visible(
                page,
                [
                    'text="选择封面"',
                    'button:has-text("选择封面")',
                    'div[class*="cover"]',
                ],
                force=True,
                timeout=3000,
            ):
                self.logger.warning("未找到封面设置按钮，跳过")
                return True

            # 2) 等待封面弹窗
            try:
                await page.wait_for_selector(
                    "div.dy-creator-content-modal", timeout=10000
                )
            except Error:
                self.logger.warning("封面弹窗未出现，跳过")
                return True

            # 3) 设置竖封面
            await self._click_first_visible(
                page, ['text="设置竖封面"'], force=True, timeout=2000
            )

            # 4) 上传封面图片
            upload_selectors = [
                "div[class^='semi-upload upload'] input.semi-upload-hidden-input",
                "input[type='file'][accept*='image']",
            ]
            if not await self._upload_file_to_first(
                page, upload_selectors, thumbnail_path, timeout=10000
            ):
                self.logger.error("未找到封面图片上传 input")
                return False

            await page.wait_for_timeout(2000)

            # 5) 点击完成
            if await self._click_first_visible(
                page, ['button:visible:has-text("完成")'], force=True, timeout=3000
            ):
                await page.wait_for_selector("div.extractFooter", state="detached")
                self.logger.info("封面设置完成")
                return True

            self.logger.error("未能点击完成按钮")
            return False
        except Exception as e:
            self.logger.error("封面设置失败", reason=str(e)[:200])
            return True  # 封面失败不影响发布

    async def _set_schedule_time(self, page: Page, publish_date: datetime) -> bool:
        try:
            await page.locator("[class^='radio']:has-text('定时发布')").click()
            await page.wait_for_selector(
                '.semi-input[placeholder="日期和时间"]', state="visible", timeout=5000
            )
            time_str = publish_date.strftime("%Y-%m-%d %H:%M")
            inp = page.locator('.semi-input[placeholder="日期和时间"]')
            await inp.click()
            await page.keyboard.press("Control+KeyA")
            await page.keyboard.insert_text(time_str)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            self.logger.info("定时发布时间设置完成")
            return True
        except Exception as e:
            self.logger.error("定时发布设置失败", reason=str(e)[:200])
            return False

    async def _set_third_party_platforms(self, page: Page) -> bool:
        """关闭第三方平台同步开关。"""
        try:
            switch = page.locator(
                '[class^="info"] > [class^="first-part"] div div.semi-switch'
            )
            if await switch.count() > 0:
                is_checked = "semi-switch-checked" in (
                    await switch.evaluate("el => el.className")
                )
                if not is_checked:
                    await switch.locator("input.semi-switch-native-control").click()
            return True
        except Exception as e:
            self.logger.error("第三方平台设置失败", reason=str(e)[:100])
            return True  # 不影响整体上传

    async def _handle_auto_video_cover(self, page: Page) -> bool:
        """处理必须设置封面的情况：选择推荐封面并确认。"""
        try:
            if not await page.get_by_text("请设置封面后再发布").first.is_visible():
                return True

            recommend_cover = page.locator('[class^="recommendCover-"]').first
            if await recommend_cover.count() == 0:
                return True

            await recommend_cover.click()
            await page.wait_for_timeout(500)

            # 确认弹窗
            if await page.get_by_text("是否确认应用此封面？").first.is_visible():
                await page.get_by_role("button", name="确定").click()
                await page.wait_for_timeout(500)
            return True
        except Exception as e:
            self.logger.error("自动封面设置失败", reason=str(e)[:200])
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
            self.logger.info(f"成功设置地理位置: {location}")
            return True
        except Exception as e:
            self.logger.error(f"设置地理位置时出错: {e}")
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
                self.logger.error("未找到标签下拉框")
                return False

            self.logger.debug("找到标签下拉框，准备选择'购物车'")
            await dropdown.click()
            await page.wait_for_selector('[role="listbox"]', timeout=5000)
            await page.locator('[role="option"]:has-text("购物车")').click()
            self.logger.debug("成功选择'购物车'")

            await page.wait_for_selector(
                'input[placeholder="粘贴商品链接"]', timeout=5000
            )
            input_field = page.locator('input[placeholder="粘贴商品链接"]')
            await input_field.fill(product_link)
            self.logger.debug(f"已输入商品链接: {product_link}")

            add_button = page.locator('span:has-text("添加链接")')
            button_class = await add_button.get_attribute("class")
            if "disable" in button_class:
                self.logger.error("'添加链接'按钮不可用")
                return False

            await add_button.click()
            self.logger.debug("成功点击'添加链接'按钮")
            await page.wait_for_timeout(2000)

            error_modal = page.locator("text=未搜索到对应商品")
            if await error_modal.count():
                confirm_button = page.locator('button:has-text("确定")')
                await confirm_button.click()
                self.logger.error("商品链接无效")
                return False

            if not await self._handle_product_dialog(page, product_title):
                return False

            self.logger.debug("成功设置商品链接")
            return True

        except Exception as e:
            self.logger.error(f"设置商品链接时出错: {str(e)}")
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
            self.logger.error("未找到商品短标题输入框")
            return False

        product_title = product_title[:10]
        await short_title_input.fill(product_title)
        await page.wait_for_timeout(1000)

        finish_button = page.locator('button:has-text("完成编辑")')
        if "disabled" not in await finish_button.get_attribute("class"):
            await finish_button.click()
            self.logger.debug("成功点击'完成编辑'按钮")
            await page.wait_for_selector(
                ".semi-modal-content", state="hidden", timeout=5000
            )
            return True
        else:
            self.logger.error("'完成编辑'按钮处于禁用状态，尝试直接关闭对话框")
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
        try:
            publish_button = page.get_by_role("button", name="发布", exact=True)
            if await publish_button.count() == 0:
                publish_button = page.locator('button:has-text("发布")').first
            if await publish_button.count() == 0:
                self.logger.error("未找到发布按钮")
                return False
            return await self._click_and_wait_for_url(
                page,
                publish_button,
                re.compile(r"/content/manage\?enter_from=publish"),
                timeout=30000,
            )
        except Error as e:
            self.logger.error("发布失败", reason=str(e)[:200])
            return False
