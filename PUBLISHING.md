# Spreado 发布指南

本指南介绍如何将 Spreado 发布到 PyPI。

## 准备工作

### 1. 安装发布工具

```bash
pip install build twine
pip install --upgrade setuptools wheel
```

### 2. 创建 PyPI 账号

1. 访问 [PyPI](https://pypi.org) 注册账号
2. 访问 [Test PyPI](https://test.pypi.org) 注册测试账号（推荐先在测试环境发布）

### 3. 配置 API 令牌

创建 `~/.pypirc` 文件：

```ini
[distutils]
index-servers = pypi testpypi

[pypi]
username = __token__
password: <your-api-token>

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password: <your-api-token>
```

## 发布流程

### 方式一：发布 Python 包（推荐）

```bash
# 1. 安装依赖
pip install -e .

# 2. 清理旧构建文件
rm -rf build/ dist/ *.egg-info/

# 3. 构建包
python -m build

# 4. 先上传到测试 PyPI（推荐）
twine upload --repository testpypi dist/*

# 5. 测试安装
pip install --index-url https://test.pypi.org/simple/ spreado

# 6. 确认工作正常
spreado --help

# 7. 上传正式 PyPI
twine upload dist/*

# 8. 验证安装
pip install spreado
spreado --help
```

### 方式二：发布预编译二进制

```bash
# 1. 构建所有平台的二进制文件（跨平台构建）
python build_binary.py --all

# 2. 仅构建当前平台
python build_binary.py

# 3. 创建 Python wheel 包
python build_binary.py --wheels

# 4. 上传到测试 PyPI
twine upload --repository testpypi dist/*

# 5. 测试安装
```

### 方式三：完整发布（推荐）

```bash
# 构建 wheel 包并上传到正式 PyPI
python build_binary.py --release
```

## 版本管理

### 更新版本号

编辑 `spreado/__version__.py`：

```python
__version__ = '2.0.0'  # 更新版本号
```

### 版本号规范

遵循语义化版本：
- 主版本号：不兼容的API修改
- 次版本号：向下兼容的功能性新增
- 修订号：向下兼容的问题修复

## 文件结构要求

发布前确保项目结构正确：

```
spreado-project/
├── spreado/              # 主包目录
│   ├── __init__.py
│   ├── __main__.py
│   ├── __version__.py
│   ├── conf.py           # 配置文件
│   ├── cli/
│   │   └── cli.py        # CLI 命令行实现
│   ├── publisher/        # 各平台上传器
│   │   ├── browser.py    # 浏览器反检测封装
│   │   ├── uploader.py   # 上传器基类
│   │   ├── douyin_uploader/
│   │   ├── xiaohongshu_uploader/
│   │   ├── kuaishou_uploader/
│   │   └── shipinhao_uploader/
│   ├── utils/            # 工具模块
│   │   ├── log.py
│   │   └── files_times.py
│   └── examples/         # 使用示例
├── pyproject.toml        # 项目配置（必需）
├── setup.py              # 兼容配置（可选）
├── MANIFEST.in           # 打包清单
├── README.md             # 说明文档
├── LICENSE               # 许可证
├── requirements.txt      # 依赖列表
├── build.py              # PyInstaller 打包脚本
├── build_binary.py       # 二进制分发构建脚本
└── PUBLISHING.md         # 发布指南
```

## 常见问题

### 1. 上传失败：文件已存在

PyPI 不允许重复上传相同版本号。需更新版本号后重新构建上传。

### 2. 包导入失败

确保 `pyproject.toml` 中的 `packages` 配置正确：

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["spreado*"]
```

### 3. 依赖未正确安装

检查 `pyproject.toml` 中的 `dependencies`：

```toml
dependencies = [
    "playwright>=1.40.0",
    "playwright-stealth>=2.0.1",
    "loguru>=0.7.0",
    # ...其他依赖
]
```

### 4. entry_points 不生效

确保 `pyproject.toml` 配置正确：

```toml
[project.scripts]
spreado = "spreado.cli.cli:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["spreado*"]
```

### 5. 二进制构建失败

确保已安装所有依赖：

```bash
pip install pyinstaller
playwright install chromium
python build.py --clean
```

### 6. 跨平台构建注意事项

- Windows 打包的文件只能在 Windows 运行
- macOS 打包的文件只能在 macOS 运行
- Linux 打包的文件只能在 Linux 运行
- 如需跨平台构建，请使用 CI/CD 服务

## 发布后检查

1. 访问 PyPI 页面确认包信息正确
2. 测试 pip 安装
3. 测试命令行工具
4. 更新 GitHub Release（如有）

## 自动发布（CI/CD）

使用 GitHub Actions 自动发布：

```yaml
name: Publish to PyPI

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    - name: Build package
      run: python -m build
    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}
```

## 联系方式

- GitHub: https://github.com/yourname/spreado
- PyPI: https://pypi.org/project/spreado
- 作者: wangruiyu (wry10150@163.com)
