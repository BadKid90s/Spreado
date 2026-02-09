# Spreado 发布指南

本指南介绍如何使用 `uv` 框架将 Spreado 发布到 PyPI 和 GitHub Releases。

## 混合发布策略

| 发布渠道 | 目标用户 | 安装方式 | 包类型 |
|---------|---------|---------|--------|
| **PyPI** | Python 开发者 | `uv tool install spreado` 或 `pip install spreado` | Wheel / SDist |
| **GitHub Releases** | 普通用户 | 下载二进制运行 | 预编译压缩包 (.tar.gz) |

## 准备工作

### 1. 安装 uv
确保已安装 [uv](https://github.com/astral-sh/uv)：
```bash
curl -LsSf https://astral-sh.uv.io/install.sh | sh
```

### 2. 配置 PyPI 令牌
推荐使用环境变量：
```bash
export UV_PUBLISH_TOKEN=your-pypi-api-token
```

## 发布流程

### 阶段一：发布到 PyPI

#### 步骤 1：版本号更新
在 `src/spreado/__init__.py` 中更新版本号。

#### 步骤 2：构建并发布
```bash
# 清理并构建
rm -rf dist/
uv build

# 上传到测试 PyPI (可选)
uv publish --publish-url https://test.pypi.org/legacy/

# 上传到正式 PyPI
uv publish
```

### 阶段二：构建预编译二进制

#### 步骤 1：本地构建
运行专用的打包脚本（需根据当前平台执行）：
```bash
uv run build_binary.py
```
该脚本会生成 `dist/spreado-v1.x.x-<platform>-<arch>.tar.gz`。

#### 步骤 2：上传到 GitHub Releases
使用 GitHub CLI：
```bash
# 创建 tag
git tag v1.0.0
git push origin v1.0.0

# 创建 Release 并上传
gh release create v1.0.0 dist/*.tar.gz --title "Release v1.0.0" --notes "版本更新说明"
```

---

## 自动化发布 (CI/CD)

项目已配置 GitHub Actions (`.github/workflows/release.yml`)。
当你在 GitHub 上创建一个新的 **Release** 或推送带有版本号的 **Tag** 时，GitHub 会自动完成：
1. `uv build` 并发布到 PyPI。
2. 多平台编译（Linux, Windows, macOS）并上传到 GitHub Release Assets。

## 常见问题

1. **包导入由于 src 目录结构失败？**
   项目已采用 `src` 布局，本地开发请使用 `uv run spreado` 或 `uv run -e .`。

2. **如何添加新依赖？**
   使用 `uv add <dependency>`，它会自动更新 `pyproject.toml` 和 `uv.lock`。
