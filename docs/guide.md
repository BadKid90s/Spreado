# 多平台视频上传工具 - 项目指南

## 项目概述

这是一个基于Python和Playwright开发的多平台视频上传工具，支持将视频同时发布到多个中国社交媒体平台，包括抖音、小红书、快手和腾讯视频号。项目采用面向对象设计，提供了统一的基类接口，便于扩展新平台。

### 核心特性

- **统一架构**: 所有平台上传器继承自BaseUploader基类，接口统一
- **模块化设计**: 高内聚低耦合，易于维护和扩展
- **自动化认证**: 支持有头模式登录和无头模式Cookie验证
- **CLI工具**: 提供完整的命令行工具，支持登录、上传、验证等操作
- **详细日志**: 使用自定义日志系统记录详细的操作日志
- **错误处理**: 完善的异常处理和资源清理机制
- **反检测技术**: 使用playwright-stealth库绕过网站的自动化检测

## 项目结构

```
uploader/
├── cli/                              # CLI命令行工具
│   └── cli.py
├── conf.py                          # 项目配置文件
├── publisher/                       # 各平台上传器
│   ├── browser.py                   # 浏览器封装与反检测
│   ├── uploader.py                  # 上传器基类
│   ├── douyin_uploader/            # 抖音上传器
│   ├── xiaohongshu_uploader/       # 小红书上传器
│   ├── kuaishou_uploader/          # 快手上传器
│   └── shipinhao_uploader/         # 腾讯视频号上传器
├── utils/                           # 工具模块
│   ├── log.py                      # 日志工具
│   └── files_times.py              # 文件时间处理
├── cookies/                         # Cookie存储目录
├── logs/                            # 日志文件目录
├── examples/                        # 示例代码
├── docs/                            # 文档目录
├── requirements.txt                 # 依赖包列表
├── README.md                        # 项目说明文档
└── QWEN.md                          # 项目指南（当前文件）
```

## 技术栈

- **Python 3.10+**: 主要编程语言
- **Playwright**: 浏览器自动化框架
- **playwright-stealth**: 反检测库
- **loguru**: 日志记录库
- **argparse**: 命令行参数解析

## 安装配置

### 环境要求

- Python 3.10+
- Playwright 1.57.0+

### 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

## 使用方法

### CLI命令行工具

#### 1. 登录平台

```bash
# 登录抖音平台（会打开浏览器，手动完成登录）
python cli/cli.py douyin login

# 登录小红书平台
python cli/cli.py xiaohongshu login

# 登录快手平台
python cli/cli.py kuaishou login

# 登录腾讯视频号平台
python cli/cli.py shipinhao login
```

#### 2. 查看认证状态

```bash
# 查看抖音认证状态
python cli/cli.py douyin status

# 验证Cookie有效性
python cli/cli.py douyin verify
```

#### 3. 上传视频

```bash
# 基本上传
python cli/cli.py douyin upload --file video.mp4 --title "我的视频" --content "视频描述" --tags "标签1,标签2"

# 从文本文件读取信息
python cli/cli.py douyin upload --file video.mp4 --txt video.txt

# 设置封面和定时发布
python cli/cli.py douyin upload --file video.mp4 --title "我的视频" --thumbnail cover.png --publish-date "2024-12-31 18:00"

# 禁用自动登录
python cli/cli.py douyin upload --file video.mp4 --title "我的视频" --no-auto-login
```

### Python API使用

```python
import asyncio
from pathlib import Path
from spreado.publisher.do`uyin_uploader import DouYinUploader


async def main():
    # 初始化上传器
    cookie_file_path = Path("../cookies/douyin_uploader/account.json")
    uploader = DouYinUploader(cookie_file_path=cookie_file_path)

    # 确保已登录
    if not await uploader.verify_cookie_flow(auto_login=True):
        print("登录失败")
        return

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
        print("上传成功")
    else:
        print("上传失败")


asyncio.run(main())
```

## 架构设计

### BaseUploader基类

所有平台上传器必须继承自BaseUploader基类，实现以下抽象方法：

- `platform_name`: 平台名称
- `login_url`: 登录页面URL
- `login_success_url`: 登录成功后的跳转URL
- `upload_url`: 上传页面URL
- `success_url_pattern`: 上传成功后的URL模式
- `_login_selectors`: 登录相关的页面元素选择器列表
- `_upload_video`: 上传视频的具体实现

### 认证流程

1. **有头模式登录流程**: 打开浏览器让用户手动登录，监听页面跳转，成功后保存Cookie
2. **无头模式验证Cookie**: 使用Cookie访问上传页面，检测是否需要登录
3. **主上传流程**: 检查认证状态，必要时自动登录，然后执行上传

### 浏览器封装

项目使用StealthBrowser类封装了Playwright浏览器实例，集成了stealth技术以绕过网站的自动化检测。该类实现了上下文管理器协议，确保资源能够正确释放。

## 开发约定

### 编码规范

- 遵循PEP 8 Python编码规范
- 使用类型注解标注函数参数和返回值
- 添加详细的文档字符串
- 使用异步编程模式（async/await）

### 日志记录

- 使用项目提供的日志工具
- 记录关键操作和错误信息
- 不同平台使用独立的日志文件

### 扩展新平台

1. 在`publisher/`目录下创建新平台文件夹
2. 创建上传器类，继承自BaseUploader
3. 实现所有抽象方法和上传逻辑
4. 在CLI工具中注册新平台

## 故障排除

### 常见问题

1. **认证失败**: 检查Cookie文件是否过期，重新运行登录命令
2. **上传失败**: 确认网络连接和平台服务状态
3. **浏览器检测**: 确保Playwright正确安装并配置了浏览器
4. **依赖问题**: 确认所有依赖包已正确安装
5. **UI元素变化**: 平台界面更新可能导致选择器失效，需要更新相关选择器

### 调试技巧

- 查看详细的日志输出
- 使用`--headless`参数控制浏览器显示模式
- 检查平台UI元素选择器是否发生变化
- 在有头模式下观察实际操作流程

## 项目维护

### 代码质量

- 保持代码简洁和可读性
- 编写单元测试（如适用）
- 定期更新依赖包
- 关注平台界面变化，及时调整选择器

### 安全考虑

- 妥善保管Cookie文件，不要提交到版本控制系统
- 避免在日志中记录敏感信息
- 定期检查依赖包的安全漏洞

## 许可证

本项目遵循MIT许可证。