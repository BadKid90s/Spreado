import asyncio

from uploader.shipinhao_uploader import ShipinhaoUploader
from uploader.auth_manager import AuthManager

if __name__ == '__main__':
    uploader = ShipinhaoUploader(headless=False)
    auth_manager = AuthManager(uploader)
    
    result = asyncio.run(auth_manager.perform_login(headless=False))
    if result:
        print("视频号认证成功！")
    else:
        print("视频号认证失败！")
