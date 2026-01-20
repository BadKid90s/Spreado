#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado CLI 命令行工具
"""

import argparse
import sys
from pathlib import Path

from datetime import datetime, timedelta

from ..publisher.douyin_uploader.uploader import DouYinUploader
from ..publisher.xiaohongshu_uploader.uploader import XiaoHongShuUploader
from ..publisher.kuaishou_uploader.uploader import KuaiShouUploader
from ..publisher.shipinhao_uploader.uploader import ShiPinHaoUploader
from ..utils import get_logger

# 版本信息
from ..__version__ import __version__, __author__, __email__

# Logo
LOGO = r"""
   _____ _____  _____  ______          _____   ____  
  / ____|  __ \|  __ \|  ____|   /\   |  __ \ / __ \ 
 | (___ | |__) | |__) | |__     /  \  | |  | | |  | |
  \___ \|  ___/|  _  /|  __|   / /\ \ | |  | | |  | |
  ____) | |    | | \ \| |____ / ____ \| |__| | |__| |
 |_____/|_|    |_|  \_\______/_/    \_\_____/ \____/ 

           全平台内容发布工具 v{}
           作者: {}
           邮箱: {}
""".format(__version__, __author__, __email__)


def main():
    """主函数"""

    print(LOGO)

    parser = argparse.ArgumentParser(
        description='Spreado - 全平台内容发布工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  spreado douyin --video video.mp4 --title "我的视频"
  spreado xiaohongshu --video video.mp4 --cover cover.jpg
  spreado --platform all --video video.mp4
        """
    )

    parser.add_argument('-v', '--version', action='version', version=f'Spreado {__version__}')

    # 平台选择
    parser.add_argument(
        'platform',
        choices=['douyin', 'xiaohongshu', 'kuaishou', 'shipinhao', 'all'],
        help='目标平台'
    )

    # 视频文件
    parser.add_argument(
        '--video',
        required=True,
        type=str,
        help='视频文件路径'
    )

    # 标题
    parser.add_argument(
        '--title',
        type=str,
        default='',
        help='视频标题'
    )

    # 描述
    parser.add_argument(
        '--content',
        type=str,
        default='',
        help='视频描述'
    )
    # 标签
    parser.add_argument(
        '--tags',
        type=str,
        default='',
        help='视频标签'
    )

    # 封面
    parser.add_argument(
        '--cover',
        type=str,
        help='封面图片路径'
    )

    # Cookie 文件
    parser.add_argument(
        '--cookies',
        type=str,
        help='Cookie 文件路径'
    )

    # 配置文件
    parser.add_argument(
        '--config',
        type=str,
        help='配置文件路径'
    )

    # 调试模式
    parser.add_argument(
        '--debug',
        action='store_true',
        help='开启调试模式'
    )

    # 无头模式
    parser.add_argument(
        '--headless',
        action='store_true',
        help='无头模式运行'
    )

    args = parser.parse_args()

    # 设置日志
    logger = get_logger("CLI")

    # 验证视频文件
    video_path = Path(args.video)
    if not video_path.exists():
        logger.error(f"视频文件不存在: {args.video}")
        return 1

    # 封面文件
    cover_path = Path(args.cover)
    if not cover_path.exists():
        logger.error(f"封面文件不存在: {args.cover}")
        return 1

    # 平台映射
    uploaders = {
        "douyin": DouYinUploader,
        "xiaohongshu": XiaoHongShuUploader,
        "kuaishou": KuaiShouUploader,
        "shipinhao": ShiPinHaoUploader,
    }

    # 选择要上传的平台
    if args.platform == 'all':
        platforms = uploaders.keys()
    else:
        platforms = [args.platform]

    # 执行上传
    success_count = 0
    fail_count = 0

    for platform in platforms:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"开始上传到: {platform.upper()}")
        logger.info(f"{'=' * 60}")

        try:
            uploader_class = uploaders[platform]
            uploader = uploader_class(
                cookie_file_path=args.cookies,
            )

            # 上传视频
            result = uploader.upload_video_flow(
                file_path=video_path,
                title=args.title,
                content=args.content,
                tags=args.tags,
                publish_date= datetime.now() + timedelta(hours=2),
                thumbnail_path=cover_path,
                auto_login=True,
            )

            if result:
                logger.info(f"✓ {platform} 上传成功")
                success_count += 1
            else:
                logger.error(f"✗ {platform} 上传失败")
                fail_count += 1

        except Exception as e:
            logger.error(f"✗ {platform} 上传异常: {e}")
            fail_count += 1

            if args.debug:
                import traceback
                traceback.print_exc()

    # 结果统计
    print(f"\n{'=' * 60}")
    print(f"上传完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    print(f"{'=' * 60}\n")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())