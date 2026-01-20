# Spreado 项目开发指南

本文档为 Spreado 多平台视频上传工具的开发指南，涵盖项目结构、技术架构、使用方法等内容。

## 项目概述

Spreado 是一个基于 Python 和 Playwright 开发的多平台视频上传工具，支持将视频发布到抖音、小红书、快手和腾讯视频号等中国社交媒体平台。

### 核心特性

- **统一架构**: 所有平台上传器继承自 `BaseUploader` 基类，接口统一
- **模块化设计**: 高内聚低耦合，易于维护和扩展
- **自动化认证**: 支持有头模式登录和无头模式 Cookie 验证
- **CLI 工具**: 提供完整的命令行工具，支持登录、上传、验证等操作
- **详细日志**: 使用 loguru 日志系统记录详细的操作日志
- **反检测技术**: 使用 playwright-stealth 库绕过网站的自动化检测

## 项目结构

```
spreado/
├── spreado/                     # 主包目录
│   ├── __init__.py              # 包初始化
│   ├── __main__.py              # 入口点
│   ├── __version__.py           # 版本信息
│   ├── conf.py                  # 项目配置文件
│   ├── cli/                     # CLI 命令行工具
│   │   ├── __init__.py
│   │   └── cli.py               # CLI 实现（支持 login/verify/upload 命令）
│   ├── publisher/               # 各平台上传器
│   │   ├── __init__.py
│   │   ├── browser.py           # StealthBrowser 浏览器封装与反检测
│   │   ├── uploader.py          # BaseUploader 上传器基类
│   │   ├── douyin_uploader/     # 抖音上传器
│   │   ├── xiaohongshu_uploader/ # 小红书上传器
│   │   ├── kuaishou_uploader/   # 快手上传器
│   │   └── shipinhao_uploader/  # 视频号上传器
│   ├── utils/                   # 工具模块
│   │   ├── __init__.py
│   │   ├── log.py               # 日志工具
│   │   └── files_times.py       # 文件时间处理
│   └── examples/                # 使用示例
├── docs/                        # 文档目录
│   ├── core_flow.md             # 核心流程文档
│   ├── guide.md                 # 开发指南（本文档）
│   └── login_flow.md            # 登录流程文档
├── pyproject.toml               # 项目配置
├── setup.py                     # 兼容配置
├── MANIFEST.in                  # 打包清单
├── requirements.txt             # 依赖列表
├── build.py                     # PyInstaller 打包脚本
└── README.md                    # 项目说明文档
```

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.8+ | 主要编程语言 |
| Playwright | 浏览器自动化框架 |
| playwright-stealth | 反检测库 |
| loguru | 日志记录 |
| argparse | 命令行参数解析 |
| pytz | 时区处理 |

## 环境配置

### 系统要求

- Python 3.8 或更高版本
- 操作系统：Windows、macOS、Linux
- 浏览器：Chromium（通过 Playwright 安装）

### 安装依赖

```bash
# 克隆项目
git clone https://github.com/yourname/spreado.git
cd spreado

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

## 使用方法

### CLI 命令行工具

#### 1. 登录平台

```bash
# 登录抖音（打开浏览器，手动完成登录）
spreado login douyin

# 登录小红书
spreado login xiaohongshu

# 登录快手
spreado login kuaishou

# 登录视频号
spreado login shipinhao
```

#### 2. 验证 Cookie

```bash
# 验证所有平台
spreado verify all

# 验证单个平台
spreado verify douyin

# 并行验证（更快）
spreado verify all --parallel
```

#### 3. 上传视频

```bash
# 基本用法
spreado upload douyin --video video.mp4 --title "我的视频"

# 带详细描述和标签
spreado upload douyin \
    --video video.mp4 \
    --title "视频标题" \
    --content "详细描述" \
    --tags "标签1,标签2,标签3" \
    --cover thumbnail.jpg

# 定时发布（2小时后）
spreado upload douyin --video video.mp4 --title "定时发布" --schedule 2

# 并行上传到多个平台
spreado upload all --video video.mp4 --title "我的视频" --parallel
```

#### 4. 获取帮助

```bash
# 主帮助
spreado --help

# 子命令帮助
spreado login --help
spreado upload --help
spreado verify --help
```

### Python API 使用

```python
import asyncio
from pathlib import Path
from spreado.publisher.douyin_uploader import DouYinUploader


async def upload_video():
    # 初始化上传器
    uploader = DouYinUploader(
        cookie_file_path=Path("cookies/douyin_uploader/account.json")
    )

    # 验证 Cookie（不自动登录）
    if not await uploader.verify_cookie_flow():
        print("Cookie 无效或已过期，请先执行 login")
        return False

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

    return result


if __name__ == "__main__":
    asyncio.run(upload_video())
```

## 架构设计

### BaseUploader 基类

所有平台上传器必须继承 `BaseUploader` 抽象类，实现以下属性和方法：

#### 抽象属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `platform_name` | str | 平台名称 |
| `login_url` | str | 登录页面 URL |
| `login_success_url` | str | 登录成功后的跳转 URL |
| `upload_url` | str | 上传页面 URL |
| `success_url_pattern` | str | 上传成功后的 URL 模式 |
| `_login_selectors` | List[str] | 登录相关页面元素选择器列表 |

#### 核心方法

| 方法 | 说明 |
|------|------|
| `login_flow()` | 有头模式登录流程 |
| `verify_cookie_flow(auto_login=False)` | 验证 Cookie，必要时自动登录 |
| `upload_video_flow()` | 主上传流程 |
| `_upload_video()` | 平台特定的上传实现（抽象方法） |

### StealthBrowser 浏览器封装

`StealthBrowser` 类封装了 Playwright 浏览器实例，主要特性：

- **反检测**: 集成 playwright-stealth 库
- **上下文管理**: 实现 `async with` 协议，确保资源正确释放
- **Cookie 管理**: 支持从文件加载和保存 Cookie

```python
async def example():
    # 创建浏览器实例
    browser = await StealthBrowser.create(headless=True)
    async with browser:
        page = await browser.new_page()
        # ... 执行操作
```

### Cookie 存储

Cookie 文件保存在以下位置：

```
cookies/
├── douyin_uploader/account.json
├── xiaohongshu_uploader/account.json
├── kuaishou_uploader/account.json
└── shipinhao_uploader/account.json
```

## 开发约定

### 编码规范

- 遵循 PEP 8 Python 编码规范
- 使用类型注解标注函数参数和返回值
- 添加详细的文档字符串
- 使用异步编程模式（async/await）

### 日志记录

- 使用 `loguru` 日志系统
- 不同平台使用独立的日志文件
- 记录关键操作和错误信息

日志配置位于 `spreado/utils/log.py`。

### 扩展新平台

1. 在 `spreado/publisher/` 目录下创建新平台文件夹
2. 创建上传器类，继承 `BaseUploader`
3. 实现所有抽象属性和方法
4. 在 `spreado/cli/cli.py` 中的 `UPLOADERS` 字典注册新平台

## 故障排除

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| 认证失败 | 重新执行 `spreado login <平台>` |
| 上传失败 | 使用 `--debug` 参数查看详细信息 |
| 找不到浏览器 | 执行 `playwright install chromium` |
| 依赖问题 | 执行 `pip install --upgrade spreado` |
| UI 元素变化 | 平台界面更新可能需要更新选择器 |

### 调试技巧

1. 使用 `--debug` 参数查看详细日志
2. 查看终端输出的错误信息
3. 确保已安装 Playwright 浏览器

### 项目维护

- 保持代码简洁和可读性
- 编写单元测试（如适用）
- 定期更新依赖包
- 关注平台界面变化，及时调整选择器

## 安全考虑

- 妥善保管 Cookie 文件，不要提交到版本控制系统
- 避免在日志中记录敏感信息
- 定期检查依赖包的安全漏洞

## 许可证

本项目遵循 MIT 许可证。
