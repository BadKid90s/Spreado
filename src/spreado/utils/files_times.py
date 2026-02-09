from datetime import timedelta
from datetime import datetime
from pathlib import Path

from ..conf import BASE_DIR


def get_absolute_path(relative_path: str, base_dir: str = None) -> str:
    """
    将相对路径转换为绝对路径

    Args:
        relative_path: 相对路径
        base_dir: 基础目录

    Returns:
        绝对路径字符串
    """
    absolute_path = Path(BASE_DIR) / base_dir / relative_path
    return str(absolute_path)


def get_title_and_hashtags(filename):
    """
    获取视频标题和 hashtag

    Args:
        filename: 视频文件名

    Returns:
        视频标题和 hashtag 列表
    """
    txt_filename = filename.replace(".mp4", ".txt")

    with open(txt_filename, "r", encoding="utf-8") as f:
        content = f.read()

    splite_str = content.strip().split("\n")
    title = splite_str[0]
    content_text = splite_str[1]
    hashtags = splite_str[2]

    import re

    tags = re.split(r"[,，\s]+", hashtags.strip())
    tags = [tag for tag in tags if tag]

    return title, content_text, tags


def generate_schedule_time_next_day(
    total_videos, videos_per_day=1, daily_times=None, timestamps=False, start_days=0
):
    """
    生成视频上传时间表，从下一天开始

    Args:
        total_videos: 要上传的视频总数
        videos_per_day: 每天上传的视频数
        daily_times: 每天发布视频的特定时间列表
        timestamps: 是否返回时间戳或datetime对象
        start_days: 从start_days天后开始

    Returns:
        视频的调度时间列表，返回时间戳或datetime对象
    """
    if videos_per_day <= 0:
        raise ValueError("videos_per_day should be a positive integer")

    if daily_times is None:
        daily_times = [6, 11, 14, 16, 22]

    if videos_per_day > len(daily_times):
        raise ValueError("videos_per_day should not exceed the length of daily_times")

    schedule = []
    current_time = datetime.now()

    for video in range(total_videos):
        day = video // videos_per_day + start_days + 1
        daily_video_index = video % videos_per_day

        hour = daily_times[daily_video_index]
        time_offset = timedelta(
            days=day,
            hours=hour - current_time.hour,
            minutes=-current_time.minute,
            seconds=-current_time.second,
            microseconds=-current_time.microsecond,
        )
        timestamp = current_time + time_offset

        schedule.append(timestamp)

    if timestamps:
        schedule = [int(time.timestamp()) for time in schedule]
    return schedule


if __name__ == "__main__":
    title, tags = get_title_and_hashtags(
        "/Users/wry/PycharmProjects/uploader/examples/videos/demo.txt"
    )
    print(f"标题：{title}")
    print(f"Hashtag：{tags}")
