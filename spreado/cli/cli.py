#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado CLI 命令行工具 (异步版本)
"""

import argparse
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Type, List

from ..publisher.douyin_uploader.uploader import DouYinUploader
from ..publisher.xiaohongshu_uploader.uploader import XiaoHongShuUploader
from ..publisher.kuaishou_uploader.uploader import KuaiShouUploader
from ..publisher.shipinhao_uploader.uploader import ShiPinHaoUploader
from ..utils import get_logger

from ..__version__ import __logo__, __version__, __author__, __email__

# Logo
LOGO = r"""
{}

           全平台内容发布工具 v{}
           作者: {}
           邮箱: {}
""".format(__logo__, __version__, __author__, __email__)

# 平台映射
UPLOADERS: Dict[str, Type] = {
    "douyin": DouYinUploader,
    "xiaohongshu": XiaoHongShuUploader,
    "kuaishou": KuaiShouUploader,
    "shipinhao": ShiPinHaoUploader,
}

PLATFORM_NAMES = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "kuaishou": "快手",
    "shipinhao": "视频号",
}


def get_uploader(platform: str, cookies: str = None):
    """获取上传器实例"""
    uploader_class = UPLOADERS.get(platform)
    if not uploader_class:
        raise ValueError(f"不支持的平台: {platform}")

    return uploader_class(
        cookie_file_path=cookies,
    )


async def login_single_platform(platform: str, args, logger) -> bool:
    """登录单个平台"""
    platform_name = PLATFORM_NAMES.get(platform, platform)
    logger.info(f"登录平台: {platform_name}")

    try:
        uploader = get_uploader(
            platform=platform,
            cookies=args.cookies,
        )

        result = await uploader.login_flow()

        if result:
            logger.info(f"✓ {platform_name} 登录成功")
            return True
        else:
            logger.error(f"✗ {platform_name} 登录失败")
            return False

    except Exception as e:
        logger.error(f"✗ {platform_name} 登录异常: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return False


async def cmd_login(args):
    """登录命令"""
    logger = get_logger("LOGIN")

    # 只登录指定的平台
    platform = args.platform
    platform_name = PLATFORM_NAMES.get(platform, platform)

    print(f"\n{'=' * 50}")
    print(f"登录平台: {platform_name}")
    print(f"{'=' * 50}")

    result = await login_single_platform(platform, args, logger)

    print(f"\n{'=' * 50}")
    if result:
        print(f"✓ {platform_name} 登录成功")
    else:
        print(f"✗ {platform_name} 登录失败")
    print(f"{'=' * 50}\n")

    return 0 if result else 1


async def verify_single_platform(platform: str, args, logger) -> bool:
    """验证单个平台 Cookie"""
    platform_name = PLATFORM_NAMES.get(platform, platform)

    try:
        uploader = get_uploader(
            platform=platform,
            cookies=args.cookies,
        )

        result = await uploader.verify_cookie_flow()

        if result:
            logger.info(f"✓ {platform_name} Cookie 有效")
            return True
        else:
            logger.warning(f"✗ {platform_name} Cookie 无效或已过期")
            return False

    except Exception as e:
        logger.error(f"✗ {platform_name} 验证异常: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return False


async def cmd_verify(args):
    """验证 Cookie 命令"""
    logger = get_logger("VERIFY")

    platforms = list(UPLOADERS.keys()) if args.platform == "all" else [args.platform]

    print(f"\n{'=' * 50}")
    print("验证 Cookie 状态")
    print(f"{'=' * 50}")

    if args.parallel and len(platforms) > 1:
        # 并行验证
        tasks = [verify_single_platform(p, args, logger) for p in platforms]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        fail_count = len(results) - success_count
    else:
        # 串行验证
        success_count = 0
        fail_count = 0
        for platform in platforms:
            result = await verify_single_platform(platform, args, logger)
            if result:
                success_count += 1
            else:
                fail_count += 1

    print(f"\n{'=' * 50}")
    print(f"验证完成: 有效 {success_count} 个, 无效 {fail_count} 个")
    print(f"{'=' * 50}\n")

    return 0 if fail_count == 0 else 1


async def upload_single_platform(
    platform: str,
    video_path: Path,
    title: str,
    content: str,
    tags: List[str],
    publish_date: datetime,
    thumbnail_path: Path,
    args,
    logger,
) -> bool:
    """上传到单个平台"""
    platform_name = PLATFORM_NAMES.get(platform, platform)
    logger.info(f"开始上传到: {platform_name}")

    try:
        uploader = get_uploader(
            platform=platform,
            cookies=args.cookies,
        )

        result = await uploader.upload_video_flow(
            file_path=video_path,
            title=title,
            content=content,
            tags=tags,
            publish_date=publish_date,
            thumbnail_path=thumbnail_path,
        )

        if result:
            logger.info(f"✓ {platform_name} 上传成功")
            return True
        else:
            logger.error(f"✗ {platform_name} 上传失败")
            return False

    except Exception as e:
        logger.error(f"✗ {platform_name} 上传异常: {e}")
        if args.debug:
            import traceback

            traceback.print_exc()
        return False


async def cmd_upload(args):
    """上传视频命令"""
    logger = get_logger("UPLOAD")

    # 验证视频文件
    video_path = Path(args.video)
    if not video_path.exists():
        logger.error(f"视频文件不存在: {args.video}")
        return 1

    # 验证封面文件
    thumbnail_path = None
    if args.cover:
        thumbnail_path = Path(args.cover)
        if not thumbnail_path.exists():
            logger.error(f"封面文件不存在: {args.cover}")
            return 1

    # 解析标签
    tags = []
    if args.tags:
        tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]

    # 解析发布时间
    publish_date = None
    if args.schedule:
        try:
            if args.schedule.isdigit():
                hours = int(args.schedule)
                publish_date = datetime.now() + timedelta(hours=hours)
            else:
                publish_date = datetime.strptime(args.schedule, "%Y-%m-%d %H:%M")
        except ValueError:
            logger.error(f"无效的发布时间格式: {args.schedule}")
            logger.info("支持格式: 数字(小时) 或 'YYYY-MM-DD HH:MM'")
            return 1

    # 选择平台
    platforms = list(UPLOADERS.keys()) if args.platform == "all" else [args.platform]

    # 显示上传信息
    print(f"\n{'=' * 50}")
    print("上传任务")
    print(f"{'=' * 50}")
    print(f"  视频: {video_path.name}")
    print(f"  标题: {args.title or '(无)'}")
    print(f"  标签: {', '.join(tags) if tags else '(无)'}")
    print(f"  封面: {thumbnail_path.name if thumbnail_path else '(无)'}")
    print(
        f"  定时: {publish_date.strftime('%Y-%m-%d %H:%M') if publish_date else '立即发布'}"
    )
    print(f"  平台: {', '.join(PLATFORM_NAMES.get(p, p) for p in platforms)}")
    print(f"{'=' * 50}\n")

    if args.parallel and len(platforms) > 1:
        # 并行上传
        logger.info("使用并行模式上传...")
        tasks = [
            upload_single_platform(
                platform=p,
                video_path=video_path,
                title=args.title or "",
                content=args.content or "",
                tags=tags,
                publish_date=publish_date,
                thumbnail_path=thumbnail_path,
                args=args,
                logger=logger,
            )
            for p in platforms
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        fail_count = len(results) - success_count
    else:
        # 串行上传
        success_count = 0
        fail_count = 0
        for platform in platforms:
            print(f"\n{'-' * 50}")
            result = await upload_single_platform(
                platform=platform,
                video_path=video_path,
                title=args.title or "",
                content=args.content or "",
                tags=tags,
                publish_date=publish_date,
                thumbnail_path=thumbnail_path,
                args=args,
                logger=logger,
            )
            if result:
                success_count += 1
            else:
                fail_count += 1

    print(f"\n{'=' * 50}")
    print(f"上传完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    print(f"{'=' * 50}\n")

    return 0 if fail_count == 0 else 1


def create_parser():
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="spreado",
        description="Spreado - 全平台内容发布工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 登录平台
  spreado login douyin

  # 验证 Cookie
  spreado verify douyin
  spreado verify all --parallel

  # 上传视频
  spreado upload douyin --video video.mp4 --title "标题"
  spreado upload all --video video.mp4 --parallel
""",
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"Spreado {__version__}"
    )

    # 子命令
    subparsers = parser.add_subparsers(
        dest="command",
        title="命令",
        description="可用命令",
        help="使用 spreado <命令> --help 查看详细帮助",
    )

    # ==================== login 命令 ====================
    login_parser = subparsers.add_parser(
        "login",
        help="登录平台获取 Cookie",
        description="登录指定平台，获取并保存 Cookie",
    )
    login_parser.add_argument(
        "platform",
        choices=["douyin", "xiaohongshu", "kuaishou", "shipinhao"],
        help="目标平台",
    )
    login_parser.add_argument("--cookies", type=str, help="Cookie 保存路径")
    login_parser.add_argument("--debug", action="store_true", help="调试模式")
    login_parser.set_defaults(func=cmd_login)

    # ==================== verify 命令 ====================
    verify_parser = subparsers.add_parser(
        "verify",
        help="验证 Cookie 是否有效",
        description="验证指定平台的 Cookie 是否有效",
    )
    verify_parser.add_argument(
        "platform",
        choices=["douyin", "xiaohongshu", "kuaishou", "shipinhao", "all"],
        help="目标平台 (all 表示所有平台)",
    )
    verify_parser.add_argument("--cookies", type=str, help="Cookie 文件路径")
    verify_parser.add_argument(
        "--parallel", "-p", action="store_true", help="并行验证多个平台"
    )
    verify_parser.add_argument("--debug", action="store_true", help="调试模式")
    verify_parser.set_defaults(func=cmd_verify)

    # ==================== upload 命令 ====================
    upload_parser = subparsers.add_parser(
        "upload", help="上传视频", description="上传视频到指定平台"
    )
    upload_parser.add_argument(
        "platform",
        choices=["douyin", "xiaohongshu", "kuaishou", "shipinhao", "all"],
        help="目标平台 (all 表示所有平台)",
    )
    upload_parser.add_argument(
        "--video", "-V", required=True, type=str, help="视频文件路径"
    )
    upload_parser.add_argument("--title", "-t", type=str, default="", help="视频标题")
    upload_parser.add_argument(
        "--content", "-c", type=str, default="", help="视频描述/正文"
    )
    upload_parser.add_argument(
        "--tags", type=str, default="", help="视频标签，多个用逗号分隔"
    )
    upload_parser.add_argument("--cover", type=str, help="封面图片路径")
    upload_parser.add_argument(
        "--schedule", type=str, help='定时发布 (小时数 或 "YYYY-MM-DD HH:MM")'
    )
    upload_parser.add_argument("--cookies", type=str, help="Cookie 文件路径")
    upload_parser.add_argument(
        "--parallel", "-p", action="store_true", help="并行上传到多个平台"
    )
    upload_parser.add_argument("--debug", action="store_true", help="调试模式")
    upload_parser.set_defaults(func=cmd_upload)

    return parser


async def async_main():
    """异步主函数"""
    print(LOGO)

    parser = create_parser()
    args = parser.parse_args()

    # 没有输入命令时显示帮助
    if not args.command:
        parser.print_help()
        return 0

    # 执行对应命令（异步）
    return await args.func(args)


def main():
    """主函数入口"""
    try:
        # Python 3.10+ 推荐方式
        if sys.version_info >= (3, 10):
            return asyncio.run(async_main())
        else:
            # 兼容旧版本
            loop = asyncio.get_event_loop()
            try:
                return loop.run_until_complete(async_main())
            finally:
                loop.close()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
