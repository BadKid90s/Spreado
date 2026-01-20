import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from uploader.douyin_uploader import DouYinUploader
from uploader.xiaohongshu_uploader import XiaoHongShuUploader
from uploader.kuaishou_uploader import KuaiShouUploader
from uploader.shipinhao_uploader import ShipinhaoUploader
from utils.files_times import get_title_and_hashtags
from uploader.auth_manager import AuthManager
from utils.log import get_logger


PLATFORMS = {
    "douyin": DouYinUploader,
    "xiaohongshu": XiaoHongShuUploader,
    "kuaishou": KuaiShouUploader,
    "shipinhao": ShipinhaoUploader,
}

ACTIONS = ["login", "upload", "verify", "status"]

logger = get_logger("CLI")


def get_account_file(platform: str) -> Path:
    """
    获取账户文件路径

    Args:
        platform: 平台名称

    Returns:
        账户文件路径
    """
    from conf import COOKIES_DIR
    return COOKIES_DIR / f"{platform}_uploader" / "account.json"


def get_uploader(platform: str, headless: bool = None) -> Optional:
    """
    获取上传器实例

    Args:
        platform: 平台名称
        headless: 是否使用无头模式

    Returns:
        上传器实例
    """
    if platform not in PLATFORMS:
        logger.error(f"不支持的平台: {platform}")
        logger.info(f"支持的平台: {', '.join(PLATFORMS.keys())}")
        return None

    account_file = get_account_file(platform)
    uploader_class = PLATFORMS[platform]

    return uploader_class(account_file=account_file, headless=headless)


async def login_action(platform: str, headless: bool = False):
    """
    执行登录操作

    Args:
        platform: 平台名称
        headless: 是否使用无头模式
    """
    uploader = get_uploader(platform, headless=False)
    if not uploader:
        return False

    logger.info(f"[+] 开始登录 {platform} 平台...")

    auth_manager = AuthManager(uploader)
    result = await auth_manager.perform_login(headless=headless)

    if result:
        logger.info(f"[+] {platform} 平台登录成功")
    else:
        logger.error(f"[!] {platform} 平台登录失败")

    return result


async def verify_action(platform: str):
    """
    执行Cookie验证操作

    Args:
        platform: 平台名称
    """
    uploader = get_uploader(platform, headless=True)
    if not uploader:
        return False

    logger.info(f"[+] 开始验证 {platform} 平台Cookie...")

    auth_manager = AuthManager(uploader)
    status = await auth_manager.get_auth_status()

    logger.info(f"[+] {platform} 平台认证状态:")
    logger.info(f"    账户文件存在: {status['account_file_exists']}")
    logger.info(f"    Cookie有效: {status['cookie_valid']}")
    logger.info(f"    已认证: {status['authenticated']}")

    return status['authenticated']


async def status_action(platform: str):
    """
    显示认证状态

    Args:
        platform: 平台名称
    """
    uploader = get_uploader(platform, headless=True)
    if not uploader:
        return False

    auth_manager = AuthManager(uploader)
    status = await auth_manager.get_auth_status()

    print(f"\n{platform.upper()} 平台认证状态:")
    print(f"  账户文件: {'存在' if status['account_file_exists'] else '不存在'}")
    print(f"  Cookie状态: {'有效' if status['cookie_valid'] else '无效'}")
    print(f"  认证状态: {'已认证' if status['authenticated'] else '未认证'}")
    print()

    return status['authenticated']


async def upload_action(
    platform: str,
    file_path: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[List[str]] = None,
    txt_file: Optional[str] = None,
    thumbnail: Optional[str] = None,
    publish_date: Optional[str] = None,
    auto_login: bool = True,
    **kwargs
):
    """
    执行上传操作

    Args:
        platform: 平台名称
        file_path: 视频文件路径
        title: 视频标题
        content: 视频描述
        tags: 视频标签列表
        txt_file: 包含标题、描述和标签的文本文件
        thumbnail: 封面图片路径
        publish_date: 定时发布时间
        auto_login: 是否自动登录
        **kwargs: 其他平台特定参数
    """
    uploader = get_uploader(platform, headless=True)
    if not uploader:
        return False

    file_path = Path(file_path)
    if not file_path.exists():
        logger.error(f"[!] 视频文件不存在: {file_path}")
        return False

    if txt_file:
        txt_path = Path(txt_file)
        if txt_path.exists():
            title, content, tags = get_title_and_hashtags(str(txt_path))
            logger.info(f"[+] 从文本文件读取信息: {txt_path}")
        else:
            logger.warning(f"[!] 文本文件不存在: {txt_path}")

    if not title:
        title = file_path.stem

    if not content:
        content = ""

    if not tags:
        tags = []

    if publish_date:
        try:
            publish_datetime = datetime.strptime(publish_date, "%Y-%m-%d %H:%M")
            logger.info(f"[+] 定时发布时间: {publish_datetime}")
        except ValueError:
            logger.error(f"[!] 发布时间格式错误，请使用: YYYY-MM-DD HH:MM")
            return False
    else:
        publish_datetime = None
        logger.info("[+] 使用即时发布")

    logger.info(f"[+] 开始上传视频到 {platform} 平台...")
    logger.info(f"    视频文件: {file_path}")
    logger.info(f"    标题: {title}")
    logger.info(f"    描述: {content[:50]}..." if len(content) > 50 else f"    描述: {content}")
    logger.info(f"    标签: {', '.join(tags)}")
    if thumbnail:
        logger.info(f"    封面: {thumbnail}")
    if publish_datetime:
        logger.info(f"    定时发布: {publish_datetime}")

    # 直接调用upload_video方法，避免重复的Cookie验证（特别是抖音平台）
    # 但仍然需要确保Cookie有效
    if not uploader.account_file.exists():
        logger.error("[!] 账户文件不存在")
        if auto_login:
            logger.info("[+] 尝试自动登录...")
            from uploader.auth_manager import AuthManager
            auth_manager = AuthManager(uploader)
            login_success = await auth_manager.perform_login(headless=False)
            if not login_success:
                logger.error("[!] 自动登录失败")
                return False
        else:
            logger.error("[!] 请先登录获取Cookie")
            return False

    try:
        result = await uploader.upload_video_flow(
            file_path=file_path,
            title=title,
            content=content,
            tags=tags,
            publish_date=publish_datetime,
            thumbnail_path=thumbnail,
            **kwargs
        )

        if result:
            # 上传成功后保存Cookie
            if hasattr(uploader, '_save_cookie') and callable(uploader._save_cookie):
                await uploader._save_cookie()
            logger.info(f"[+] 视频上传成功")
        else:
            logger.error(f"[!] 视频上传失败")

        return result
    except Exception as e:
        logger.error(f"[!] 上传视频时出错: {e}")
        return False
    finally:
        # 确保资源清理
        if hasattr(uploader, '_cleanup_resources') and callable(uploader._cleanup_resources):
            await uploader._cleanup_resources()


def main():
    parser = argparse.ArgumentParser(
        description="多平台视频上传工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 登录抖音平台
  python cli.py douyin login

  # 上传视频到抖音
  python cli.py douyin upload video.mp4 --title "我的视频" --content "视频描述" --tags "标签1,标签2"

  # 从文本文件读取信息并上传
  python cli.py douyin upload video.mp4 --txt video.txt

  # 验证Cookie状态
  python cli.py douyin verify

  # 查看认证状态
  python cli.py douyin status
        """
    )

    parser.add_argument(
        "platform",
        choices=PLATFORMS.keys(),
        help="平台名称 (douyin, xiaohongshu, kuaishou, tencent)"
    )

    parser.add_argument(
        "action",
        choices=ACTIONS,
        help="操作类型 (login, upload, verify, status)"
    )

    parser.add_argument(
        "--file",
        help="视频文件路径 (用于upload操作)"
    )

    parser.add_argument(
        "--title",
        help="视频标题 (用于upload操作)"
    )

    parser.add_argument(
        "--content",
        help="视频描述 (用于upload操作)"
    )

    parser.add_argument(
        "--tags",
        help="视频标签，用逗号分隔 (用于upload操作)"
    )

    parser.add_argument(
        "--txt",
        help="包含标题、描述和标签的文本文件 (用于upload操作)"
    )

    parser.add_argument(
        "--thumbnail",
        help="封面图片路径 (用于upload操作)"
    )

    parser.add_argument(
        "--publish-date",
        help="定时发布时间，格式: YYYY-MM-DD HH:MM (用于upload操作)"
    )

    parser.add_argument(
        "--no-auto-login",
        action="store_true",
        help="禁用自动登录 (用于upload操作)"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用无头模式 (用于login操作)"
    )

    args = parser.parse_args()

    tags = []
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(",")]

    kwargs = {}
    if args.platform == "douyin":
        location = getattr(args, "location", None)
        product_link = getattr(args, "product_link", None)
        product_title = getattr(args, "product_title", None)
        if location:
            kwargs["location"] = location
        if product_link and product_title:
            kwargs["product_link"] = product_link
            kwargs["product_title"] = product_title

    if args.action == "login":
        result = asyncio.run(login_action(args.platform, args.headless))
        sys.exit(0 if result else 1)

    elif args.action == "verify":
        result = asyncio.run(verify_action(args.platform))
        sys.exit(0 if result else 1)

    elif args.action == "status":
        result = asyncio.run(status_action(args.platform))
        sys.exit(0 if result else 1)

    elif args.action == "upload":
        if not args.file:
            logger.error("[!] 上传操作需要指定视频文件路径 (--file)")
            sys.exit(1)

        result = asyncio.run(upload_action(
            platform=args.platform,
            file_path=args.file,
            title=args.title,
            content=args.content,
            tags=tags,
            txt_file=args.txt,
            thumbnail=args.thumbnail,
            publish_date=args.publish_date,
            auto_login=not args.no_auto_login,
            **kwargs
        ))
        sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
