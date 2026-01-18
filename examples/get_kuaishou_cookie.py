import asyncio

from uploader.kuaishou_uploader import KuaiShouUploader
from uploader.auth_manager import AuthManager

if __name__ == '__main__':
    uploader = KuaiShouUploader(headless=False)
    auth_manager = AuthManager(uploader)
    
    result = asyncio.run(auth_manager.perform_login(headless=False))
    if result:
        print("快手认证成功！")
    else:
        print("快手认证失败！")
