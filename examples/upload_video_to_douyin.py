import asyncio
from pathlib import Path

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
from utils.files_times import generate_schedule_time_next_day, get_title_and_hashtags

if __name__ == '__main__':
    filepath = Path(BASE_DIR) / "examples" / "videos"
    account_file = Path(BASE_DIR / "examples" / "cookies" / "douyin_uploader" / "account.json")
    # 获取视频目录
    folder_path = Path(filepath)
    # 获取文件夹中的所有文件
    files = list(folder_path.glob("*.mp4"))
    file_num = len(files)
    cookie_setup = asyncio.run(douyin_setup(account_file, handle=False))
    for index, file in enumerate(files):
        title, content, tags = get_title_and_hashtags(str(file))
        thumbnail_path = file.with_suffix('.png')
        # 打印视频文件名、标题和 hashtag
        print(f"视频文件名：{file}")
        print(f"标题：{title}")
        print(f"Hashtag：{tags}")
        app = DouYinVideo(title, content, tags, file, 0, account_file)
        asyncio.run(app.main(), debug=False)
