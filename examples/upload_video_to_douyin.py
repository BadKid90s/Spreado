import asyncio
from pathlib import Path
from datetime import datetime, timedelta

from conf import BASE_DIR
from uploader.douyin_uploader import DouYinUploader
from uploader.auth_manager import AuthManager
from utils.files_times import get_title_and_hashtags

if __name__ == '__main__':
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

    uploader = DouYinUploader(headless=True)
    auth_manager = AuthManager(uploader)
    
    async def upload():
        if await auth_manager.ensure_authenticated(auto_login=False):
            result = await uploader.upload_video(
                file_path=file_path,
                title=title,
                content=content,
                tags=tags,
                publish_date=publish_time,
                thumbnail_path=thumbnail_path
            )
            if result:
                print("视频上传成功！")
            else:
                print("视频上传失败！")
        else:
            print("认证失败，请先运行 get_douyin_cookie.py 获取认证信息")

    asyncio.run(upload())
