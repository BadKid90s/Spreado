import asyncio

from uploader.douyin_uploader import DouYinUploader
from uploader.auth_manager import AuthManager

if __name__ == '__main__':
    uploader = DouYinUploader(headless=False)
    auth_manager = AuthManager(uploader)
    
    result = asyncio.run(auth_manager.perform_login(headless=False))
    if result:
        print("抖音认证成功！")
    else:
        print("抖音认证失败！")
