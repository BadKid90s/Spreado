import asyncio

from uploader.xiaohongshu_uploader import XiaoHongShuUploader
from uploader.auth_manager import AuthManager

if __name__ == '__main__':
    uploader = XiaoHongShuUploader(headless=False)
    auth_manager = AuthManager(uploader)
    
    result = asyncio.run(auth_manager.perform_login(headless=False))
    if result:
        print("小红书认证成功！")
    else:
        print("小红书认证失败！")
