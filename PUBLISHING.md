# Spreado 发布指南

本指南介绍如何将 Spreado 发布到 PyPI 和 Git Releases，采用混合发布策略。

## 混合发布策略

| 发布渠道 | 目标用户 | 安装方式 | 包类型 |
|---------|---------|---------|--------|
| **PyPI** | Python 开发者 | `pip install spreado` | Wheel 包 |
| **GitHub Releases** | 普通用户 | 下载二进制运行 | 预编译压缩包 |

## 准备工作

### 1. 安装发布工具

```bash
pip install build twine wheel
pip install --upgrade setuptools
pip install pyinstaller
```

### 2. 创建账号

**PyPI 账号：**
- 访问 [PyPI](https://pypi.org) 注册正式账号
- 访问 [Test PyPI](https://test.pypi.org) 注册测试账号（推荐先在测试环境验证）

**GitHub 账号：**
- 确保有 GitHub 账号
- 创建 Personal Access Token（用于 CLI 上传）

### 3. 配置 API 令牌

创建 `~/.pypirc` 文件：

```ini
[distutils]
index-servers = pypi testpypi

[pypi]
username = __token__
password = <your-pypi-api-token>

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = <your-test-pypi-api-token>
```

配置 GitHub CLI 认证：

```bash
gh auth login
```

## 发布流程

### 阶段一：构建并发布 Python Wheel 包

#### 步骤 1：清理旧构建文件

```bash
rm -rf build/ dist/ *.egg-info/
```

#### 步骤 2：构建 Wheel 包

> **注意**：项目目录下存在 `build.py` 文件，会与 Python 标准 `build` 模块冲突。
> 请使用以下方式之一构建 Wheel：

**方式一：使用 pip wheel（推荐）**

```bash
pip wheel . --no-deps -w dist/
```

**方式二：使用标准 build 模块**

```bash
python -m build --wheel
```

**方式三：在项目外构建**

```bash
cd /tmp
python -m build --wheel /path/to/spreado-project
```

构建完成后检查：

```bash
ls dist/
# spreado-1.0.0-py3-none-any.whl
```

#### 步骤 3：先上传到测试 PyPI（推荐）

```bash
twine upload --repository testpypi dist/*
```

#### 步骤 4：测试安装

```bash
pip install --index-url https://test.pypi.org/simple/ spreado
spreado --help
```

#### 步骤 5：确认工作正常后上传正式 PyPI

```bash
twine upload dist/*
```

### 阶段二：构建并发布预编译二进制

#### 步骤 1：在各平台分别构建二进制文件

**Linux x64：**

```bash
python build_binary.py
# 输出: dist/spreado-1.0.0-linux-x64.tar.gz
```

**Windows x64：**

```bash
python build_binary.py
# 输出: dist/spreado-1.0.0-windows-x64.tar.gz
```

**macOS x64：**

```bash
python build_binary.py
# 输出: dist/spreado-1.0.0-macos-x64.tar.gz
```

**macOS arm64 (Apple Silicon)：**

```bash
python build_binary.py
# 输出: dist/spreado-1.0.0-macos-arm64.tar.gz
```

#### 步骤 2：清理临时文件

```bash
rm -f dist/install_browser.sh dist/README.txt
```

只保留 `.tar.gz` 压缩包：

```bash
ls dist/
# spreado-1.0.0-linux-x64.tar.gz
```

#### 步骤 3：上传到 GitHub Releases

**方法一：使用 GitHub CLI（推荐）**

```bash
# 创建 tag 并推送到远程
git tag v1.0.0
git push origin v1.0.0

# 创建 Release 并上传二进制文件
gh release create v1.0.0 \
  dist/*.tar.gz \
  --title "Release v1.0.0" \
  --notes "Release notes here"
```

**方法二：手动上传**

1. 访问 https://github.com/yourname/spreado/releases/new
2. 选择刚推送的 tag v1.0.0
3. 填写 Release 标题和说明
4. 拖拽所有 `dist/spreado-*.tar.gz` 文件到 Assets 区域
5. 点击 Publish release

### 阶段三：一键完整发布

使用 `--release` 参数自动完成所有步骤：

```bash
python build_binary.py --release
```

此命令会：
1. 清理并构建 Wheel 包
2. 构建当前平台的二进制压缩包
3. 提示用户在其他平台构建二进制文件
4. 指导用户完成 PyPI 和 GitHub Releases 发布

## 版本管理

### 更新版本号

编辑 `spreado/__version__.py`：

```python
__version__ = '1.0.0'  # 更新版本号
```

### 版本号规范

遵循语义化版本控制：

| 版本类型 | 说明 | 示例 |
|---------|------|------|
| 主版本 | 不兼容的 API 修改 | 1.0.0 → 2.0.0 |
| 次版本 | 向下兼容的新功能 | 1.0.0 → 1.1.0 |
| 修订号 | 向下兼容的问题修复 | 1.0.0 → 1.0.1 |

### 版本发布流程

```bash
# 1. 更新版本号
vim spreado/__version__.py

# 2. 提交更改
git add spreado/__version__.py
git commit -m "Bump version to 1.0.0"

# 3. 创建 tag
git tag -a v1.0.0 -m "Version 1.0.0"

# 4. 推送到远程
git push origin main --tags

# 5. 开始发布流程
python build_binary.py --release
```

## 快速参考

### 常用命令

```bash
# 构建 Wheel 包（推荐）
pip wheel . --no-deps -w dist/

# 或使用标准 build 模块
python -m build --wheel

# 构建当前平台二进制
python build_binary.py

# 构建 Wheel 并上传测试 PyPI
pip wheel . --no-deps -w dist/
twine upload --repository testpypi dist/*.whl

# 构建 Wheel 并上传正式 PyPI
pip wheel . --no-deps -w dist/
twine upload dist/*.whl

# 一键完整发布
python build_binary.py --release

# 查看帮助
python build_binary.py --help
```

### 文件结构要求

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
│   └── utils/            # 工具模块
│       ├── log.py
│       └── files_times.py
├── pyproject.toml        # 项目配置
├── setup.py              # 兼容配置
├── MANIFEST.in           # 打包清单
├── README.md             # 说明文档
├── LICENSE               # 许可证
├── requirements.txt      # 依赖列表
├── build.py              # PyInstaller 打包脚本
├── build_binary.py       # 二进制分发构建脚本
└── PUBLISHING.md         # 发布指南
```

### 输出文件说明

| 文件类型 | 位置 | 用途 |
|---------|------|------|
| `spreado-1.0.0-py3-none-any.whl` | dist/ | 上传 PyPI |
| `spreado-1.0.0.tar.gz` | dist/ | 上传 PyPI（源码） |
| `spreado-1.0.0-linux-x64.tar.gz` | dist/ | GitHub Releases |
| `spreado-1.0.0-windows-x64.tar.gz` | dist/ | GitHub Releases |
| `spreado-1.0.0-macos-x64.tar.gz` | dist/ | GitHub Releases |
| `spreado-1.0.0-macos-arm64.tar.gz` | dist/ | GitHub Releases |

## 常见问题

### 1. PyPI 上传失败：文件已存在

PyPI 不允许重复上传相同版本号。

**解决方案：** 更新版本号后重新构建上传：

```bash
# 更新版本号
vim spreado/__version__.py

# 重新构建并上传
rm -rf dist/
python -m build
twine upload dist/*
```

### 2. 包导入失败

确保 `pyproject.toml` 中的 `packages` 配置正确：

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["spreado*"]
```

### 3. entry_points 不生效

确保 `pyproject.toml` 配置正确：

```toml
[project.scripts]
spreado = "spreado.cli.cli:main"
```

### 4. 二进制构建失败

确保已安装所有依赖：

```bash
pip install pyinstaller
playwright install chromium
python build.py --clean
```

### 5. 跨平台构建限制

- Windows 打包的文件只能在 Windows 运行
- macOS 打包的文件只能在 macOS 运行
- Linux 打包的文件只能在 Linux 运行
- 如需为其他平台构建，请使用 CI/CD 服务

### 6. GitHub Releases 上传失败

使用 GitHub CLI 认证：

```bash
gh auth login
gh release create v1.0.0 dist/*.tar.gz --title "Release v1.0.0"
```

## 发布后检查清单

### PyPI 检查

- [ ] 访问 https://pypi.org/project/spreado 确认包信息正确
- [ ] 检查文件列表是否包含 wheel 和源码包
- [ ] 测试 pip 安装：`pip install spreado`
- [ ] 测试命令行工具：`spreado --help`

### GitHub Releases 检查

- [ ] 确认 Release 已发布
- [ ] 验证所有平台二进制文件已上传
- [ ] 检查二进制文件大小是否合理
- [ ] 更新项目 README 中的下载链接

## 自动发布（CI/CD）

### GitHub Actions 工作流

创建 `.github/workflows/release.yml`：

```yaml
name: Release

on:
  release:
    types: [created]

jobs:
  build-pypi:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
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

  build-binaries:
    needs: build-pypi
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            platform: linux-x64
          - os: macos-latest
            platform: macos-x64
          - os: macos-14
            platform: macos-arm64
          - os: windows-latest
            platform: windows-x64
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        pip install -e .
        pip install pyinstaller
    - name: Build binary
      run: python build_binary.py
    - name: Upload binary
      uses: softprops/action-gh-release@v2
      with:
        files: dist/*.tar.gz
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 需要的 Secrets

在 GitHub 仓库设置中添加以下 Secrets：

| Secret 名称 | 用途 |
|------------|------|
| `PYPI_API_TOKEN` | PyPI API Token |
| `GITHUB_TOKEN` | GitHub 自动生成 |

## 用户安装指南

### 方式一：pip 安装（推荐）

```bash
pip install spreado

# 使用
spreado --help
spreado login douyin
spreado upload douyin -v video.mp4
```

### 方式二：下载二进制（无需 Python）

1. 访问 https://github.com/yourname/spreado/releases
2. 下载对应平台的压缩包：
   - `spreado-1.0.0-linux-x64.tar.gz` (Linux)
   - `spreado-1.0.0-windows-x64.zip` (Windows)
   - `spreado-1.0.0-macos-x64.tar.gz` (Intel Mac)
   - `spreado-1.0.0-macos-arm64.tar.gz` (Apple Silicon Mac)

3. 解压并运行：

```bash
# Linux/macOS
tar -xzf spreado-1.0.0-linux-x64.tar.gz
cd spreado-1.0.0-linux-x64
./spreado --help

# Windows
# 双击 spreado.exe 或在命令行运行
spreado.exe --help
```

4. 首次使用需要安装浏览器：

```bash
# Linux/macOS
./install_browser.sh

# Windows
install_browser.bat
```

## 联系方式

- GitHub: https://github.com/yourname/spreado
- PyPI: https://pypi.org/project/spreado
- 作者: wangruiyu (wry10150@163.com)
