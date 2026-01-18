import asyncio

from uploader.tencent_uploader import TencentUploader
from uploader.auth_manager import AuthManager

if __name__ == '__main__':
    uploader = TencentUploader(headless=False)
    auth_manager = AuthManager(uploader)
    
    result = asyncio.run(auth_manager.perform_login(headless=False))
    if result:
        print("腾讯视频认证成功！")
    else:
        print("腾讯视频认证失败！")
