# Spreado 项目开发指南

本文档为 Spreado 多平台视频上传工具的开发指南，涵盖项目结构、技术架构、使用方法等内容。

## 项目概述

Spreado 是一个基于 Python、系统 Chromium 浏览器和 CDP 的多平台视频上传工具，支持将视频发布到抖音、小红书、快手和腾讯视频号等中国社交媒体平台。

### 核心特性

- **统一架构**: 所有平台发布器继承自 `BasePublisher`，接口统一
- **模块化设计**: 高内聚低耦合，易于维护和扩展
- **自动化认证**: 支持有头模式登录和无头模式 Cookie 验证
- **CLI 工具**: 提供完整的命令行工具，支持登录、上传、验证等操作
- **详细日志**: 使用 loguru 日志系统记录详细的操作日志
- **真实浏览器**: 通过 CDP 控制系统安装的 Chrome、Edge、Chromium 或 Brave

## 项目结构

```
Spreado/
├── src/spreado/                 # 主包目录（src 布局）
│   ├── __init__.py              # 公共 API 导出（含版本号）
│   ├── __main__.py              # python -m spreado 入口
│   ├── conf.py                  # 路径/日志配置常量
│   ├── plugin_loader.py         # 插件自动发现与注册
│   ├── account_manager.py       # 多账号 Cookie 管理
│   ├── core/                    # 核心抽象层
│   │   ├── __init__.py
│   │   ├── browser.py           # StealthBrowser 浏览器封装与反检测
│   │   ├── authentication.py    # 认证配置、状态存储与会话管理
│   │   ├── page_actions.py      # 通用页面操作
│   │   └── base_publisher.py    # BasePublisher 发布流程与 Task 接口
│   ├── models/                  # 数据模型
│   │   └── task.py              # Task 发布任务模型
│   ├── plugins/                 # 平台插件（内置 + 外部均可）
│   │   ├── douyin/uploader.py   # 抖音上传器
│   │   ├── xiaohongshu/uploader.py  # 小红书上传器
│   │   ├── kuaishou/uploader.py # 快手上传器
│   │   ├── shipinhao/uploader.py# 视频号上传器
│   │   └── bilibili/uploader.py # B站上传器（示例插件）
│   ├── cli/                     # CLI 命令行工具
│   │   └── cli.py               # CLI 实现（list/login/verify/upload）
│   └── utils/                   # 工具模块
│       ├── log.py               # 日志工具
│       └── files_times.py       # 文件时间处理
├── docs/                        # 文档目录
├── pyproject.toml               # 项目配置（hatchling + uv）
├── build_binary.py              # PyInstaller 打包脚本
└── README.md                    # 项目说明文档
```

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 主要编程语言 |
| Chrome DevTools Protocol | 连接并控制系统浏览器 |
| Playwright | 将现有 Page/Locator 操作适配为 CDP 调用 |
| playwright-stealth | 页面初始化反检测配置 |
| loguru | 日志记录 |
| argparse | 命令行参数解析 |
| pytz | 时区处理 |

## 环境配置

### 系统要求

- Python 3.10 或更高版本
- 操作系统：Windows、macOS、Linux
- 浏览器：系统已安装的 Chrome、Edge、Chromium 或 Brave

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
from spreado.plugins.douyin.uploader import DouYinUploader


async def upload_video():
    # 初始化上传器
    uploader = DouYinUploader(
        cookie_file_path=Path("cookies/douyin/default/account.json")
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

### BasePublisher 基类

所有平台发布器必须继承 `BasePublisher`，提供平台信息、认证配置和发布实现：

#### 平台契约

| 成员 | 类型 | 说明 |
|------|------|------|
| `platform_name` | str | 平台名称 |
| `display_name` | str | 平台显示名称 |
| `authentication_config` | AuthenticationConfig | 登录 URL、验证 URL 和认证 DOM 信号 |
| `_upload_video()` | coroutine | 平台特定的视频发布实现 |

#### 核心方法

| 方法 | 说明 |
|------|------|
| `login_flow()` | 有头模式登录流程 |
| `verify_cookie_flow(auto_login=False)` | 验证 Cookie，必要时自动登录 |
| `upload_video_flow()` | 主上传流程 |
| `_upload_video()` | 平台特定的上传实现（抽象方法） |

### StealthBrowser 浏览器封装

`StealthBrowser` 启动系统浏览器并通过 CDP 连接，主要特性：

- **系统浏览器**: 不启动或回退到 Playwright 内置 Chromium
- **持久配置**: 使用 Spreado 专用 profile，跨运行保留浏览器状态
- **隔离运行**: 不接管用户日常 Chrome 配置
- **反检测**: 集成 playwright-stealth 页面初始化配置
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
├── douyin/
│   └── default/
│       ├── account.json   # Playwright storage_state（cookies）
│       ├── meta.json      # 账号元数据
│       └── .account.lock  # 同账号进程互斥锁
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

> 支持多账号：使用 `--account <账号ID>` 选择账号。Cookie 位于 `cookies/{platform}/{account_id}`，浏览器 profile 位于系统应用数据目录的 `browser-profiles/{platform}/{account_id}`。旧版 `{platform}_uploader/account.json` 会由默认账号兼容读取，也可通过 `AccountManager.migrate_legacy_cookies()` 显式迁移。

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

1. 在 `src/spreado/plugins/` 目录下创建新平台文件夹，如 `my_platform/`
2. 在其中创建 `uploader.py`，定义上传器类继承 `BasePublisher`
3. 实现所有抽象属性（`platform_name`、`display_name`、`login_url` 等）和 `_upload_video()` 方法
4. **无需额外注册**：`PluginLoader` 会在启动时自动发现并加载

参考 `plugins/bilibili/uploader.py` 中的示例框架。

## 故障排除

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| 认证失败 | 重新执行 `spreado login <平台>` |
| 上传失败 | 使用 `--debug` 参数查看详细信息 |
| 找不到浏览器 | 安装受支持的系统浏览器，或设置 `SPREADO_BROWSER_PATH` |
| 依赖问题 | 执行 `pip install --upgrade spreado` |
| UI 元素变化 | 平台界面更新可能需要更新选择器 |

### 调试技巧

1. 使用 `--debug` 参数查看详细日志
2. 查看终端输出的错误信息
3. 确保已安装 Chrome、Edge、Chromium 或 Brave

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
