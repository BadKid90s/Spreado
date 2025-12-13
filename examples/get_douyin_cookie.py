import asyncio
from pathlib import Path

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup

if __name__ == '__main__':
    account_file = Path(BASE_DIR / "examples" / "cookies" / "douyin_uploader" / "account.json")
    account_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_setup = asyncio.run(douyin_setup(str(account_file), handle=True))