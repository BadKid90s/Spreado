import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from spreado.conf import BASE_DIR
from spreado.models.task import Task
from spreado.plugins.xiaohongshu import XiaoHongShuUploader


async def main():
    images_dir = Path(BASE_DIR) / "examples" / "images"
    image_paths = [
        images_dir / "demo-1.png",
        images_dir / "demo-2.png",
    ]

    task = Task(
        type="image_text",
        platform="xiaohongshu",
        title="测试图文",
        content="AI 应用",
        tags=["入门codex", "AI"],
        media_files=[str(path) for path in image_paths],
        publish_date=datetime.now() + timedelta(hours=2),
    )

    uploader = XiaoHongShuUploader()
    result = await uploader.publish_image_text(task)
    if result:
        print(f"{uploader.platform_name}图文发布成功！")
    else:
        print(f"{uploader.platform_name}图文发布失败！")


if __name__ == "__main__":
    asyncio.run(main())
