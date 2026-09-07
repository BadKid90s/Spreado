# Spreado - 全平台内容发布工具

一个强大的自动化工具，支持将视频同时发布到多个中国社交媒体平台，包括抖音、小红书、快手和腾讯视频号。

## 🚀 功能特性

- **多平台支持**: 一键上传至抖音、小红书、快手、腾讯视频号
- **智能认证**: 自动处理登录和Cookie管理，支持二维码扫码登录全流程
- **灵活调度**: 支持定时发布和草稿保存
- **丰富配置**: 标题、描述、标签、封面、地理位置等完整设置
- **命令行界面**: 简单易用的CLI工具
- **程序接口**: 支持Python API集成
- **插件化架构**: 新平台无需改动核心代码，放入 `plugins/` 目录即可自动发现

## 🤖 Agent Skill

我们为 AI Agent (如 Claude, Antigravity，OpenCode, Codex, Cursor, Windsurf) 提供了专门的 Skill 支持，可以更智能地协助您进行安装、配置和视频发布。

### 获取 Skill
您可以下载打包好的 `.skill` 文件并导入到您的 AI 助手：

- **下载链接**: [spreado-skill](./skills/spreado-skill)
- **源码位置**: `./skills/spreado-skill`

### 支持的功能
- **智能安装**: 自动根据环境推荐最合适的安装方式（二进制或 Python）。
- **流程引导**: 引导完成多平台登录认证和状态校验。
- **发布助手**: 协同处理视频上传、元数据配置及定时任务。

## 📋 系统要求

- Python **3.10** 或更高版本
- 操作系统：Windows, macOS, Linux
- 浏览器：系统已安装的 Chrome、Edge、Chromium 或 Brave

## 📦 安装指南

### 方式一：下载可执行文件（最简单）

如果你不想安装 Python 环境，可以直接从 GitHub 下载官方编译好的可执行文件：

| 操作系统 | 下载链接 | 国内加速 |
| :--- | :--- | :--- |
| **Windows** | [x64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-windows-x64.exe) \| [ARM64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-windows-arm64.exe) | [🚀 x64](https://gh-proxy.org/https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-windows-x64.exe) \| [ARM64](https://gh-proxy.org/https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-windows-arm64.exe) |
| **macOS** | [Silicon](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-macos-arm64) \| [Intel](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-macos-x64) | [🚀 Silicon](https://gh-proxy.org/https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-macos-arm64) \| [Intel](https://gh-proxy.org/https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-macos-x64) |
| **Linux** | [x64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-linux-x64) \| [ARM64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-linux-arm64) | [🚀 x64](https://gh-proxy.org/https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-linux-x64) \| [ARM64](https://gh-proxy.org/https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-linux-arm64) |

> 更多版本请前往 [GitHub Releases](https://github.com/BadKid90s/Spreado/releases) 页面。

### 方式二：使用 uv 安装（推荐）

如果你安装了 [uv](https://github.com/astral-sh/uv)，可以极其快速地安装：

```bash
# 作为工具全局安装
uv tool install spreado

# 或者在项目中使用
uv add spreado
```

### 方式二：通过 pip 安装

```bash
pip install spreado
```

> Spreado 会自动检测系统安装的 Chrome、Edge、Chromium 或 Brave，并通过 CDP 控制。项目不再下载或使用 Playwright 内置 Chromium。

### 方式三：从源码安装

```bash
# 克隆项目
git clone https://github.com/BadKid90s/spreado.git
cd spreado

# 使用 uv 环境同步（推荐）
uv sync

# 或者使用传统 pip
pip install .
```

## 🔧 快速开始

### 1. 平台登录认证

首次使用需要登录各个平台（会打开浏览器窗口）：

```bash
# 登录抖音（支持扫码/账密，等待手机确认后自动保存）
spreado login douyin

# 登录同一平台的另一个账号
spreado login douyin --account brand-b

# 登录小红书
spreado login xiaohongshu

# 登录快手（跨域扫码：在 passport 页扫码，手机确认后自动跳转）
spreado login kuaishou

# 登录腾讯视频号
spreado login shipinhao
```

> **提示**：快手使用独立的 passport 域名登录，扫码后请在手机上确认，不要关闭浏览器，等待自动跳转即可。

### 2. 验证认证状态

```bash
# 检查所有平台认证状态
spreado verify all

# 检查单个平台
spreado verify douyin

# 检查指定账号
spreado verify douyin --account brand-b

# 并行验证（更快）
spreado verify all --parallel
```

### 3. 上传视频

**基本用法**

```bash
# 上传到抖音
spreado upload douyin --video video.mp4 --title "我的视频标题"

# 使用指定账号上传
spreado upload douyin --account brand-b --video video.mp4 --title "我的视频标题"

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
├── douyin/
│   └── default/
│       └── account.json
├── xiaohongshu/
│   └── default/
│       └── account.json
├── kuaishou/
│   └── default/
│       └── account.json
└── shipinhao/
    └── default/
        └── account.json
```

> 多账号支持：登录、验证和上传时使用相同的 `--account <账号ID>`。每个账号的认证文件、浏览器 profile 和运行锁均相互隔离；`--cookies` 仅用于覆盖认证文件路径。

### 自定义 Cookie 路径

```bash
# 指定自定义 Cookie 文件路径
spreado upload douyin --video video.mp4 --title "标题" --cookies /path/to/cookies/douyin/myaccount/account.json
```

## 🐍 Python API 使用示例

```python
import asyncio
from pathlib import Path
from spreado.plugins.douyin.uploader import DouYinUploader


async def upload_video():
    # 初始化上传器
    uploader = DouYinUploader(account_id="brand-b")

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

Spreado 通过 Chrome DevTools Protocol（CDP）连接系统真实浏览器，按以下优先级选择：

1. **显式路径** - `SPREADO_BROWSER_PATH`
2. **浏览器类型** - `SPREADO_BROWSER_CHANNEL`
3. **自动检测** - 查找已安装的 Chrome、Edge、Chromium 或 Brave

浏览器使用按账号隔离的持久化 Spreado 专用配置目录，不会接管日常浏览器配置。默认根目录为：

| 平台 | 配置目录 |
|-----|---------|
| Windows | `%LOCALAPPDATA%\Spreado\browser-profiles` |
| macOS | `~/Library/Application Support/Spreado/browser-profiles` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/spreado/browser-profiles` |

实际 profile 路径会追加 `{platform}/{account_id}`。同一账号不能同时运行两个登录、验证或发布流程，不同账号可以并行。

### 自动检测

无需任何配置，Spreado 会自动检测以下浏览器：

| 平台 | 检测的浏览器 |
|-----|------------|
| Windows | Chrome, Edge, Chromium, Brave |
| macOS | Chrome, Edge, Chromium, Brave |
| Linux | Chrome, Edge, Chromium, Brave |

### 手动指定浏览器

如需手动指定浏览器，可设置环境变量：

```bash
# 使用系统 Chrome
export SPREADO_BROWSER_CHANNEL=chrome

# 或使用 Edge
export SPREADO_BROWSER_CHANNEL=msedge

# 或指定浏览器路径
export SPREADO_BROWSER_PATH="/path/to/chrome"

# 可选：指定账号 profile 的根目录
export SPREADO_BROWSER_PROFILES_DIR="/path/to/spreado-profiles"
```

## 🛠️ 故障排除

### 常见问题

1. **提示找不到浏览器？**
   
   请先安装 Chrome、Edge、Chromium 或 Brave。若自动检测不到，可指定路径：
   ```bash
   export SPREADO_BROWSER_PATH="/path/to/chrome"
   ```

2. **Cookie 过期怎么办？**
   ```bash
   # 重新登录（Cookie 过期会在下次上传时自动检测并提示）
   spreado login douyin
   ```

3. **快手扫码后页面跳走了？**
   
   扫码后请在手机上点击"确认"，不要关闭浏览器。登录检测会等待手机确认完成后再跳转，无需手动操作。

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

### 各平台通用命令（推荐）

使用 `uv` 可以确保在一个干净的环境中构建：

```bash
uv run build_binary.py
```

该脚本会：
1. 自动调用 PyInstaller 进行精简打包。
2. 将 Playwright 浏览器引擎打包进压缩包。
3. 在 `dist/` 目录下生成各平台的 `.tar.gz` 压缩包。

### 传统方式

```bash
# 安装 PyInstaller
pip install pyinstaller

# 执行打包
python build_binary.py
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目！


## 📄 许可证

本项目遵循 MIT 许可证。
