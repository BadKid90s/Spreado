# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List

from anyio import Path
from playwright.async_api import Playwright, async_playwright
import os
import asyncio
import platform

from conf import LOCAL_CHROME_HEADLESS
from utils.base_social_media import set_init_script
from utils.files_times import get_absolute_path
from utils.log import kuaishou_logger


def get_chrome_path():
    """自动检测本地Chrome浏览器路径
    支持Windows、macOS和Linux系统
    返回Chrome可执行文件路径或None
    """
    system = platform.system()

    if system == "Windows":
        # Windows系统Chrome路径
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    elif system == "Darwin":  # macOS
        # macOS系统Chrome路径
        possible_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    elif system == "Linux":
        # Linux系统Chrome路径
        possible_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/opt/google/chrome/chrome"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    return None


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        # 获取Chrome浏览器路径
        chrome_path = get_chrome_path()
        if chrome_path:
            browser = await playwright.chromium.launch(headless=LOCAL_CHROME_HEADLESS, executable_path=chrome_path)
        else:
            browser = await playwright.chromium.launch(headless=LOCAL_CHROME_HEADLESS)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        try:
            await page.wait_for_selector("div.names div.container div.name:text('机构服务')", timeout=5000)  # 等待5秒

            kuaishou_logger.info("[+] 等待5秒 cookie 失效")
            return False
        except:
            kuaishou_logger.success("[+] cookie 有效")
            return True


async def kuaishou_setup(account_file, handle=False):
    account_file = get_absolute_path(account_file, "kuaishou_uploader")
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            return False
        kuaishou_logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录，登陆后会自动生成cookie文件')
        await get_kuaishou_cookie(account_file)
    return True


async def get_kuaishou_cookie(account_file):
    url_changed_event = asyncio.Event()

    async def on_url_change():
        # 检查是否是主框架的变化
        if page.url != original_url:
            url_changed_event.set()

    async with async_playwright() as playwright:
        options = {
            'args': [
                '--lang en-GB'
            ],
            'headless': LOCAL_CHROME_HEADLESS,  # Set headless option here
        }
        # 获取Chrome浏览器路径
        chrome_path = get_chrome_path()
        if chrome_path:
            kuaishou_logger.info(f'[+] 使用自动检测到的Chrome浏览器: {chrome_path}')
            browser = await playwright.chromium.launch(executable_path=chrome_path, **options)
        else:
            # Make sure to run headed.
            browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://cp.kuaishou.com")
        await page.get_by_role("link", name="立即登录").click()
        await page.get_by_text("扫码登录").click()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)

        original_url = page.url
        # 监听页面的 'framenavigated' 事件，只关注主框架的变化
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)

        try:
            # 等待 URL 变化或超时
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)  # 最多等待 200 秒
            print("监听页面跳转成功")
        except asyncio.TimeoutError:
            print("监听页面跳转超时")
            await page.close()
            await context.close()
            await browser.close()
            return None
        await context.storage_state(path=account_file)
        await page.close()
        await context.close()
        await browser.close()
        return None


class KuaiShouVideo(object):
    def __init__(self, title: str, content: str, tags: List[str], file_path: str | Path, account_file: str | Path,
                 publish_date: datetime = None, thumbnail_path: str | Path = None):
        self.title: str = title  # 视频标题
        self.content: str = content
        self.tags: List[str] = tags
        self.file_path: str = file_path
        self.publish_date: datetime = publish_date
        self.account_file = account_file
        self.thumbnail_path: str | Path = thumbnail_path
        self.date_format = '%Y-%m-%d %H:%M'
        # 自动获取Chrome浏览器路径
        self.local_executable_path = get_chrome_path()
        if self.local_executable_path:
            kuaishou_logger.info(f'[+] 自动检测到Chrome浏览器路径: {self.local_executable_path}')
        else:
            kuaishou_logger.warning('[!] 未检测到Chrome浏览器，将使用Playwright默认浏览器')
        self.headless = LOCAL_CHROME_HEADLESS

    async def handle_upload_error(self, page):
        kuaishou_logger.error("视频出错了，重新上传中")
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def upload(self, playwright: Playwright) -> None:
        # 使用 Chromium 浏览器启动一个浏览器实例
        if self.local_executable_path:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                executable_path=self.local_executable_path,
            )
        else:
            browser = await playwright.chromium.launch(
                headless=self.headless
            )  # 创建一个浏览器上下文，使用指定的 cookie 文件
        context = await browser.new_context(storage_state=f"{self.account_file}")
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://cp.kuaishou.com/article/publish/video")
        kuaishou_logger.info('正在上传-------{}.mp4'.format(self.title))
        # 等待页面跳转到指定的 URL，没进入，则自动等待到超时
        kuaishou_logger.info('正在打开主页...')
        await page.wait_for_url("https://cp.kuaishou.com/article/publish/video")
        # 点击 "上传视频" 按钮
        upload_button = page.locator("button[class^='_upload-btn']")
        await upload_button.wait_for(state='visible')  # 确保按钮可见

        async with page.expect_file_chooser() as fc_info:
            await upload_button.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(self.file_path)

        await asyncio.sleep(1)

        # if not await page.get_by_text("封面编辑").count():
        #     raise Exception("似乎没有跳转到到编辑页面")

        # 等待按钮可交互
        new_feature_button = page.get_by_role("button", name="Skip")
        if await new_feature_button.count() > 0:
            await new_feature_button.click()

        # 添加标题文字和话题
        await self.add_title_tags(page)

        # 添加封面
        await self.add_thumbnail(page)

        max_retries = 60  # 设置最大重试次数,最大等待时间为 2 分钟
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 获取包含 '上传中' 文本的元素数量
                number = await page.locator("text=上传中").count()

                if number == 0:
                    kuaishou_logger.success("视频上传完毕")
                    break
                else:
                    if retry_count % 5 == 0:
                        kuaishou_logger.info("正在上传视频中...")
                    await asyncio.sleep(2)
            except Exception as e:
                kuaishou_logger.error(f"检查上传状态时发生错误: {e}")
                await asyncio.sleep(2)  # 等待 2 秒后重试
            retry_count += 1

        if retry_count == max_retries:
            kuaishou_logger.warning("超过最大重试次数，视频上传可能未完成。")

        # 定时任务
        if self.publish_date != 0:
            await self.set_schedule_time(page, self.publish_date)

        # 判断视频是否发布成功
        while True:
            try:
                publish_button = page.get_by_text("发布", exact=True)
                if await publish_button.count() > 0:
                    await publish_button.click()

                await asyncio.sleep(1)
                confirm_button = page.get_by_text("确认发布")
                if await confirm_button.count() > 0:
                    await confirm_button.click()

                # 等待页面跳转，确认发布成功
                await page.wait_for_url(
                    "https://cp.kuaishou.com/article/manage/video?status=2&from=publish",
                    timeout=5000,
                )
                kuaishou_logger.success("视频发布成功")
                break
            except Exception as e:
                kuaishou_logger.info(f"视频正在发布中... 错误: {e}")
                await page.screenshot(full_page=True)
                await asyncio.sleep(1)

        await context.storage_state(path=self.account_file)  # 保存cookie
        kuaishou_logger.info('cookie更新完毕！')
        # 关闭浏览器上下文和浏览器实例
        await context.close()
        await browser.close()

    async def add_title_tags(self, page):
        await page.locator("#work-description-edit").click()

        # 构建完整的文本内容
        content = f"{self.title}\n{self.content}\n"
        await page.keyboard.type(content)

        for index, tag in enumerate(self.tags, start=1):
            # 移除标签中的 # 号（如果有的话），因为我们要通过输入 # 来触发话题选择
            clean_tag = tag.lstrip("#")
            # 输入 # 号触发话题选择
            await page.get_by_text("#话题").click()
            # 输入标签名
            await page.keyboard.type(clean_tag)
            # 等待下拉选项出现
            await page.wait_for_timeout(100)
            # 按下回车键选择第一个匹配的话题
            await page.keyboard.press("Enter")
        kuaishou_logger.info(f"成功添加内容和hashtag: {len(self.tags)}")

    async def add_thumbnail(self, page):
        if self.thumbnail_path:
            kuaishou_logger.info('  [-] 正在设置视频封面...')
            await page.get_by_text("封面设置").nth(1).click()
            await page.wait_for_selector("div.ant-modal:has(*:text('上传封面'))")
            await page.get_by_text("上传封面").click()

            await page.locator('div.ant-modal-body input[type="file"]').set_input_files(self.thumbnail_path)
            await page.get_by_role("button", name="确认").click()

            kuaishou_logger.info('  [+] 视频封面设置完成！')
            # 等待封面设置对话框关闭
            await page.wait_for_selector("div.extractFooter", state='detached')

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def set_schedule_time(self, page, publish_date):
        kuaishou_logger.info("click schedule")
        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M:%S")
        await page.locator("label:text('发布时间')").locator('xpath=following-sibling::div').locator(
            '.ant-radio-input').nth(1).click()
        await asyncio.sleep(1)

        await page.locator('div.ant-picker-input input[placeholder="选择日期时间"]').click()
        await asyncio.sleep(1)

        await page.keyboard.press("Control+KeyA")
        await page.keyboard.type(str(publish_date_hour))
        await page.keyboard.press("Enter")
        await asyncio.sleep(1)