#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Spreado Binary Build Script

Build pre-compiled binary executables for different platforms.

Supported platforms:
- Windows (x64)
- macOS (x64, arm64)
- Linux (x64, arm64)

Usage:
    python build_binary.py                    # Build for current platform
    python build_binary.py --all              # Build for all platforms
    python build_binary.py --upload           # Build and upload to PyPI
"""

import os
import sys
import shutil
import subprocess
import platform
import argparse
from pathlib import Path

APP_NAME = "spreado"
VERSION_FILE = Path("src/spreado/__init__.py")


def get_playwright_browser_path():
    """Get Playwright browser installation path"""
    system = platform.system().lower()

    if system == "windows":
        base_path = (
            Path(os.environ.get("USERPROFILE", ""))
            / "AppData"
            / "Local"
            / "ms-playwright"
        )
    elif system == "darwin":
        base_path = Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        base_path = Path.home() / ".cache" / "ms-playwright"

    return base_path


def find_chromium_path():
    """Find Chromium browser path in Playwright installation"""
    browser_path = get_playwright_browser_path()

    if not browser_path.exists():
        print(f"  [!] Playwright browser path not found: {browser_path}")
        return None

    # Find chromium directory (e.g., chromium-1140, chromium-1148)
    chromium_dirs = list(browser_path.glob("chromium-*"))
    if not chromium_dirs:
        print(f"  [!] No Chromium installation found in: {browser_path}")
        return None

    # Use the latest version
    chromium_dir = sorted(chromium_dirs)[-1]
    print(f"  Found Chromium: {chromium_dir.name}")

    return chromium_dir


def copy_chromium_to_package(temp_dir: Path):
    """Copy Chromium browser to package directory"""
    chromium_path = find_chromium_path()

    if not chromium_path:
        print("  [!] Chromium not found, skipping browser bundling")
        return False

    # Create browser directory in package
    browser_dest = temp_dir / "browser"
    browser_dest.mkdir(parents=True, exist_ok=True)

    print("  Copying Chromium browser (this may take a while)...")

    try:
        # Copy entire chromium directory
        shutil.copytree(chromium_path, browser_dest / chromium_path.name, symlinks=True)

        # Get size
        total_size = sum(
            f.stat().st_size
            for f in (browser_dest / chromium_path.name).rglob("*")
            if f.is_file()
        )
        size_mb = total_size / (1024 * 1024)
        print(f"  Copied Chromium browser: {size_mb:.1f} MB")

        return True
    except Exception as e:
        print(f"  [!] Failed to copy Chromium: {e}")
        return False


def get_version():
    """Get version number"""
    if VERSION_FILE.exists():
        content = VERSION_FILE.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "__version__" in line and "=" in line:
                return line.split("=", 1)[1].strip().strip("\"'")
    return "1.0.0"


def get_platform_info():
    """Get current platform info"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        # Windows ARM64 detection
        if machine in ("arm64", "aarch64"):
            return "windows", "arm64", ".exe"
        else:
            return "windows", "x64", ".exe"
    elif system == "darwin":
        if machine == "arm64":
            return "macos", "arm64", ""
        else:
            return "macos", "x64", ""
    else:
        # Linux
        if machine in ("aarch64", "arm64"):
            return "linux", "arm64", ""
        else:
            return "linux", "x64", ""


PLATFORM_MAP = {
    # Windows
    ("windows", "x64"): ("windows", "x64", ".exe"),
    ("windows", "amd64"): ("windows", "x64", ".exe"),
    ("windows", "arm64"): ("windows", "arm64", ".exe"),
    ("windows", "aarch64"): ("windows", "arm64", ".exe"),
    # macOS
    ("darwin", "x64"): ("macos", "x64", ""),
    ("darwin", "x86_64"): ("macos", "x64", ""),
    ("darwin", "arm64"): ("macos", "arm64", ""),
    # Linux
    ("linux", "x64"): ("linux", "x64", ""),
    ("linux", "x86_64"): ("linux", "x64", ""),
    ("linux", "aarch64"): ("linux", "arm64", ""),
    ("linux", "arm64"): ("linux", "arm64", ""),
}


def get_current_build_target():
    """Get current platform as build target"""
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
    """Clean build directories"""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"  Cleaned: {dir_name}/")

    for spec_file in Path(".").glob("*.spec"):
        spec_file.unlink()
        print(f"  Cleaned: {spec_file.name}")


def build_specific_platform(platform_name, arch, output_dir=None, onefile=True):
    """Build binary for specific platform"""
    current_system, current_arch, current_ext = get_platform_info()

    if (platform_name, arch) != (current_system, current_arch):
        print(
            f"\n[!] Skip cross-platform build: cannot build {platform_name}-{arch} on {current_system}-{current_arch}"
        )
        print("    Please run this script on the target platform")
        return None

    if output_dir is None:
        output_dir = Path("dist")

    pkg_name = f"{APP_NAME}-{platform_name}-{arch}"
    temp_dir = Path(f"build/{pkg_name}")

    print(f"\n{'='*60}")
    print(f"  Building: {platform_name} ({arch})")
    print(f"{'='*60}")

    clean_build_dirs()

    # Use PyInstaller directly
    entry_point = "src/spreado/__main__.py"

    build_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--onefile" if onefile else "--onedir",
        "--clean",
        "--noconfirm",
        # Collect playwright related data
        "--collect-all",
        "playwright",
        "--collect-all",
        "playwright_stealth",
        # Hidden imports
        "--hidden-import",
        "spreado.cli.cli",
        "--hidden-import",
        "spreado.publisher",
        "--hidden-import",
        "spreado.publisher.douyin_uploader",
        "--hidden-import",
        "spreado.publisher.xiaohongshu_uploader",
        "--hidden-import",
        "spreado.publisher.kuaishou_uploader",
        "--hidden-import",
        "spreado.publisher.shipinhao_uploader",
        entry_point,
    ]

    print(f"\nExecuting build command: {' '.join(build_cmd)}")

    result = subprocess.run(build_cmd, capture_output=False)

    if result.returncode != 0:
        print(f"\n[X] Build failed: {platform_name} ({arch})")
        return False

    temp_dir.mkdir(parents=True, exist_ok=True)

    dist_path = Path("dist")
    exe_name = f"{APP_NAME}{current_ext}"

    copied = False
    for item in dist_path.iterdir():
        if item.is_file() and (item.name == exe_name or item.suffix == ".exe"):
            dest_path = temp_dir / exe_name
            shutil.copy2(item, dest_path)
            print(f"  Copied: {item.name} -> {dest_path.name}")
            if current_ext != ".exe":
                os.chmod(dest_path, 0o755)
            copied = True
            break

    if not copied:
        for item in dist_path.iterdir():
            if item.is_file() and item.name.startswith(APP_NAME) and not item.suffix:
                dest_path = temp_dir / exe_name
                shutil.copy2(item, dest_path)
                print(f"  Copied: {item.name} -> {dest_path.name}")
                os.chmod(dest_path, 0o755)
                copied = True
                break

    if not copied:
        print("\n[X] Error: Executable not found")
        return False

    # Copy Chromium browser to package
    print("\n  Bundling Chromium browser...")
    browser_bundled = copy_chromium_to_package(temp_dir)

    # Create README.txt
    if browser_bundled:
        readme_content = f"""Spreado v{get_version()} - {platform_name} ({arch})

=== Browser Auto-Detection ===

Spreado automatically detects installed Chrome/Edge browsers.
Just run the executable directly:

  Linux/macOS:  ./spreado --help
  Windows:      spreado.exe --help

The program will show which browser is being used:
  [Browser] Using: auto-detected: /usr/bin/google-chrome


=== Option 1: Use bundled Chromium ===

Chromium browser is bundled in the 'browser' folder.
Use the run script to use the bundled browser:

  Linux/macOS:  ./run.sh --help
  Windows:      run.bat --help


=== Option 2: Manual browser configuration ===

If auto-detection doesn't work, you can manually specify:

  # Use system Chrome
  export SPREADO_BROWSER_CHANNEL=chrome

  # Or use Edge
  export SPREADO_BROWSER_CHANNEL=msedge

  # Or specify browser path directly
  export SPREADO_BROWSER_PATH="/path/to/chrome"


For more info: https://github.com/BadKid90s/Spreado
"""
    else:
        readme_content = f"""Spreado v{get_version()} - {platform_name} ({arch})

=== Browser Auto-Detection (Default) ===

Spreado automatically detects installed Chrome/Edge browsers.
Just run the executable directly:

  Linux/macOS:  ./spreado --help
  Windows:      spreado.exe --help

The program will show which browser is being used:
  [Browser] Using: auto-detected: /usr/bin/google-chrome


=== Manual Configuration (if needed) ===

If auto-detection doesn't work, you can manually specify:

  # Use system Chrome
  export SPREADO_BROWSER_CHANNEL=chrome

  # Or use Edge  
  export SPREADO_BROWSER_CHANNEL=msedge

  # Or specify browser path directly
  export SPREADO_BROWSER_PATH="/path/to/chrome"

  # Or install Playwright Chromium
  playwright install chromium


For more info: https://github.com/BadKid90s/Spreado
"""
    readme_path = temp_dir / "README.txt"
    readme_path.write_text(readme_content, encoding="utf-8")
    print("  Created: README.txt")

    # Create run script (with browser path set)
    if browser_bundled:
        if platform.system() == "Windows":
            run_script = temp_dir / "run.bat"
            run_content = f'@echo off\nset PLAYWRIGHT_BROWSERS_PATH=%~dp0browser\n"{APP_NAME}.exe" %*\n'
            run_script.write_text(run_content, encoding="utf-8")
            print("  Created: run.bat")
        else:
            run_script = temp_dir / "run.sh"
            run_content = f"""#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PLAYWRIGHT_BROWSERS_PATH="$SCRIPT_DIR/browser"
"$SCRIPT_DIR/{APP_NAME}" "$@"
"""
            run_script.write_text(run_content, encoding="utf-8")
            os.chmod(run_script, 0o755)
            print("  Created: run.sh")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define final executable name without version
    final_exe_name = f"{APP_NAME}-{platform_name}-{arch}{current_ext}"
    final_output = output_dir / final_exe_name

    print(f"\n  Finalizing: {final_exe_name}")

    if final_output.exists():
        final_output.unlink()

    # Copy the executable from temp_dir to dist/
    exe_in_temp = temp_dir / exe_name
    shutil.copy2(exe_in_temp, final_output)

    if current_ext != ".exe":
        os.chmod(final_output, 0o755)

    shutil.rmtree(temp_dir)
    print(f"\n[OK] {platform_name} ({arch}) build completed")
    print(f"  Output: {final_output}")

    return final_output


def build_current_platform():
    """Build binary for current platform"""
    system, machine, exe_ext = get_platform_info()
    return build_specific_platform(system, machine)


def build_all_platforms():
    """Build binaries for all platforms"""
    platforms = [
        ("windows", "x64"),
        ("windows", "arm64"),
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
            print(f"\n[X] Build failed {platform_name} ({arch}): {e}")
            results.append((platform_name, arch, None))

    print(f"\n{'='*60}")
    print("  Build Summary")
    print(f"{'='*60}")

    skipped = sum(1 for r in results if r[2] is None)
    succeeded = sum(1 for r in results if r[2] is not None and r[2] is not False)
    failed = sum(1 for r in results if r[2] is False)

    for platform_name, arch, archive_path in results:
        if archive_path is None:
            print(f"  {platform_name:10} ({arch:6}): [-] Skipped (cross-platform)")
        elif archive_path is False:
            print(f"  {platform_name:10} ({arch:6}): [X] Failed")
        else:
            print(f"  {platform_name:10} ({arch:6}): [OK] {archive_path.name}")

    print(f"\n  Total: {succeeded} succeeded, {failed} failed, {skipped} skipped")
    print(
        f"\n  Note: On {platform.system()}-{platform.machine()}, only current platform binary can be built"
    )
    print("        To build for other platforms, run this script on the target OS")

    return succeeded > 0 and failed == 0


def upload_to_pypi(test=True):
    """Upload to PyPI"""
    print(f"\n{'='*60}")
    print("  Preparing to upload to PyPI")
    print(f"{'='*60}")

    if test:
        pypi_cmd = ["twine", "upload", "--repository", "testpypi", "dist/*"]
        pypi_type = "Test PyPI"
    else:
        pypi_cmd = ["twine", "upload", "dist/*"]
        pypi_type = "PyPI"

    print(f"\nUploading to {pypi_type}...")
    print(f"Command: {' '.join(pypi_cmd)}")

    result = subprocess.run(pypi_cmd)

    if result.returncode == 0:
        print("\n[OK] Upload succeeded!")
    else:
        print("\n[X] Upload failed")

    return result.returncode == 0


def create_wheels_for_pypi():
    """Create wheel files for PyPI"""
    print(f"\n{'='*60}")
    print("  Creating Python Wheel files")
    print(f"{'='*60}")

    build_cmd = [sys.executable, "-m", "build", "--wheel"]
    result = subprocess.run(build_cmd)

    if result.returncode == 0:
        print("\n[OK] Wheel files created successfully")
        dist_path = Path("dist")
        for wheel_file in dist_path.glob("*.whl"):
            print(f"  {wheel_file.name}")
    else:
        print("\n[X] Wheel file creation failed")

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(
        description="Spreado Binary Build Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build_binary.py              # Build for current platform
  python build_binary.py --all        # Build for all platforms
  python build_binary.py --upload     # Upload to PyPI (test)
  python build_binary.py --release    # Full release workflow
        """,
    )

    parser.add_argument(
        "--all", action="store_true", help="Build binaries for all platforms"
    )
    parser.add_argument(
        "--upload", action="store_true", help="Upload to PyPI (test environment)"
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Full release workflow (build and upload to PyPI)",
    )
    parser.add_argument(
        "--wheels", action="store_true", help="Only create Python wheel files"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Only clean build directories"
    )

    args = parser.parse_args()

    version = get_version()
    print(f"\n{'='*60}")
    print(f"  Spreado Binary Build Tool v{version}")
    print(f"{'='*60}")

    if args.clean:
        clean_build_dirs()
        print("\n[OK] Clean completed")
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
