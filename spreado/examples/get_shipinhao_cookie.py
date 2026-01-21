import asyncio

from ..publisher.shipinhao_uploader import ShiPinHaoUploader


async def main():
    uploader = ShiPinHaoUploader()
    result = await uploader.login_flow()
    if result:
        print(f"{uploader.platform_name}认证成功！")
    else:
        print(f"{uploader.platform_name}认证失败！")


if __name__ == "__main__":
    asyncio.run(main())
