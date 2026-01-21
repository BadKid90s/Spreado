# 登录流程实现详解

本文档详细描述 Spreado 多平台视频上传工具中的登录认证流程实现。

## 1. 概述

登录认证是 Spreado 的核心功能之一，负责管理用户在各平台的登录状态。整个认证系统包含以下组件：

| 组件 | 说明 |
|------|------|
| `login_flow()` | 有头模式登录流程，用户手动登录 |
| `verify_cookie_flow()` | Cookie 验证流程 |
| `_verify_cookie()` | 无头模式验证 Cookie 有效性 |
| `StealthBrowser` | 浏览器封装类，集成反检测技术 |

## 2. 有头模式登录流程

**方法**: `BaseUploader.login_flow()`
**模式**: 有头模式（headless=False）
**返回值**: `bool` - 登录是否成功

### 2.1 方法签名

```python
async def login_flow(self) -> bool:
```

### 2.2 实现步骤

1. **初始化浏览器**: 创建 `StealthBrowser` 实例（headless=False）
2. **打开登录页面**: 创建新页面并导航到登录 URL
3. **等待用户登录**: 输出提示信息，等待用户在浏览器中完成登录
4. **监听跳转**: 使用 `page.wait_for_url()` 等待页面跳转到登录成功 URL
5. **保存 Cookie**: 登录成功后保存 Cookie 到账户文件
6. **清理资源**: 正确关闭浏览器上下文

### 2.3 关键代码

```python
async def login_flow(self) -> bool:
    try:
        async with await StealthBrowser.create(headless=False) as browser:
            page = await browser.new_page()
            await page.goto(self.login_url)
            self.logger.info(f"[+] 已打开登录页面，请在浏览器中完成登录操作")

            # 等待页面跳转到登录成功 URL
            await page.wait_for_url(
                url=self.login_success_url,
                timeout=60000,
                wait_until="commit"
            )

            # 确保目录存在
            self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存 Cookie（包含 storage_state）
            await page.context.storage_state(path=self.cookie_file_path)
            self.logger.info(f"[+] Cookie已保存到: {self.cookie_file_path}")
            self.logger.info("[+] 登录成功，Cookie已保存")
            return True
    except (Error, Exception) as e:
        self.logger.error(f"[!] 登录过程中出错: {e}")
        return False
```

### 2.4 技术要点

- **URL 监听**: 使用 `wait_for_url()` 等待特定 URL 出现
- **超时设置**: 超时时间为 60 秒
- **Storage State**: 使用 `context.storage_state()` 保存完整的浏览器状态
- **异常处理**: 捕获所有异常并记录日志

## 3. Cookie 验证流程

### 3.1 方法签名

```python
async def verify_cookie_flow(self, auto_login: bool = False) -> bool:
```

**参数**:
- `auto_login`: 是否在 Cookie 无效时自动执行登录流程

**返回值**: `bool` - 是否已登录

### 3.2 执行流程

```
verify_cookie_flow(auto_login)
       │
       ├─ Cookie文件不存在?
       │     ├─ 是 → auto_login=True? → 执行 login_flow
       │     │                        └─ 否 → 返回 False
       │     │
       │     └─ 否 → 调用 _verify_cookie()
       │                  │
       │                  ├─ Cookie有效 → 返回 True
       │                  │
       │                  └─ Cookie无效 → auto_login=True?
       │                                 ├─ 是 → 执行 login_flow
       │                                 └─ 否 → 返回 False
```

### 3.3 关键代码

```python
async def verify_cookie_flow(self, auto_login: bool = False) -> bool:
    # 检查 Cookie 文件是否存在
    if not self.cookie_file_path.exists():
        self.logger.warning("[!] 账户文件不存在")
        if auto_login:
            return await self.login_flow()
        return False

    # 验证 Cookie 有效性
    if await self._verify_cookie():
        return True

    # Cookie 无效时是否自动登录
    if auto_login:
        return await self.login_flow()

    return False
```

## 4. 无头模式验证 Cookie

**方法**: `BaseUploader._verify_cookie()`
**模式**: 无头模式（headless=True）
**返回值**: `bool` - Cookie 是否有效

### 4.1 实现步骤

1. **检查文件**: 验证 Cookie 文件是否存在
2. **初始化浏览器**: 创建 `StealthBrowser` 实例（headless=True）
3. **加载 Cookie**: 从文件加载 Cookie 到浏览器上下文
4. **访问上传页**: 导航到上传页面
5. **检测登录状态**: 检查页面是否包含登录相关元素
6. **返回结果**: 根据检测结果返回验证状态

### 4.2 关键代码

```python
async def _verify_cookie(self) -> bool:
    try:
        if not self.cookie_file_path.exists():
            self.logger.warning("[!] 账户文件不存在")
            return False

        self.logger.info("[+] 开始验证Cookie有效性")

        async with await StealthBrowser.create(headless=True) as browser:
            await browser.load_cookies_from_file(self.cookie_file_path)
            async with await browser.new_page() as page:
                self.logger.info("[+] 打开上传页面")
                await page.goto(self.upload_url, timeout=30000)

                # 检查是否需要登录
                login_required = await self._check_login_required(page)
                if login_required:
                    self.logger.warning("[!] Cookie已失效")
                    return False
                else:
                    self.logger.info("[+] Cookie有效")
                    return True
    except (Error, Exception) as e:
        self.logger.error(f"[!] 验证Cookie时出错: {e}")
        return False
```

### 4.3 登录检测机制

`_check_login_required()` 方法通过检查页面上是否有登录相关元素来判断用户是否需要重新登录：

```python
async def _check_login_required(self, page: Page) -> bool:
    for selector in self._login_selectors:
        try:
            element = page.locator(selector)
            if await element.count() > 0:
                if await element.first.is_visible():
                    return True
        except Error:
            continue
    return False
```

每个平台实现需要提供 `_login_selectors` 属性，定义用于检测登录状态的选择器列表。

## 5. 登录相关选择器

各平台上传器需要实现 `_login_selectors` 属性，定义用于检测是否需要登录的元素选择器。

### 5.1 选择器定义示例

```python
@property
def _login_selectors(self) -> List[str]:
    return [
        "selector_for_login_button",
        "selector_for_login_form",
        "another_login_related_selector",
    ]
```

### 5.2 选择器匹配逻辑

1. 遍历选择器列表
2. 使用 `page.locator(selector)` 定位元素
3. 检查元素是否存在且可见
4. 任一选择器匹配成功即认为需要登录

## 6. 主上传流程中的认证

`upload_video_flow()` 方法整合了认证和上传流程：

```python
async def upload_video_flow(
    self,
    file_path: str | Path,
    title: str = "",
    content: str = "",
    tags: List[str] = None,
    publish_date: Optional[datetime] = None,
    thumbnail_path: Optional[str | Path] = None,
    auto_login: bool = False,
) -> bool:
    self.logger.info(f"[+] 开始上传视频: {title}")

    # 验证登录状态
    if not await self.verify_cookie_flow(auto_login=auto_login):
        self.logger.error("[!] 登录失败，无法上传视频")
        return False

    # 执行上传
    async with await StealthBrowser.create(headless=True) as browser:
        await browser.load_cookies_from_file(self.cookie_file_path)
        async with await browser.new_page() as page:
            await page.goto(self.upload_url)
            result = await self._upload_video(
                page=page,
                file_path=file_path,
                title=title,
                content=content,
                tags=tags,
                publish_date=publish_date,
                thumbnail_path=thumbnail_path
            )
            return result
```

## 7. Cookie 文件格式

### 7.1 文件路径

```
cookies/
├── douyin_uploader/account.json
├── xiaohongshu_uploader/account.json
├── kuaishou_uploader/account.json
└── shipinhao_uploader/account.json
```

### 7.2 文件格式

支持两种格式：

**格式 1: Playwright storage_state**
```json
{
    "cookies": [...],
    "origins": [...]
}
```

**格式 2: 直接 Cookie 列表**
```json
[
    {
        "name": "session",
        "value": "xxx",
        "domain": ".example.com",
        ...
    }
]
```

## 8. 错误处理策略

### 8.1 登录失败

```python
try:
    # 登录逻辑
except (Error, Exception) as e:
    self.logger.error(f"[!] 登录过程中出错: {e}")
    return False
```

### 8.2 Cookie 验证失败

```python
if login_required:
    self.logger.warning("[!] Cookie已失效")
    return False
```

### 8.3 资源清理

所有浏览器操作使用上下文管理器确保资源正确释放：

```python
async with await StealthBrowser.create(headless=False) as browser:
    # 浏览器操作
# 自动关闭浏览器上下文
```

## 9. 日志记录

### 9.1 信息日志

- `[+] 已打开登录页面，请在浏览器中完成登录操作`
- `[+] Cookie已保存到: {path}`
- `[+] 登录成功，Cookie已保存`
- `[+] Cookie有效`

### 9.2 警告日志

- `[!] 账户文件不存在`
- `[!] Cookie已失效`

### 9.3 错误日志

- `[!] 登录过程中出错: {error}`
- `[!] 验证Cookie时出错: {error}`

## 10. 扩展性考虑

### 10.1 统一接口

- 所有平台继承 `BaseUploader` 基类
- 使用统一的登录和验证流程
- 通过抽象属性实现平台特定的 URL 配置

### 10.2 易于维护

- 代码结构清晰，职责分离
- 便于添加新的平台支持
- 选择器可配置，易于更新
