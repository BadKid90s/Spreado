import asyncio
from pathlib import Path

from conf import BASE_DIR
from uploader.kuaishou_uploader.main import kuaishou_setup

if __name__ == '__main__':
    account_file = Path(BASE_DIR / "cookies" / "kuaishou_uploader" / "account.json")
    account_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_setup = asyncio.run(kuaishou_setup(str(account_file), handle=True))
