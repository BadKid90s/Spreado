#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado 二进制分发构建脚本

为不同平台构建预编译的二进制可执行文件。

支持以下平台:
- Windows (x64)
- macOS (x64, arm64)
- Linux (x64, arm64)

使用方法:
    python build_binary.py                    # 构建当前平台
    python build_binary.py --all              # 构建所有平台
    python build_binary.py --upload           # 构建并上传到 PyPI
"""

import os
import sys
import tarfile
import shutil
import subprocess
import platform
import argparse
from pathlib import Path


APP_NAME = "spreado"
VERSION_FILE = Path("spreado/__version__.py")


def get_version():
    """获取版本号"""
    if VERSION_FILE.exists():
        content = VERSION_FILE.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "__version__" in line and "=" in line:
                return line.split("=", 1)[1].strip().strip("\"'")
    return "1.0.0"


def get_platform_info():
    """获取当前平台信息"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "windows", "x64", ".exe"
    elif system == "darwin":
        if machine == "arm64":
            return "macos", "arm64", ""
        else:
            return "macos", "x64", ""
    else:
        if machine == "aarch64":
            return "linux", "arm64", ""
        else:
            return "linux", "x64", ""


PLATFORM_MAP = {
    ("windows", "x64"): ("windows", "x64", ".exe"),
    ("darwin", "x64"): ("macos", "x64", ""),
    ("darwin", "arm64"): ("macos", "arm64", ""),
    ("linux", "x64"): ("linux", "x64", ""),
    ("linux", "aarch64"): ("linux", "arm64", ""),
}


def get_current_build_target():
    """获取当前平台作为构建目标"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    key = (system, machine)
    if key in PLATFORM_MAP:
        return PLATFORM_MAP[key]
    elif machine == "aarch64":
        return ("linux", "arm64", "")
    else:
        return ("linux", "x64", "")


def clean_build_dirs():
    """清理构建目录"""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"  已清理: {dir_name}/")

    for spec_file in Path(".").glob("*.spec"):
        spec_file.unlink()
        print(f"  已清理: {spec_file.name}")


def build_specific_platform(platform_name, arch, output_dir=None, onefile=True):
    """为特定平台构建二进制文件"""
    current_system, current_arch, current_ext = get_platform_info()

    if (platform_name, arch) != (current_system, current_arch):
        print(f"\n⚠ 跳过跨平台构建: 不能在 {current_system}-{current_arch} 上构建 {platform_name}-{arch}")
        print("   请在目标平台上运行此脚本")
        return None

    if output_dir is None:
        output_dir = Path("dist")

    pkg_name = f"{APP_NAME}-{get_version()}-{platform_name}-{arch}"
    temp_dir = Path(f"build/{pkg_name}")

    print(f"\n{'='*60}")
    print(f"  正在构建: {platform_name} ({arch})")
    print(f"{'='*60}")

    clean_build_dirs()

    build_cmd = [
        sys.executable, "build.py",
        "--no-archive",
    ]

    if not onefile:
        build_cmd.append("--dir")

    print(f"\n执行构建命令: {' '.join(build_cmd)}")

    result = subprocess.run(build_cmd, capture_output=False)

    if result.returncode != 0:
        print(f"\n✗ 构建失败: {platform_name} ({arch})")
        return False

    temp_dir.mkdir(parents=True, exist_ok=True)

    dist_path = Path("dist")
    exe_name = f"{APP_NAME}{current_ext}"

    copied = False
    for item in dist_path.iterdir():
        if item.is_file() and (item.name == exe_name or item.suffix == ".exe"):
            dest_path = temp_dir / exe_name
            shutil.copy2(item, dest_path)
            print(f"  复制: {item.name} -> {dest_path.name}")
            os.chmod(dest_path, 0o755)
            copied = True
            break

    if not copied:
        for item in dist_path.iterdir():
            if item.is_file() and item.name.startswith(APP_NAME) and not item.suffix:
                dest_path = temp_dir / exe_name
                shutil.copy2(item, dest_path)
                print(f"  复制: {item.name} -> {dest_path.name}")
                os.chmod(dest_path, 0o755)
                copied = True
                break

    if not copied:
        print("\n✗ 错误: 找不到可执行文件")
        return False

    readme_path = temp_dir / "README.txt"
    if Path("dist/README.txt").exists():
        shutil.copy2("dist/README.txt", readme_path)
        print("  复制: README.txt")

    if platform.system() == "Windows":
        install_script = temp_dir / "install_browser.bat"
        if Path("dist/install_browser.bat").exists():
            shutil.copy2("dist/install_browser.bat", install_script)
            print("  复制: install_browser.bat")
    else:
        install_script = temp_dir / "install_browser.sh"
        if Path("dist/install_browser.sh").exists():
            shutil.copy2("dist/install_browser.sh", install_script)
            os.chmod(install_script, 0o755)
            print("  复制: install_browser.sh")

    archive_path = output_dir / f"{pkg_name}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        for item in temp_dir.iterdir():
            tar.add(item, arcname=item.name)
            print(f"  打包: {item.name}")

    shutil.rmtree(temp_dir)
    print(f"\n✓ {platform_name} ({arch}) 构建完成")
    print(f"  输出文件: {archive_path}")

    return archive_path


def build_current_platform():
    """构建当前平台的二进制文件"""
    system, machine, exe_ext = get_platform_info()
    return build_specific_platform(system, machine)


def build_all_platforms():
    """构建所有平台的二进制文件"""
    platforms = [
        ("windows", "x64"),
        ("macos", "x64"),
        ("macos", "arm64"),
        ("linux", "x64"),
        ("linux", "arm64"),
    ]

    results = []
    for platform_name, arch in platforms:
        try:
            result = build_specific_platform(platform_name, arch)
            results.append((platform_name, arch, result))
        except Exception as e:
            print(f"\n✗ 构建失败 {platform_name} ({arch}): {e}")
            results.append((platform_name, arch, None))

    print(f"\n{'='*60}")
    print("  构建汇总")
    print(f"{'='*60}")

    skipped = sum(1 for r in results if r[2] is None)
    succeeded = sum(1 for r in results if r[2] is not None and r[2] is not False)
    failed = sum(1 for r in results if r[2] is False)

    for platform_name, arch, archive_path in results:
        if archive_path is None:
            print(f"  {platform_name:10} ({arch:6}): ⊘ 跳过（跨平台限制）")
        elif archive_path is False:
            print(f"  {platform_name:10} ({arch:6}): ✗ 失败")
        else:
            print(f"  {platform_name:10} ({arch:6}): ✓ {archive_path.name}")

    print(f"\n  总计: {succeeded} 成功, {failed} 失败, {skipped} 跳过")
    print(f"\n  提示: 在 {platform.system()}-{platform.machine()} 上只能构建当前平台的二进制文件")
    print("        如需构建其他平台，请在对应操作系统上运行此脚本")

    return succeeded > 0 and failed == 0


def upload_to_pypi(test=True):
    """上传到 PyPI"""
    print(f"\n{'='*60}")
    print("  准备上传到 PyPI")
    print(f"{'='*60}")

    if test:
        pypi_cmd = ["twine", "upload", "--repository", "testpypi", "dist/*"]
        pypi_type = "Test PyPI"
    else:
        pypi_cmd = ["twine", "upload", "dist/*"]
        pypi_type = "PyPI"

    print(f"\n正在上传到 {pypi_type}...")
    print(f"命令: {' '.join(pypi_cmd)}")

    result = subprocess.run(pypi_cmd)

    if result.returncode == 0:
        print("\n✓ 上传成功!")
    else:
        print("\n✗ 上传失败")

    return result.returncode == 0


def create_wheels_for_pypi():
    """为 PyPI 创建 wheel 文件"""
    print(f"\n{'='*60}")
    print("  创建 Python Wheel 文件")
    print(f"{'='*60}")

    build_cmd = [sys.executable, "-m", "build", "--wheel"]
    result = subprocess.run(build_cmd)

    if result.returncode == 0:
        print("\n✓ Wheel 文件创建成功")
        dist_path = Path("dist")
        for wheel_file in dist_path.glob("*.whl"):
            print(f"  {wheel_file.name}")
    else:
        print("\n✗ Wheel 文件创建失败")

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Spreado 二进制分发构建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python build_binary.py              # 构建当前平台
  python build_binary.py --all        # 构建所有平台
  python build_binary.py --upload     # 上传到 PyPI (测试)
  python build_binary.py --release    # 完整发布流程
        """
    )

    parser.add_argument("--all", action="store_true",
                        help="构建所有平台的二进制文件")
    parser.add_argument("--upload", action="store_true",
                        help="上传到 PyPI (测试环境)")
    parser.add_argument("--release", action="store_true",
                        help="完整发布流程（构建并上传到正式 PyPI）")
    parser.add_argument("--wheels", action="store_true",
                        help="仅创建 Python wheel 文件")
    parser.add_argument("--clean", action="store_true",
                        help="仅清理构建目录")

    args = parser.parse_args()

    version = get_version()
    print(f"\n{'='*60}")
    print(f"  Spreado 二进制构建工具 v{version}")
    print(f"{'='*60}")

    if args.clean:
        clean_build_dirs()
        print("\n✓ 清理完成")
        return 0

    if args.wheels:
        success = create_wheels_for_pypi()
        return 0 if success else 1

    if args.release:
        if not create_wheels_for_pypi():
            return 1

        if not upload_to_pypi(test=False):
            return 1

        return 0

    if args.all:
        success = build_all_platforms()
    else:
        success = build_current_platform()

    if args.upload:
        upload_to_pypi(test=True)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
