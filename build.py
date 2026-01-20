#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado 构建脚本
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean():
    """清理构建文件"""
    print("🧹 清理旧文件...")

    dirs = ['build', 'dist', '__pycache__']
    for dir_name in dirs:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  ✓ 删除 {dir_name}/")

    # 删除 .spec 文件
    for spec_file in Path('.').glob('*.spec'):
        if spec_file.name != 'build.spec':
            spec_file.unlink()
            print(f"  ✓ 删除 {spec_file}")


def get_playwright_driver_path():
    """获取 Playwright 驱动路径"""
    try:
        import playwright
        playwright_path = Path(playwright.__file__).parent
        driver_path = playwright_path / 'driver'

        if driver_path.exists():
            print(f"✓ 找到 Playwright 驱动: {driver_path}")
            return str(driver_path)
        else:
            print(f"⚠ Playwright 驱动不存在: {driver_path}")
            return None
    except ImportError:
        print("⚠ Playwright 未安装")
        return None


def create_spec():
    """创建 spec 配置"""
    print("\n📝 生成 spec 文件...")

    driver_path = get_playwright_driver_path()

    if not driver_path:
        print("❌ 无法找到 Playwright 驱动，请先安装: pip install playwright")
        return False

    # 转换路径为适合的格式
    driver_path = driver_path.replace('\\', '/')

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['spreado/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        (r'{driver_path}', 'playwright/driver'),
        ('spreado/conf.py', 'spreado'),
        ('assets/*', 'assets'),
    ],
    hiddenimports=[
        'spreado',
        'spreado.cli',
        'spreado.cli.cli',
        'spreado.publisher',
        'spreado.publisher.browser',
        'spreado.publisher.uploader',
        'spreado.publisher.douyin_uploader',
        'spreado.publisher.xiaohongshu_uploader',
        'spreado.publisher.kuaishou_uploader',
        'spreado.publisher.shipinhao_uploader',
        'spreado.utils',
        'playwright',
        'playwright.sync_api',
        'playwright.async_api',
        'playwright._impl',
        'greenlet',
        'websockets',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='spreado',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
)
'''

    with open('build.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)

    print("  ✓ build.spec 已生成")
    return True


def build():
    """执行构建"""
    print("\n🔨 开始构建...")

    result = subprocess.run(
        ['pyinstaller', 'build.spec', '--clean'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("❌ 构建失败:")
        print(result.stderr)
        return False

    print("  ✓ 构建完成")
    return True


def package():
    """打包额外文件"""
    print("\n📦 打包额外文件...")

    dist_dir = Path('dist')

    # 复制配置文件模板
    extra_files = [
        ('README.md', 'README.md'),
        ('requirements.txt', 'requirements.txt'),
    ]

    for src, dst in extra_files:
        if os.path.exists(src):
            dst_path = dist_dir / dst
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst_path)
            print(f"  ✓ 复制 {src}")

    # 创建配置文件示例
    config_example = dist_dir / 'config.example.json'
    config_content = '''{
    "platforms": {
        "douyin": {
            "cookies": "cookies/douyin.json"
        },
        "xiaohongshu": {
            "cookies": "cookies/xiaohongshu.json"
        }
    }
}'''

    with open(config_example, 'w', encoding='utf-8') as f:
        f.write(config_content)
    print("  ✓ 生成 config.example.json")

    # 创建启动脚本
    print("\n📝 生成启动脚本...")

    # Windows 批处理
    bat_content = '''@echo off
chcp 65001 > nul
echo.
echo ====================================
echo    SPREADO - 全平台内容发布工具
echo ====================================
echo.

spreado.exe %*

if errorlevel 1 (
    echo.
    echo ❌ 执行失败
    pause
) else (
    echo.
    echo ✓ 执行成功
)
'''

    with open(dist_dir / 'spreado.bat', 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print("  ✓ 生成 spreado.bat")

    # Linux/Mac shell
    sh_content = '''#!/bin/bash

echo ""
echo "===================================="
echo "   SPREADO - 全平台内容发布工具"
echo "===================================="
echo ""

./spreado "$@"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ 执行成功"
else
    echo ""
    echo "❌ 执行失败"
fi
'''

    with open(dist_dir / 'spreado.sh', 'w', encoding='utf-8') as f:
        f.write(sh_content)

    os.chmod(dist_dir / 'spreado.sh', 0o755)
    print("  ✓ 生成 spreado.sh")

    # 创建使用说明
    readme = dist_dir / 'USAGE.txt'
    usage_content = '''Spreado 使用说明
==================

1. 基本使用
-----------
spreado <平台> --video <视频路径> [选项]

2. 支持平台
-----------
- douyin       抖音
- xiaohongshu  小红书
- kuaishou     快手
- shipinhao    视频号
- all          所有平台

3. 常用命令
-----------
# 上传到抖音
spreado douyin --video video.mp4 --title "我的视频"

# 上传到小红书（带封面）
spreado xiaohongshu --video video.mp4 --cover cover.jpg

# 上传到所有平台
spreado all --video video.mp4 --title "标题" --description "描述"

4. 参数说明
-----------
--video       视频文件路径（必需）
--title       视频标题
--description 视频描述
--cover       封面图片路径
--cookies     Cookie 文件路径
--config      配置文件路径
--headless    无头模式运行
--debug       调试模式

5. Cookie 配置
--------------
首次使用需要登录各平台获取 Cookie
Cookie 文件格式参考 config.example.json

6. 获取帮助
-----------
spreado --help
spreado <平台> --help

7. 更多信息
-----------
GitHub: https://github.com/yourname/spreado
文档: https://spreado.io/docs
'''

    with open(readme, 'w', encoding='utf-8') as f:
        f.write(usage_content)
    print("  ✓ 生成 USAGE.txt")


def get_size(path):
    """获取文件或目录大小"""
    if os.path.isfile(path):
        return os.path.getsize(path)

    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total += os.path.getsize(filepath)
    return total


def summary():
    """显示构建摘要"""
    print("\n" + "=" * 60)
    print("✨ 构建完成！")
    print("=" * 60)

    exe_path = Path('dist/spreado.exe' if sys.platform == 'win32' else 'dist/spreado')

    if exe_path.exists():
        size_mb = get_size(exe_path) / 1024 / 1024
        print(f"\n📍 可执行文件: {exe_path}")
        print(f"📊 文件大小: {size_mb:.2f} MB")

    dist_size = get_size('dist') / 1024 / 1024
    print(f"📦 总大小: {dist_size:.2f} MB")

    print(f"\n📂 输出目录: {Path('dist').absolute()}")

    print("\n🚀 运行方式:")
    if sys.platform == 'win32':
        print("  Windows: spreado.bat douyin --video video.mp4")
        print("  或直接: spreado.exe --help")
    else:
        print("  Linux/Mac: ./spreado.sh douyin --video video.mp4")
        print("  或直接: ./spreado --help")

    print("\n💡 提示:")
    print("  1. 首次使用需配置各平台 Cookie")
    print("  2. 查看 USAGE.txt 了解详细用法")
    print("  3. 参考 config.example.json 配置")

    print("\n" + "=" * 60 + "\n")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  SPREADO 构建工具")
    print("=" * 60 + "\n")

    # 检查依赖
    print("🔍 检查依赖...")
    try:
        import PyInstaller
        print("  ✓ PyInstaller 已安装")
    except ImportError:
        print("  ❌ PyInstaller 未安装")
        print("  请运行: pip install pyinstaller")
        return 1

    # 执行构建流程
    clean()

    if not create_spec():
        return 1

    if not build():
        return 1

    package()
    summary()

    return 0


if __name__ == '__main__':
    sys.exit(main())