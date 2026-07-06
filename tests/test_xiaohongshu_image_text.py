import asyncio
from datetime import datetime

from spreado.models.task import Task
from spreado.plugins.xiaohongshu.uploader import XiaoHongShuUploader


def test_xiaohongshu_declares_image_text_support():
    uploader = XiaoHongShuUploader()

    assert "image_text" in uploader.supported_content_types


def test_publish_image_text_requires_media_files():
    uploader = XiaoHongShuUploader()
    task = Task(type="image_text", platform="xiaohongshu", media_files=[])

    assert asyncio.run(uploader.publish_image_text(task)) is False


def test_publish_image_text_maps_task_to_flow(monkeypatch):
    uploader = XiaoHongShuUploader()
    publish_date = datetime(2026, 9, 1, 22, 23)
    captured = {}

    async def fake_flow(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(uploader, "upload_image_text_flow", fake_flow)

    task = Task(
        type="image_text",
        platform="xiaohongshu",
        title="测试标题",
        content="测试正文",
        tags=["AI", "#howto"],
        media_files=["a.png", "b.png"],
        publish_date=publish_date,
    )

    assert asyncio.run(uploader.publish_image_text(task)) is True
    assert captured == {
        "image_paths": ["a.png", "b.png"],
        "title": "测试标题",
        "content": "测试正文",
        "tags": ["AI", "#howto"],
        "publish_date": publish_date,
    }


def test_publish_button_falls_back_to_xhs_shadow_host(monkeypatch):
    uploader = XiaoHongShuUploader()
    clicked = {}

    class FakeRoleLocator:
        @property
        def first(self):
            return self

        async def count(self):
            return 0

    class FakeHostLocator:
        @property
        def first(self):
            return self

        async def count(self):
            return 1

        async def scroll_into_view_if_needed(self):
            clicked["scrolled"] = True

        async def wait_for(self, state, timeout):
            clicked["waited"] = (state, timeout)

        async def bounding_box(self):
            return {"x": 10, "y": 20, "width": 1200, "height": 90}

    class FakeMouse:
        async def click(self, x, y):
            clicked["point"] = (x, y)

    class FakePage:
        url = "https://creator.xiaohongshu.com/publish/publish?published=true"
        mouse = FakeMouse()

        def get_by_role(self, role, name):
            return FakeRoleLocator()

        def locator(self, selector):
            clicked["selector"] = selector
            return FakeHostLocator()

        async def wait_for_url(self, pattern, timeout):
            clicked["wait_for_url"] = timeout

    assert asyncio.run(uploader._click_publish_button(FakePage())) is True
    assert clicked["selector"] == 'xhs-publish-btn[submit-disabled="false"]'
    assert clicked["point"] == (682.0, 65.0)
