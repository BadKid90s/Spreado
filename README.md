# 多平台视频发布工具

## 项目概述

多平台视频发布工具是一个基于Python和Gradio开发的图形化界面应用程序，旨在简化视频内容创作者在多个社交媒体平台上的视频发布流程。

该工具支持一键将视频发布到抖音、小红书、快手、微信视频号等多个主流平台，大大提高内容发布的效率。

## 核心功能

- **多平台支持**: 支持抖音、小红书、快手、微信视频号等主流社交媒体平台
- **统一界面操作**: 通过单一界面完成所有平台的视频发布操作
- **视频预览**: 支持上传视频的实时预览功能
- **智能信息提取**: 自动从视频文件名或关联的文本文件中提取标题和标签
- **定时发布**: 支持设置定时发布功能，可预设发布时间
- **批量操作**: 支持一次操作发布到多个平台
- **日志记录**: 详细的发布过程日志，便于跟踪发布状态

## 技术栈

- **核心语言**: Python 3.10+
- **前端框架**: Gradio 6.1.0
- **异步处理**: asyncio
- **文件处理**: 自定义文件处理模块
- **平台SDK**: 各平台专用的上传SDK

## 环境要求

- Python 3.10 或更高版本
- 支持的操作系统: Windows, macOS, Linux
- 网络连接(用于平台API调用)
- 各平台的账号权限和认证信息

## 安装步骤

### 1. 克隆项目

```bash
git clone <repository-url>
cd uploader
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置平台账号

在`cookies`目录下为各平台创建相应的账号配置文件:
- 抖音: `cookies/douyin_uploader/account.json`
- 小红书: `cookies/xiaohongshu_uploader/account.json`

## 使用指南

### 启动应用

```bash
python ui/app.py
```

应用将在 http://0.0.0.0:7860 启动，默认情况下可以从任何网络接口访问。

### 使用步骤

1. **上传视频**: 点击"上传视频文件并预览"选择要发布的视频文件
2. **上传封面**(可选): 上传自定义封面图片
3. **编辑信息**: 根据需要修改视频标题、描述和标签
4. **设置选项**: 
   - 启用定时发布并设置时间(可选)
   - 选择要发布的平台
5. **开始发布**: 点击"🚀 开始发布"按钮

## 配置说明

### 目录结构

```
uploader/
├── ui/                 # 用户界面代码
├── uploader/           # 各平台上传实现
│   ├── douyin_uploader/
│   ├── xiaohongshu_uploader/
│   └── ...
├── utils/              # 工具函数
├── cookies/            # 平台账号配置
├── conf.py             # 项目配置
└── requirements.txt    # 依赖列表
```

### 平台配置

每个平台需要独立的配置文件，通常包含:
- 账号认证信息
- Cookie数据
- 平台特定的配置参数

## 常见问题解答(FAQ)

### Q: 如何解决"ModuleNotFoundError"错误?

A: 确保已正确安装所有依赖包:
```bash
pip install -r requirements.txt
```

### Q: 视频上传失败怎么办?

A: 检查以下几点:
1. 网络连接是否正常
2. 平台账号配置是否正确
3. 视频格式是否符合平台要求
4. 账号是否有上传权限

### Q: 如何添加新的发布平台?

A: 需要:
1. 在`uploader`目录下创建新的平台文件夹
2. 实现该平台的上传逻辑
3. 在UI中添加平台选择项

### Q: 应用启动后无法访问?

A: 检查:
1. 应用是否正常启动(查看控制台输出)
2. 防火墙设置
3. 端口是否被占用(默认端口7860)

## 贡献指南

欢迎任何形式的贡献!请遵循以下步骤:

### 提交Issue
- 使用清晰的标题描述问题
- 详细说明复现步骤
- 提供相关错误日志

### 提交Pull Request
1. Fork项目仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 代码规范
- 遵循PEP 8编码规范
- 添加必要的注释和文档
- 确保代码通过所有测试