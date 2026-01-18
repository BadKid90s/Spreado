from huggingface_hub import login

# 多平台视频上传工具 - 项目文档

## 项目概述

多平台视频上传工具是一个基于Python和Playwright开发的自动化工具，旨在帮助内容创作者将视频同时发布到多个中国社交媒体平台，包括抖音、小红书、快手和腾讯视频。该项目支持通过图形界面（Gradio）或命令行脚本进行操作。

### 核心功能
1. **多平台支持**: 支持抖音、小红书、快手、腾讯视频等主流平台
2. **自动化上传**: 使用Playwright模拟浏览器操作进行视频上传
3. **定时发布**: 支持设置未来时间发布视频
4. **自定义封面**: 支持上传自定义视频封面
5. **标签处理**: 从文本文件自动提取标题、描述和标签
6. **Cookie认证**: 使用存储的Cookie进行平台认证
7. **详细日志**: 提供完整的上传过程日志记录

### 技术栈
- **编程语言**: Python 3.10+
- **浏览器自动化**: Playwright 1.57.0
- **异步处理**: asyncio
- **日志管理**: loguru

## 项目结构

```
uploader/
├── cookies/                  # 存储各平台认证信息
│   ├── douyin_uploader/      # 抖音认证文件
│   ├── kuaishou_uploader/    # 快手认证文件
│   ├── tencent_uploader/     # 腾讯视频认证文件
│   └── xiaohongshu_uploader/ # 小红书认证文件
├── examples/                 # 示例脚本
│   ├── videos/               # 示例视频文件
│   ├── get_*_cookie.py       # 获取各平台认证的脚本
│   └── upload_video_to_*.py  # 各平台上传示例脚本
├── uploader/                 # 各平台上传实现
│   ├── douyin_uploader/      # 抖音上传模块
│   ├── kuaishou_uploader/    # 快手上传模块
│   ├── tencent_uploader/     # 腾讯视频上传模块
│   └── xiaohongshu_uploader/ # 小红书上传模块
├── utils/                    # 工具函数
├── requirements.txt          # 依赖包列表
├── README.md                 # 项目说明文档
```

## 架构设计

### 基础类结构
- `BaseUploader`: 所有上传器的基类，定义了通用方法和属性
- 各平台上传器: 继承自BaseUploader，实现平台特定的上传逻辑

### 浏览器管理
- **有头模式**: 用于需要人工操作的场景（如获取cookie、登录验证）
- **无头模式**: 用于自动化操作（如视频上传）


### 认证机制
- 每个平台使用独立的Cookie文件进行身份验证
- 通过`get_*_cookie.py`脚本获取和更新认证信息
- Cookie文件存储在`cookies/*_uploader/`目录下

## 使用方法

### 环境配置
```bash
pip install -r requirements.txt
playwright install
```

### 平台认证设置
1. 运行对应的`get_*_cookie.py`脚本获取认证信息
2. 将生成的认证文件放置到相应目录：
   - 抖音: `cookies/douyin_uploader/account.json`
   - 小红书: `cookies/xiaohongshu_uploader/account.json`
   - 快手: `cookies/kuaishou_uploader/account.json`
   - 腾讯视频: `cookies/tencent_uploader/account.json`

### 命令行使用
```python
import asyncio
from pathlib import Path
from uploader.douyin_uploader.main import douyin_setup, DouYinVideo
from utils.files_times import get_title_and_hashtags

# 设置路径
file_path = Path("path/to/your/video.mp4")
account_file = Path("cookies/douyin_uploader/account.json")
txt_path = Path("path/to/your/video.txt")  # 包含标题、描述和标签

# 获取视频信息
title, content, tags = get_title_and_hashtags(str(txt_path))


# 初始化上传器
cookie_path = Path("path")
app = DouYinUploader(cookie_path)

# 登录逻辑
app.login()

# 上传逻辑
app.upload(
    title=title,
    content=content,
    tags=tags,
    file_path=file_path,
)

```

### 文本文件格式
视频对应的文本文件应按以下格式组织：
```
视频标题
视频描述
标签1,标签2,标签3
```

## 开发约定

### 编码规范
- 遵循PEP 8 Python编码规范
- 使用有意义的变量和函数命名
- 添加适当的注释和文档字符串
- 方法和函数要具有参数和返回值类型声明
- 使用统一的日志方式记录日志
- 使用playwright要注意资源清理
- 使用面向对象的思想进行功能开发
- 使用设计模式提高程序的扩展性
- 实现高内聚低耦合的代码设计。

### 异步编程
- 所有I/O操作使用async/await模式
- 合理处理异步上下文管理器

### 错误处理
- 实现适当的异常捕获和处理
- 提供清晰的错误信息

### 日志记录
- 使用项目提供的日志工具记录关键操作
- 不同平台使用独立的日志文件

### 开发调试
- 启动Debug模式后
- 使用统一的配置，打开所有playwright示例的有头模式
- 打印debug类型的日志

## 扩展开发

### 添加新平台
1. 在`uploader/`目录下创建新平台文件夹
2. 实现平台特定的上传逻辑
3. 创建对应的认证和Cookie管理功能
4. 添加示例脚本

### 功能增强
- 支持更多视频格式
- 增加批量上传功能
- 添加上传进度显示
- 实现更智能的标签建议

## 故障排除

### 常见问题
1. **认证失败**: 检查Cookie文件是否过期，重新运行`get_*_cookie.py`
2. **上传失败**: 确认网络连接和平台服务状态
3. **浏览器检测**: 确保Playwright正确安装并配置了浏览器
4. **依赖问题**: 确认所有依赖包已正确安装

### 调试技巧
- 查看详细的日志输出
- 使用Playwright的调试模式
- 检查平台UI元素选择器是否发生变化

## 项目维护

### 更新策略
- 定期检查各平台UI变化，更新选择器
- 跟踪Playwright版本更新
- 监控平台API变化

### 安全考虑
- 妥善保管认证文件
- 不要在版本控制系统中提交敏感信息
- 定期更换认证凭据

## 流程说明


### 新流程设计（参考[新流程梳理](./新流程梳理.md)）
- **有头模式登录流程**: 用于手动登录和保存Cookie
- **无头模式验证Cookie流程**: 验证Cookie有效性
- **无头模式上传视频流程**: 执行视频上传
- **主流程**: 协调以上各子流程的执行

## 测试文件
项目包含多个测试文件用于验证各项功能：
- `test_browser_management.py`: 测试浏览器管理功能
- `test_fixed_navigate.py`: 测试修复后的页面跳转功能
- `test_optimized_browser_management.py`: 测试优化后的浏览器管理功能
- 其他测试文件用于验证特定功能的正确性

## 依赖项
- Playwright: 用于浏览器自动化
- loguru: 用于日志记录
- 其他标准库和第三方库（详见requirements.txt）