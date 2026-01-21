# Spreado - 全平台内容发布工具

一个强大的自动化工具，支持将视频同时发布到多个中国社交媒体平台，包括抖音、小红书、快手和腾讯视频号。

## 🚀 功能特性

- **多平台支持**: 一键上传至抖音、小红书、快手、腾讯视频号
- **智能认证**: 自动处理登录和Cookie管理
- **灵活调度**: 支持定时发布和草稿保存
- **丰富配置**: 标题、描述、标签、封面、地理位置等完整设置
- **命令行界面**: 简单易用的CLI工具
- **程序接口**: 支持Python API集成

## 📋 系统要求

- Python 3.8 或更高版本
- 操作系统：Windows, macOS, Linux
- 浏览器：自动检测系统已安装的 Chrome/Edge，或使用 Playwright Chromium

## 📦 安装指南

### 方式一：通过 PyPI 安装（推荐）

```bash
# 安装最新版本
pip install spreado
```

> 💡 **无需单独安装浏览器！** Spreado 会自动检测系统已安装的 Chrome 或 Edge 浏览器。如果未检测到，会使用 Playwright 内置的 Chromium。

### 方式二：从源码安装

```bash
# 克隆项目
git clone https://github.com/BadKid90s/spreado.git
cd spreado

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

## 🔧 快速开始

### 1. 平台登录认证

首次使用需要登录各个平台：

```bash
# 登录抖音（会打开浏览器，手动完成登录）
spreado login douyin

# 登录小红书
spreado login xiaohongshu

# 登录快手
spreado login kuaishou

# 登录腾讯视频号
spreado login shipinhao
```

### 2. 验证认证状态

```bash
# 检查所有平台认证状态
spreado verify all

# 检查单个平台
spreado verify douyin

# 并行验证（更快）
spreado verify all --parallel
```

### 3. 上传视频

**基本用法**

```bash
# 上传到抖音
spreado upload douyin --video video.mp4 --title "我的视频标题"

# 上传到小红书（需要封面）
spreado upload xiaohongshu --video video.mp4 --cover cover.jpg --title "标题"

# 上传到所有平台
spreado upload all --video video.mp4 --title "我的视频"
```

**高级用法**

```bash
# 带详细描述和标签
spreado upload douyin \
    --video video.mp4 \
    --title "视频标题" \
    --content "详细描述内容" \
    --tags "标签1,标签2,标签3" \
    --cover thumbnail.jpg

# 定时发布（2小时后）
spreado upload douyin --video video.mp4 --title "定时发布" --schedule 2

# 指定发布时间
spreado upload douyin --video video.mp4 --title "定时发布" --schedule "2024-12-31 18:00"

# 并行上传到多个平台
spreado upload all --video video.mp4 --title "我的视频" --parallel
```

### 4. 获取帮助

```bash
# 查看主帮助
spreado --help

# 查看登录命令帮助
spreado login --help

# 查看上传命令帮助
spreado upload --help
```

## 🔧 配置文件

### Cookie 存储位置

登录后，Cookie 文件保存在以下位置：

```
cookies/
├── douyin_uploader/account.json
├── xiaohongshu_uploader/account.json
├── kuaishou_uploader/account.json
└── shipinhao_uploader/account.json
```

### 自定义 Cookie 路径

```bash
spreado upload douyin --video video.mp4 --title "标题" --cookies /path/to/cookies/
```

## 🐍 Python API 使用示例

```python
import asyncio
from pathlib import Path
from spreado.publisher.douyin_uploader import DouYinUploader


async def upload_video():
    # 初始化上传器
    uploader = DouYinUploader(
        cookie_file_path=Path("cookies/douyin_uploader/account.json")
    )

    # 上传视频
    result = await uploader.upload_video_flow(
        file_path=Path("video.mp4"),
        title="我的视频",
        content="视频描述",
        tags=["标签1", "标签2"],
        thumbnail_path=Path("cover.png"),
    )

    if result:
        print("上传成功！")
    else:
        print("上传失败！")


# 运行上传
if __name__ == "__main__":
    asyncio.run(upload_video())
```

## 🌐 浏览器配置

Spreado 支持多种浏览器选项，按以下优先级自动选择：

1. **自动检测系统浏览器**（默认）- 自动查找已安装的 Chrome/Edge
2. **环境变量指定** - 手动配置浏览器
3. **Playwright Chromium** - 作为后备选项

### 自动检测

无需任何配置，Spreado 会自动检测以下浏览器：

| 平台 | 检测的浏览器 |
|-----|------------|
| Windows | Chrome, Edge |
| macOS | Chrome, Edge, Chromium |
| Linux | google-chrome, chromium, edge |

### 手动指定浏览器

如需手动指定浏览器，可设置环境变量：

```bash
# 使用系统 Chrome
export SPREADO_BROWSER_CHANNEL=chrome

# 或使用 Edge
export SPREADO_BROWSER_CHANNEL=msedge

# 或指定浏览器路径
export SPREADO_BROWSER_PATH="/path/to/chrome"
```

### 使用 Playwright Chromium

如果系统没有安装浏览器，可手动安装 Playwright Chromium：

```bash
playwright install chromium
```

## 🛠️ 故障排除

### 常见问题

1. **提示找不到浏览器？**
   
   Spreado 会自动检测系统 Chrome/Edge。如果检测不到，可以：
   ```bash
   # 方式1：手动指定浏览器路径
   export SPREADO_BROWSER_PATH="/path/to/chrome"
   
   # 方式2：安装 Playwright Chromium
   playwright install chromium
   ```

2. **Cookie 过期怎么办？**
   ```bash
   # 重新登录
   spreado login douyin
   ```

3. **上传失败？**
   ```bash
   # 使用调试模式查看详细信息
   spreado upload douyin --video video.mp4 --title "标题" --debug
   ```

4. **依赖问题？**
   ```bash
   # 重新安装依赖
   pip install --upgrade spreado
   ```

5. **所有平台都需要登录吗？**
   是的，首次使用每个平台都需要执行 `spreado login <平台>` 进行登录认证。登录成功后 Cookie 会保存在本地，后续上传无需重复登录。

6. **如何查看详细日志？**
   使用 `--debug` 参数可以查看详细的调试日志，帮助排查问题。

### 调试技巧

- 使用 `--debug` 参数查看详细日志和错误信息
- 查看终端输出的 `[Browser] Using: ...` 信息确认使用的浏览器
- 查看终端输出的错误信息

## 📦 打包为可执行文件

如果您需要将项目打包为独立的可执行文件（无需 Python 环境）：

### Windows

```bash
# 安装 PyInstaller
pip install pyinstaller

# 执行打包
python build.py

# 打包后的文件位于 dist/ 目录
```

### macOS / Linux

```bash
# 安装 PyInstaller
pip install pyinstaller

# 执行打包
python build.py

# 赋予执行权限
chmod +x dist/spreado
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目！

## 📄 许可证

本项目遵循 MIT 许可证。
