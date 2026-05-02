# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Spreado is a Python CLI tool and library for automated multi-platform video publishing to Chinese social media platforms (Douyin, Xiaohongshu, Kuaishou, Tencent Shipinhao). It uses Playwright with stealth plugins to automate browser-based uploads.

## Development Commands

This project uses **uv** as the package manager (lockfile: `uv.lock`).

```bash
# Install dependencies (including dev extras)
uv sync --all-extras --dev

# Lint
uv run ruff check .

# Format check
uv run black --check .

# Run a single test
uv run pytest tests/test_<name>.py

# Build standalone binaries (bundles Playwright Chromium)
uv run build_binary.py
```

CI runs `ruff check .` and `black --check .` — these must pass before merging.

## Architecture

Uses a `src` layout: all source lives under `src/spreado/`.

```
src/spreado/
├── __init__.py          # 公共 API 导出
├── __main__.py          # python -m spreado 入口
├── conf.py              # 路径/日志配置常量
├── plugin_loader.py     # 插件自动发现与注册
├── account_manager.py   # 多账号 Cookie 管理
├── core/                # 核心抽象层
│   ├── browser.py       # StealthBrowser 封装
│   ├── uploader.py      # BaseUploader 抽象基类
│   └── base_publisher.py# BasePublisher（Task 驱动接口）
├── models/
│   └── task.py          # 发布任务数据模型
├── plugins/             # 平台插件（内置 + 外部均可）
│   ├── douyin/uploader.py
│   ├── xiaohongshu/uploader.py
│   ├── kuaishou/uploader.py
│   ├── shipinhao/uploader.py
│   └── bilibili/uploader.py  # 示例插件
├── cli/
│   └── cli.py           # CLI 命令（login/verify/upload/list）
└── utils/
    ├── log.py
    └── files_times.py
```

### Class hierarchy

```
BaseUploader (core/uploader.py)   — Template Method pattern
    └── BasePublisher (core/base_publisher.py)  — Task-driven publish API
            └── DouYinUploader / XiaoHongShuUploader / KuaiShouUploader / ShiPinHaoUploader / BilibiliUploader
                (plugins/{platform}/uploader.py)
```

### Uploader pattern (Template Method)

`core/uploader.py` defines `BaseUploader`, an ABC that implements the full login/verify/upload workflow. Each platform subclass must provide:

- **Properties**: `platform_name`, `login_url`, `login_success_url`, `upload_url`, `success_url_pattern`
- **Selectors**: `_login_selectors` — CSS/text selectors to detect the login page
- **Upload logic**: `_upload_video()` — the platform-specific automation

The base class workflows:
1. `login_flow()` — visible browser, waits for login, saves cookies via Playwright `storage_state`
2. `verify_cookie_flow()` — headless browser with saved cookies, checks if login page appears (expired)
3. `upload_video_flow()` — verifies cookies, then delegates to `_upload_video()`

### BasePublisher (`core/base_publisher.py`)

Extends `BaseUploader` with a Task-driven publish API:
- `publish_video(task: Task)` — maps `Task` fields to `upload_video_flow()`
- `publish_image_text(task: Task)` — image+text publishing (platform-specific, opt-in)
- `execute(task: Task)` — unified entry point that dispatches by `task.type`
- `display_name` — human-readable platform name (abstract property)

### Plugin system (`plugin_loader.py`)

`PluginLoader` auto-discovers all non-abstract `BasePublisher` subclasses by scanning:
1. Built-in modules listed in `_BUILTIN_MODULES`
2. Any `uploader.py` found in subdirectories of `plugins/`

Use `get_plugin_loader()` for the global singleton. External plugins can be dropped into `plugins/` without any registration code.

### Account manager (`account_manager.py`)

Manages multi-account cookie storage with the directory structure:

```
cookies/
├── douyin/
│   └── default/
│       ├── account.json   # Playwright storage_state
│       └── meta.json      # UA, fingerprint, created_at
├── xiaohongshu/
│   └── default/
│       └── account.json
└── ...
```

`AccountManager.migrate_legacy_cookies()` handles migration from the old `{platform}_uploader/account.json` layout.

### Task model (`models/task.py`)

`Task` is a dataclass encapsulating all publish parameters: `title`, `content`, `tags`, `media_files`, `thumbnail_path`, `publish_date`, `type` (`"video"` or `"image_text"`).

### StealthBrowser (`core/browser.py`)

Wraps Playwright with `playwright-stealth` anti-detection. Browser resolution priority: `executable_path` param > `channel` param > env vars > system auto-detect > bundled Chromium.

### CLI (`cli/cli.py`)

Argparse-based with four subcommands: `list`, `login`, `verify`, `upload`. Platform choices are resolved dynamically from `PluginLoader` — no hardcoded platform lists. Entry point defined in `pyproject.toml` as `spreado = "spreado.cli.cli:main"`. Also runnable via `python -m spreado`.

### Configuration (`conf.py`)

Defines `BASE_DIR`, `COOKIES_DIR`, `LOGS_DIR`, `PLUGINS_DIR`, `LOG_LEVEL`. Cookies are stored under `cookies/<platform>/<account_name>/account.json` relative to `BASE_DIR`.

### Utilities (`utils/`)

- `log.py` — loguru-based logger helpers
- `files_times.py` — path resolution, title/hashtag parsing from `.txt` files, schedule generation

## Adding a New Platform

1. Create `src/spreado/plugins/<platform>/uploader.py`
2. Subclass `BasePublisher` and implement all abstract properties and `_upload_video()`
3. The `PluginLoader` will auto-discover the new class on next load — **no registration needed**

See `plugins/bilibili/uploader.py` for a documented example skeleton.
