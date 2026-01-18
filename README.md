# 多平台视频上传工具 - 重构版

基于新设计方案重构的多平台视频上传工具，提供统一的API接口和CLI命令行工具。

## 项目概述

本工具支持将视频同时发布到多个中国社交媒体平台，包括抖音、小红书、快手和腾讯视频。采用面向对象设计，提供统一的基类接口，便于扩展新平台。

## 核心特性

- **统一架构**: 所有平台上传器继承自BaseUploader基类，接口统一
- **模块化设计**: 高内聚低耦合，易于维护和扩展
- **自动化认证**: 支持有头模式登录和无头模式Cookie验证
- **CLI工具**: 提供完整的命令行工具，支持登录、上传、验证等操作
- **详细日志**: 使用loguru记录详细的操作日志
- **错误处理**: 完善的异常处理和资源清理机制

## 项目结构

```
uploader/
├── cli.py                              # CLI命令行工具
├── utils/                              # 工具模块
│   ├── base_uploader.py                # 上传器基类
│   ├── auth_manager.py                # 认证管理器
│   ├── base_social_media.py           # 社交媒体基础配置
│   ├── log.py                         # 日志工具
│   └── files_times.py                 # 文件时间处理
├── uploader/                           # 各平台上传器
│   ├── douyin_uploader/               # 抖音上传器
│   │   ├── __init__.py
│   │   └── uploader.py
│   ├── xiaohongshu_uploader/          # 小红书上传器
│   │   ├── __init__.py
│   │   └── uploader.py
│   ├── kuaishou_uploader/             # 快手上传器
│   │   ├── __init__.py
│   │   └── uploader.py
│   └── tencent_uploader/              # 腾讯视频上传器
│       ├── __init__.py
│       └── uploader.py
├── cookies/                            # Cookie存储目录
│   ├── douyin_uploader/
│   ├── xiaohongshu_uploader/
│   ├── kuaishou_uploader/
│   └── tencent_uploader/
├── examples/                           # 示例代码
├── docs/                               # 文档目录
└── requirements.txt                    # 依赖包列表
```

## 安装配置

### 环境要求

- Python 3.10+
- Playwright 1.57.0+

### 安装依赖

```bash
pip install -r requirements.txt
playwright install
```

## 使用方法

### CLI命令行工具

#### 1. 登录平台

```bash
# 登录抖音平台（会打开浏览器，手动完成登录）
python cli.py douyin login

# 登录小红书平台
python cli.py xiaohongshu login

# 登录快手平台
python cli.py kuaishou login

# 登录腾讯视频平台
python cli.py tencent login
```

#### 2. 查看认证状态

```bash
# 查看抖音认证状态
python cli.py douyin status

# 验证Cookie有效性
python cli.py douyin verify
```

#### 3. 上传视频

```bash
# 基本上传
python cli.py douyin upload video.mp4 --title "我的视频" --content "视频描述" --tags "标签1,标签2"

# 从文本文件读取信息
python cli.py douyin upload video.mp4 --txt video.txt

# 设置封面和定时发布
python cli.py douyin upload video.mp4 --title "我的视频" --thumbnail cover.png --publish-date "2024-12-31 18:00"

# 禁用自动登录
python cli.py douyin upload video.mp4 --title "我的视频" --no-auto-login
```

#### 4. 平台特定参数

```bash
# 抖音：设置地理位置和商品链接
python cli.py douyin upload video.mp4 --title "我的视频" --location "北京市" --product-link "https://..." --product-title "商品名称"

# 腾讯视频：设置分类和保存为草稿
python cli.py tencent upload video.mp4 --title "我的视频" --category "原创" --is-draft
```

### Python API使用

```python
import asyncio
from pathlib import Path
from uploader.douyin_uploader import DouYinUploader

async def main():
    # 初始化上传器
    account_file = Path("cookies/douyin_uploader/account.json")
    uploader = DouYinUploader(account_file=account_file)

    # 确保已登录
    if not await uploader.ensure_login(auto_login=True):
        print("登录失败")
        return

    # 上传视频
    result = await uploader.upload(
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

## 文本文件格式

视频对应的文本文件应按以下格式组织：

```
视频标题
视频描述
标签1,标签2,标签3
```

## 架构设计

### BaseUploader基类

所有平台上传器必须继承自BaseUploader基类，实现以下抽象方法：

- `platform_name`: 平台名称
- `login_url`: 登录页面URL
- `upload_url`: 上传页面URL
- `success_url_pattern`: 上传成功后的URL模式
- `login_selectors`: 登录相关的页面元素选择器列表
- `upload_video`: 上传视频的具体实现

### 认证流程

1. **有头模式登录流程**: 打开浏览器让用户手动登录，监听页面跳转，成功后保存Cookie
2. **无头模式验证Cookie**: 使用Cookie访问上传页面，检测是否需要登录
3. **主上传流程**: 检查认证状态，必要时自动登录，然后执行上传

### 错误处理

- 完善的异常捕获和处理
- 详细的错误日志记录
- 自动资源清理，避免内存泄漏

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

1. 在`uploader/`目录下创建新平台文件夹
2. 创建上传器类，继承自BaseUploader
3. 实现所有抽象方法
4. 在CLI工具中注册新平台

## 故障排除

### 常见问题

1. **认证失败**: 检查Cookie文件是否过期，重新运行登录命令
2. **上传失败**: 确认网络连接和平台服务状态
3. **浏览器检测**: 确保Playwright正确安装并配置了浏览器
4. **依赖问题**: 确认所有依赖包已正确安装

### 调试技巧

- 查看详细的日志输出
- 使用`--headless`参数控制浏览器显示模式
- 检查平台UI元素选择器是否发生变化

## 更新日志

### 重构版

- 创建统一的BaseUploader基类
- 重构所有平台上传器，实现统一接口
- 实现统一的认证管理器
- 提供完整的CLI命令行工具
- 完善错误处理和日志记录
- 优化代码结构和可维护性

## 许可证

本项目遵循MIT许可证。
