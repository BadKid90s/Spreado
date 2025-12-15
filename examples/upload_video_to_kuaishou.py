import asyncio
from pathlib import Path

from conf import BASE_DIR
from uploader.kuaishou_uploader.main import kuaishou_setup, KuaiShouVideo
from utils.files_times import get_title_and_hashtags

if __name__ == '__main__':
    filepath = Path(BASE_DIR) / "examples" / "videos"
    account_file = Path(BASE_DIR / "cookies" / "kuaishou_uploader" / "account.json")
    cookie_setup = asyncio.run(kuaishou_setup(account_file, handle=False))

    # 使用固定路径的demo文件
    folder_path = Path(filepath)
    file_path = folder_path / "demo.mp4"
    thumbnail_path = folder_path / "demo.png"
    txt_path = folder_path / "demo.txt"

    title, content, tags = get_title_and_hashtags(str(txt_path))
    # 打印视频文件信息
    print(f"视频文件名：{file_path}")
    print(f"标题：{title}")
    print(f"Hashtag：{tags}")

    # 设置发布时间为当前时间2小时后
    from datetime import datetime, timedelta

    publish_time = datetime.now() + timedelta(hours=2)

    app = KuaiShouVideo(title=title,
                        content=content,
                        tags=tags,
                        file_path=file_path,
                        account_file=account_file,
                        publish_date=publish_time,
                        thumbnail_path=thumbnail_path,
                        )
    asyncio.run(app.main(), debug=False)
