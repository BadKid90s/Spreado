#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado 构建脚本
自动从 spreado/__version__.py 读取版本号
"""

import os
import sys
import shutil
import subprocess
import zipfile
import platform
from pathlib import Path
import argparse

# ============================================================
# 配置
# ============================================================

APP_NAME = 'spreado'

HIDDEN_IMPORTS = [
    'spreado',
    'spreado.cli',
    'spreado.cli.cli',
    'spreado.publisher',
    'spreado.publisher.browser',
    'spreado.publisher.uploader',
    'spreado.publisher.douyin_uploader',
    'spreado.publisher.douyin_uploader.uploader',
    'spreado.publisher.xiaohongshu_uploader',
    'spreado.publisher.xiaohongshu_uploader.uploader',
    'spreado.publisher.kuaishou_uploader',
    'spreado.publisher.kuaishou_uploader.uploader',
    'spreado.publisher.shipinhao_uploader',
    'spreado.publisher.shipinhao_uploader.uploader',
    'spreado.utils',
    'spreado.utils.log',
    'spreado.utils.files_times',
    'playwright',
    'playwright.sync_api',
    'playwright.async_api',
    'playwright._impl',
    'playwright_stealth',
    'greenlet',
    'pyee',
]


# ============================================================
# 工具函数
# ============================================================

def get_version():
    """从 spreado/__version__.py 获取版本号"""
    version_file = Path('spreado/__version__.py')

    if not version_file.exists():
        return "0.0.1"

    # 方法1: 动态导入
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("__version__", version_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.__version__
    except Exception:
        pass

    # 方法2: 文本解析
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            for line in f:
                if '__version__' in line and '=' in line:
                    return line.split('=', 1)[1].strip().strip('"\'')
    except Exception:
        pass

    return "0.0.1"


def get_package_version(package_name):
    """获取已安装包的版本号"""
    try:
        from importlib.metadata import version
        return version(package_name)
    except Exception:
        return None


def get_platform_info():
    """获取平台信息"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == 'windows':
        return 'windows', '.exe', 'zip'
    elif system == 'darwin':
        arch = 'arm64' if machine == 'arm64' else 'x64'
        return f'macos-{arch}', '', 'tar.gz'
    else:
        return f'linux-{machine}', '', 'tar.gz'


def get_size_str(path):
    """获取文件大小的格式化字符串"""
    if not os.path.exists(path):
        return "0 B"

    size = os.path.getsize(path) if os.path.isfile(path) else 0
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ============================================================
# 路径获取函数
# ============================================================

def get_playwright_driver_path():
    """获取 Playwright 驱动路径"""
    try:
        import playwright
        driver_path = Path(playwright.__file__).parent / 'driver'
        if driver_path.exists():
            return str(driver_path).replace('\\', '/')
    except ImportError:
        pass
    return None


def get_playwright_stealth_path():
    """获取 playwright_stealth 路径（包含 JS 文件）"""
    try:
        import playwright_stealth
        stealth_path = Path(playwright_stealth.__file__).parent
        if stealth_path.exists():
            return str(stealth_path).replace('\\', '/')
    except ImportError:
        pass
    return None


# ============================================================
# 构建步骤
# ============================================================

def clean():
    """清理构建文件"""
    print("🧹 清理旧文件...")

    for dir_name in ['build', 'dist', '__pycache__']:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  ✓ 删除 {dir_name}/")

    for spec_file in Path('.').glob('*.spec'):
        spec_file.unlink()
        print(f"  ✓ 删除 {spec_file}")

    # 清理 .pyc 文件
    for pyc in Path('.').rglob('*.pyc'):
        pyc.unlink()

    for pycache in Path('.').rglob('__pycache__'):
        if pycache.exists():
            shutil.rmtree(pycache)


def create_spec(onefile=True):
    """创建 PyInstaller spec 配置文件"""
    print("\n📝 生成 spec 文件...")

    # 获取 Playwright 驱动路径
    driver_path = get_playwright_driver_path()
    if not driver_path:
        print("  ✗ Playwright 驱动未找到")
        print("    请运行: pip install playwright")
        return False
    print(f"  ✓ Playwright 驱动: {driver_path}")

    # 构建 datas 列表
    datas_lines = [
        f"        (r'{driver_path}', 'playwright/driver'),",
    ]

    # 获取 playwright_stealth 路径
    stealth_path = get_playwright_stealth_path()
    if stealth_path:
        print(f"  ✓ playwright_stealth: {stealth_path}")
        datas_lines.append(f"        (r'{stealth_path}', 'playwright_stealth'),")
    else:
        print("  ⚠ playwright_stealth 未找到，跳过")

    datas_str = '\n'.join(datas_lines)

    # 构建 hiddenimports 列表
    hidden_imports_str = ',\n        '.join(f"'{imp}'" for imp in HIDDEN_IMPORTS)

    # 检查图标文件
    icon_line = "icon=None,"
    for icon in ['assets/icon.ico', 'icon.ico', 'assets/icon.png']:
        if os.path.exists(icon):
            icon_path = icon.replace('\\', '/')
            icon_line = f"icon=r'{icon_path}',"
            print(f"  ✓ 图标: {icon}")
            break

    # EXE 配置
    if onefile:
        exe_block = f'''exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{APP_NAME}',
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
    {icon_line}
)'''
    else:
        exe_block = f'''exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_line}
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{APP_NAME}',
)'''

    # 生成 spec 文件内容
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# Auto-generated by build.py

block_cipher = None

a = Analysis(
    ['spreado/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
{datas_str}
    ],
    hiddenimports=[
        {hidden_imports_str}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'pydoc',
        'doctest',
        'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

{exe_block}
'''

    with open('build.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)

    print("  ✓ build.spec 已生成")
    return True


def build(verbose=False):
    """执行 PyInstaller 构建"""
    print("\n🔨 开始构建...")
    print("  （这可能需要几分钟，请耐心等待）")

    cmd = ['pyinstaller', 'build.spec', '--clean', '--noconfirm']

    if verbose:
        result = subprocess.run(cmd)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("\n  ✗ 构建失败:")
            # 显示最后 2000 字符的错误信息
            error_msg = result.stderr
            if len(error_msg) > 2000:
                error_msg = "...\n" + error_msg[-2000:]
            print(error_msg)
            return False

    if result.returncode != 0:
        return False

    print("  ✓ 构建完成")
    return True


def create_readme():
    """创建使用说明文件"""
    print("\n📝 生成说明文件...")

    dist_dir = Path('dist')
    dist_dir.mkdir(exist_ok=True)

    version = get_version()

    readme_content = f'''
═══════════════════════════════════════════════════════════════════
                      SPREADO v{version}
                    全平台内容发布工具
═══════════════════════════════════════════════════════════════════


【首次使用 - 必须执行】
───────────────────────────────────────────────────────────────────

  安装 Playwright 浏览器（仅需执行一次）:

    playwright install chromium


【登录平台】
───────────────────────────────────────────────────────────────────

  spreado login douyin        # 登录抖音
  spreado login xiaohongshu   # 登录小红书
  spreado login kuaishou      # 登录快手
  spreado login shipinhao     # 登录视频号


【上传视频】
───────────────────────────────────────────────────────────────────

  # 上传到抖音
  spreado upload douyin --video video.mp4 --title "视频标题"

  # 上传到小红书（带封面）
  spreado upload xiaohongshu --video video.mp4 --cover cover.jpg

  # 上传到所有平台
  spreado upload all --video video.mp4 --title "标题"


【参数说明】
───────────────────────────────────────────────────────────────────

  必需参数:
    -v, --video       视频文件路径

  可选参数:
    -t, --title       视频标题
    -d, --desc        视频描述
    -c, --cover       封面图片路径
    --tags            标签（逗号分隔）
    --headless        无头模式运行
    --debug           调试模式


【Cookie 存储位置】
───────────────────────────────────────────────────────────────────

  cookies/
  ├── douyin_uploader/account.json
  ├── kuaishou_uploader/account.json
  ├── shipinhao_uploader/account.json
  └── xiaohongshu_uploader/account.json


【获取帮助】
───────────────────────────────────────────────────────────────────

  spreado --help
  spreado login --help
  spreado upload --help


【常见问题】
───────────────────────────────────────────────────────────────────

  Q: 提示找不到浏览器？
  A: 运行 playwright install chromium

  Q: Cookie 过期怎么办？
  A: 重新运行 spreado login <平台>

  Q: 上传失败？
  A: 使用 --debug 参数查看详细日志


═══════════════════════════════════════════════════════════════════
'''

    with open(dist_dir / 'README.txt', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print("  ✓ README.txt")

    # Windows 浏览器安装脚本
    if sys.platform == 'win32':
        bat_content = '''@echo off
chcp 65001 > nul
echo.
echo ========================================
echo   安装 Playwright Chromium 浏览器
echo ========================================
echo.
echo 正在安装，请稍候...
echo.
playwright install chromium
echo.
if errorlevel 1 (
    echo [错误] 安装失败，请检查网络连接
) else (
    echo [成功] 浏览器安装完成！
)
echo.
pause
'''
        with open(dist_dir / 'install_browser.bat', 'w', encoding='utf-8') as f:
            f.write(bat_content)
        print("  ✓ install_browser.bat")
    else:
        sh_content = '''#!/bin/bash
echo ""
echo "========================================"
echo "  安装 Playwright Chromium 浏览器"
echo "========================================"
echo ""
echo "正在安装，请稍候..."
echo ""
playwright install chromium
if [ $? -eq 0 ]; then
    echo ""
    echo "[成功] 浏览器安装完成！"
else
    echo ""
    echo "[错误] 安装失败，请检查网络连接"
fi
'''
        sh_path = dist_dir / 'install_browser.sh'
        with open(sh_path, 'w', encoding='utf-8') as f:
            f.write(sh_content)
        os.chmod(sh_path, 0o755)
        print("  ✓ install_browser.sh")


def create_archive():
    """创建发布压缩包"""
    print("\n📦 创建发布包...")

    version = get_version()
    platform_name, exe_ext, archive_ext = get_platform_info()
    archive_name = f"{APP_NAME}-{version}-{platform_name}"

    dist_dir = Path('dist')

    # 获取要打包的文件
    files_to_pack = []
    for f in dist_dir.iterdir():
        if f.is_file() and not f.name.endswith(('.zip', '.tar.gz')):
            files_to_pack.append(f)

    if not files_to_pack:
        print("  ⚠ 没有找到要打包的文件")
        return None

    if archive_ext == 'zip':
        archive_path = dist_dir / f"{archive_name}.zip"
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files_to_pack:
                zf.write(f, f.name)
                print(f"  + {f.name}")
    else:
        import tarfile
        archive_path = dist_dir / f"{archive_name}.tar.gz"
        with tarfile.open(archive_path, 'w:gz') as tf:
            for f in files_to_pack:
                tf.add(f, f.name)
                print(f"  + {f.name}")

    print(f"  ✓ {archive_path.name} ({get_size_str(archive_path)})")
    return archive_path


def summary():
    """显示构建摘要"""
    version = get_version()
    platform_name, exe_ext, _ = get_platform_info()

    dist_dir = Path('dist')
    exe_name = f"{APP_NAME}{exe_ext}"
    exe_path = dist_dir / exe_name

    print("\n")
    print("=" * 60)
    print(f"  ✨ 构建完成!")
    print("=" * 60)

    print(f"\n  📋 项目信息:")
    print(f"     名称: {APP_NAME}")
    print(f"     版本: {version}")
    print(f"     平台: {platform_name}")

    if exe_path.exists():
        print(f"\n  📦 可执行文件:")
        print(f"     路径: {exe_path}")
        print(f"     大小: {get_size_str(exe_path)}")

    print(f"\n  📂 输出目录: {dist_dir.absolute()}")

    # 列出所有输出文件
    print(f"\n  📋 输出文件:")
    for item in sorted(dist_dir.iterdir()):
        if item.is_file():
            print(f"     {item.name:<35} {get_size_str(item):>10}")

    print("\n" + "-" * 60)
    print("  ⚠️  用户首次使用需执行:")
    print("     playwright install chromium")
    print("-" * 60)

    print("\n  🚀 运行方式:")
    if sys.platform == 'win32':
        print(f"     .\\{exe_name} --help")
        print(f"     .\\{exe_name} login douyin")
        print(f"     .\\{exe_name} upload douyin -v video.mp4")
    else:
        print(f"     ./{exe_name} --help")
        print(f"     ./{exe_name} login douyin")
        print(f"     ./{exe_name} upload douyin -v video.mp4")

    print("\n" + "=" * 60 + "\n")


def check_dependencies():
    """检查构建依赖"""
    print("\n🔍 检查依赖...")

    all_ok = True

    # 检查版本号
    version = get_version()
    print(f"  ✓ 版本号: {version}")

    # PyInstaller (必需)
    pyinstaller_ver = get_package_version('pyinstaller')
    if pyinstaller_ver:
        print(f"  ✓ PyInstaller {pyinstaller_ver}")
    else:
        print("  ✗ PyInstaller 未安装")
        print("    请运行: pip install pyinstaller")
        all_ok = False

    # Playwright (必需)
    playwright_ver = get_package_version('playwright')
    if playwright_ver:
        print(f"  ✓ Playwright {playwright_ver}")
    else:
        print("  ✗ Playwright 未安装")
        print("    请运行: pip install playwright")
        all_ok = False

    # playwright-stealth (可选但推荐)
    stealth_ver = get_package_version('playwright-stealth')
    if stealth_ver:
        print(f"  ✓ playwright-stealth {stealth_ver}")
    else:
        print("  ⚠ playwright-stealth 未安装（可选）")

    # 检查入口文件
    if Path('spreado/__main__.py').exists():
        print("  ✓ 入口文件存在")
    else:
        print("  ✗ 入口文件不存在: spreado/__main__.py")
        all_ok = False

    return all_ok


# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Spreado 构建脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python build.py                 # 完整构建
  python build.py --clean         # 仅清理
  python build.py -v              # 显示详细日志
  python build.py --dir           # 目录模式（非单文件）
  python build.py --no-archive    # 不生成压缩包
'''
    )

    parser.add_argument('--clean', action='store_true',
                        help='仅清理构建文件')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示详细构建日志')
    parser.add_argument('--dir', action='store_true',
                        help='目录模式（非单文件打包）')
    parser.add_argument('--no-archive', action='store_true',
                        help='不生成压缩包')

    args = parser.parse_args()

    # 打印标题
    version = get_version()
    print("\n" + "=" * 60)
    print(f"  SPREADO 构建工具")
    print(f"  版本: {version}")
    print("=" * 60)

    # 仅清理模式
    if args.clean:
        clean()
        print("\n✅ 清理完成\n")
        return 0

    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请先安装必要的依赖\n")
        return 1

    # 清理旧文件
    clean()

    # 生成 spec 文件
    if not create_spec(onefile=not args.dir):
        print("\n❌ spec 文件生成失败\n")
        return 1

    # 执行构建
    if not build(verbose=args.verbose):
        print("\n❌ 构建失败\n")
        return 1

    # 生成说明文件
    create_readme()

    # 创建压缩包
    if not args.no_archive:
        create_archive()

    # 显示摘要
    summary()

    return 0


if __name__ == '__main__':
    sys.exit(main())