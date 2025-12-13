from pathlib import Path

# 创建所有平台的cookies目录
BASE_DIR = Path(__file__).parent.resolve()

# 抖音
douyin_cookie_dir = BASE_DIR / "cookies" / "douyin_uploader"
douyin_cookie_dir.mkdir(parents=True, exist_ok=True)

# 快手
kuaishou_cookie_dir = BASE_DIR / "cookies" / "kuaishou_uploader"
kuaishou_cookie_dir.mkdir(parents=True, exist_ok=True)

# 腾讯
tencent_cookie_dir = BASE_DIR / "cookies" / "tencent_uploader"
tencent_cookie_dir.mkdir(parents=True, exist_ok=True)

# 小红书
xiaohongshu_cookie_dir = BASE_DIR / "cookies" / "xiaohongshu_uploader"
xiaohongshu_cookie_dir.mkdir(parents=True, exist_ok=True)