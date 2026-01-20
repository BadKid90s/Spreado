# 多平台视频上传工具

一个强大的自动化工具，支持将视频同时发布到多个中国社交媒体平台，包括抖音、小红书、快手和腾讯视频号。

## 🚀 功能特性

- **多平台支持**: 一键上传至抖音、小红书、快手、腾讯视频号
- **智能认证**: 自动处理登录和Cookie管理
- **灵活调度**: 支持定时发布和草稿保存
- **丰富配置**: 标题、描述、标签、封面、地理位置等完整设置
- **命令行界面**: 简单易用的CLI工具
- **程序接口**: 支持Python API集成

## 📋 系统要求

- Python 3.10 或更高版本
- 操作系统：Windows, macOS, Linux

## 📦 安装指南

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd spreado
   ```

2. **创建虚拟环境（推荐）**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # 或
   .venv\Scripts\activate     # Windows
   ```

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

## 🔧 快速开始

### 1. 平台登录认证

首次使用需要登录各个平台：

```bash
# 登录抖音（会打开浏览器，手动完成登录）
python cli/cli.py douyin login

# 登录小红书
python cli/cli.py xiaohongshu login

# 登录快手
python cli/cli.py kuaishou login

# 登录腾讯视频号
python cli/cli.py shipinhao login
```

### 2. 验证认证状态

```bash
# 检查抖音认证状态
python cli/cli.py douyin status

# 验证Cookie有效性
python cli/cli.py douyin verify
```

### 3. 上传视频

**基本上传**
```bash
python cli/cli.py douyin upload --file video.mp4 --title "我的视频" --content "视频描述" --tags "标签1,标签2"
```

**高级功能**
```bash
# 设置封面和定时发布
python cli/cli.py douyin upload --file video.mp4 --title "我的视频" --thumbnail cover.png --publish-date "2024-12-31 18:00"

# 从文本文件读取信息
python cli/cli.py douyin upload --file video.mp4 --txt video.txt

# 禁用自动登录
python cli/cli.py douyin upload --file video.mp4 --title "我的视频" --no-auto-login
```

### 4. 支持的平台

| 平台 | 命令 | 特殊功能 |
|------|------|----------|
| 抖音 | `douyin` | 地理位置、商品链接、第三方同步 |
| 小红书 | `xiaohongshu` | 详细标签管理 |
| 快手 | `kuaishou` | 定时发布 |
| 腾讯视频号 | `shipinhao` | 原创声明、合集、短标题 |

## 📁 项目结构

```
spreado/
├── cli/                    # 命令行工具
│   └── cli.py
├── publisher/             # 各平台上传器
│   ├── browser.py         # 浏览器封装与反检测
│   ├── uploader.py        # 上传器基类
│   ├── douyin_uploader/   # 抖音上传器
│   ├── xiaohongshu_uploader/ # 小红书上传器
│   ├── kuaishou_uploader/ # 快手上传器
│   └── shipinhao_uploader/ # 腾讯视频号上传器
├── utils/                 # 工具模块
├── conf.py                # 配置文件
└── requirements.txt       # 依赖列表
```

## ⚙️ 高级用法

### 文本文件格式

创建一个 `.txt` 文件，按以下格式组织信息：
```
视频标题
视频描述
标签1,标签2,标签3
```

### Python API 使用示例

```python
import asyncio
from pathlib import Path
from spreado.publisher.douyin_uploader import DouYinUploader


async def upload_video():
   # 初始化上传器
   cookie_file_path = Path("spreado/cookies/douyin_uploader/account.json")
   uploader = DouYinUploader(cookie_file_path=cookie_file_path)

   # 上传视频
   result = await uploader.upload_video_flow(
      file_path="video.mp4",
      title="我的视频",
      content="视频描述",
      tags=["标签1", "标签2"],
      thumbnail_path="cover.png",
      auto_login=True
   )

   if result:
      print("上传成功！")
   else:
      print("上传失败！")


# 运行上传
asyncio.run(upload_video())
```

## 🛠️ 故障排除

### 常见问题

1. **认证失败**
   - 确保已成功登录平台
   - 检查Cookie文件是否过期，重新运行登录命令

2. **上传失败**
   - 检查网络连接
   - 确认视频文件格式和大小符合平台要求
   - 查看日志文件获取详细错误信息

3. **浏览器问题**
   - 确保Playwright Chromium浏览器已正确安装
   - 检查是否有浏览器进程未正确关闭

### 调试技巧

- 使用 `--headless` 参数控制浏览器显示模式
- 查看 `logs/` 目录下的详细日志
- 在开发阶段可使用有头模式进行调试

## 📦 打包为可执行文件

您可以将项目打包为独立的可执行文件，方便在没有Python环境的机器上运行：

```bash
# 安装PyInstaller
pip install pyinstaller

# 安装Playwright浏览器
playwright install chromium

# 运行打包脚本
./build_exe.sh

# 打包后的可执行文件位于 dist/uploader
```

详细打包说明请参见 [BUILD.md](BUILD.md)。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目！

## 📄 许可证

本项目遵循 MIT 许可证。
