import asyncio

from publisher.shipinhao_uploader import ShipinhaoUploader


async def main():
    uploader = ShipinhaoUploader()
    result = await uploader.login_flow()
    if result:
        print(f"{uploader.platform_name}认证成功！")
    else:
        print(f"{uploader.platform_name}认证失败！")
    await uploader.close()

if __name__ == '__main__':
    asyncio.run(main())
