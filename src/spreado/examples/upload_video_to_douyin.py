import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from ..conf import BASE_DIR
from ..publisher.douyin_uploader import DouYinUploader
from ..utils.files_times import get_title_and_hashtags


async def main():
    filepath = Path(BASE_DIR) / "examples" / "videos"

    folder_path = Path(filepath)
    file_path = folder_path / "demo.mp4"
    thumbnail_path = folder_path / "demo.png"
    txt_path = folder_path / "demo.txt"

    title, content, tags = get_title_and_hashtags(str(txt_path))
    print(f"视频文件名：{file_path}")
    print(f"标题：{title}")
    print(f"Hashtag：{tags}")

    publish_time = datetime.now() + timedelta(hours=2)

    uploader = DouYinUploader()

    # await uploader.verify_cookie_flow(auto_login=False)

    result = await uploader.upload_video_flow(
        file_path=file_path,
        title=title,
        content=content,
        tags=tags,
        publish_date=publish_time,
        thumbnail_path=thumbnail_path,
    )
    if result:
        print(f"{uploader.platform_name}视频上传成功！")
    else:
        print(f"{uploader.platform_name}视频上传失败！")


if __name__ == "__main__":
    asyncio.run(main())
