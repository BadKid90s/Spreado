import unittest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from uploader.base_uploader import BaseUploader
from uploader.auth_manager import AuthManager
from uploader.douyin_uploader import DouYinUploader
from uploader.xiaohongshu_uploader import XiaoHongShuUploader
from uploader.kuaishou_uploader import KuaiShouUploader
from uploader.tencent_uploader import TencentUploader


class TestBaseUploader(unittest.TestCase):
    """
    测试BaseUploader基类
    """

    def setUp(self):
        self.account_file = Path("/tmp/test_account.json")

    def test_platform_name_property(self):
        """
        测试平台名称属性
        """
        class TestUploader(BaseUploader):
            @property
            def platform_name(self):
                return "test"

            @property
            def login_url(self):
                return "https://test.com/login"

            @property
            def upload_url(self):
                return "https://test.com/upload"

            @property
            def success_url_pattern(self):
                return "https://test.com/success"

            @property
            def login_selectors(self):
                return [".login-btn"]

            async def upload_video(self, file_path, title, content, tags, **kwargs):
                return True

        uploader = TestUploader(self.account_file)
        self.assertEqual(uploader.platform_name, "test")

    def test_get_chrome_path(self):
        """
        测试Chrome路径检测
        """
        class TestUploader(BaseUploader):
            @property
            def platform_name(self):
                return "test"

            @property
            def login_url(self):
                return "https://test.com/login"

            @property
            def upload_url(self):
                return "https://test.com/upload"

            @property
            def success_url_pattern(self):
                return "https://test.com/success"

            @property
            def login_selectors(self):
                return [".login-btn"]

            async def upload_video(self, file_path, title, content, tags, **kwargs):
                return True

        uploader = TestUploader(self.account_file)
        chrome_path = uploader._get_chrome_path()
        self.assertIsInstance(chrome_path, (str, type(None)))


class TestAuthManager(unittest.TestCase):
    """
    测试认证管理器
    """

    def setUp(self):
        self.account_file = Path("/tmp/test_account.json")

    def test_check_account_file_exists(self):
        """
        测试检查账户文件是否存在
        """
        class MockUploader(BaseUploader):
            @property
            def platform_name(self):
                return "test"

            @property
            def login_url(self):
                return "https://test.com/login"

            @property
            def upload_url(self):
                return "https://test.com/upload"

            @property
            def success_url_pattern(self):
                return "https://test.com/success"

            @property
            def login_selectors(self):
                return [".login-btn"]

            async def upload_video(self, file_path, title, content, tags, **kwargs):
                return True

        uploader = MockUploader(self.account_file)
        auth_manager = AuthManager(uploader)

        async def test():
            result = await auth_manager.check_account_file_exists()
            self.assertFalse(result)

        asyncio.run(test())


class TestDouYinUploader(unittest.TestCase):
    """
    测试抖音上传器
    """

    def setUp(self):
        self.account_file = Path("/tmp/test_douyin_account.json")

    def test_platform_properties(self):
        """
        测试平台属性
        """
        uploader = DouYinUploader(self.account_file)
        self.assertEqual(uploader.platform_name, "douyin")
        self.assertEqual(uploader.login_url, "https://creator.douyin.com/")
        self.assertEqual(uploader.upload_url, "https://creator.douyin.com/creator-micro/content/upload")
        self.assertEqual(uploader.success_url_pattern, "https://creator.douyin.com/creator-micro/content/manage")


class TestXiaoHongShuUploader(unittest.TestCase):
    """
    测试小红书上传器
    """

    def setUp(self):
        self.account_file = Path("/tmp/test_xiaohongshu_account.json")

    def test_platform_properties(self):
        """
        测试平台属性
        """
        uploader = XiaoHongShuUploader(self.account_file)
        self.assertEqual(uploader.platform_name, "xiaohongshu")
        self.assertEqual(uploader.login_url, "https://creator.xiaohongshu.com/")
        self.assertEqual(uploader.upload_url, "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video")
        self.assertEqual(uploader.success_url_pattern, "https://creator.xiaohongshu.com/publish/success")


class TestKuaiShouUploader(unittest.TestCase):
    """
    测试快手上传器
    """

    def setUp(self):
        self.account_file = Path("/tmp/test_kuaishou_account.json")

    def test_platform_properties(self):
        """
        测试平台属性
        """
        uploader = KuaiShouUploader(self.account_file)
        self.assertEqual(uploader.platform_name, "kuaishou")
        self.assertEqual(uploader.login_url, "https://cp.kuaishou.com")
        self.assertEqual(uploader.upload_url, "https://cp.kuaishou.com/article/publish/video")
        self.assertEqual(uploader.success_url_pattern, "https://cp.kuaishou.com/article/manage/video?status=2&from=publish")


class TestTencentUploader(unittest.TestCase):
    """
    测试腾讯视频上传器
    """

    def setUp(self):
        self.account_file = Path("/tmp/test_tencent_account.json")

    def test_platform_properties(self):
        """
        测试平台属性
        """
        uploader = TencentUploader(self.account_file)
        self.assertEqual(uploader.platform_name, "tencent")
        self.assertEqual(uploader.login_url, "https://channels.weixin.qq.com")
        self.assertEqual(uploader.upload_url, "https://channels.weixin.qq.com/platform/post/create")
        self.assertEqual(uploader.success_url_pattern, "https://channels.weixin.qq.com/platform/post/list")


if __name__ == "__main__":
    unittest.main()
