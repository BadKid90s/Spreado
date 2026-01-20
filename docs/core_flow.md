# 核心执行流程

本文档详细描述了 Spreado 多平台视频上传工具的核心执行流程。

## 1. 有头模式登录流程

**模式**: 有头模式（headless=False）
**目的**: 用户手动登录并保存 Cookie
**入口**: `BaseUploader.login_flow()`

### 执行步骤

1. 创建 `StealthBrowser` 实例（headless=False）
2. 创建新页面并导航到登录页面 URL
3. 输出提示信息，等待用户在浏览器中完成登录
4. 使用 `page.wait_for_url()` 监听页面跳转到登录成功 URL
5. 登录成功后保存 Cookie 到账户文件（JSON 格式）
6. 清理浏览器资源

### 关键代码

```python
async def login_flow(self) -> bool:
    async with await StealthBrowser.create(headless=False) as browser:
        page = await browser.new_page()
        await page.goto(self.login_url)
        self.logger.info(f"[+] 已打开登录页面，请在浏览器中完成登录操作")
        await page.wait_for_url(
            url=self.login_success_url,
            timeout=60000,
            wait_until="commit"
        )
        self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
        await page.context.storage_state(path=self.cookie_file_path)
        self.logger.info(f"[+] Cookie已保存到: {self.cookie_file_path}")
        return True
```

## 2. 无头模式验证 Cookie 流程

**模式**: 无头模式（headless=True）
**目的**: 验证已保存的 Cookie 是否仍然有效
**入口**: `BaseUploader._verify_cookie()`

### 执行步骤

1. 检查 Cookie 文件是否存在
2. 创建 `StealthBrowser` 实例（headless=True）
3. 从文件加载 Cookie 到浏览器上下文
4. 导航到上传页面
5. 检查页面上是否有登录相关元素（通过 `_login_selectors` 定义）
6. 根据检查结果返回验证成功/失败
7. 清理浏览器资源

### 关键代码

```python
async def _verify_cookie(self) -> bool:
    if not self.cookie_file_path.exists():
        self.logger.warning("[!] 账户文件不存在")
        return False

    async with await StealthBrowser.create(headless=True) as browser:
        await browser.load_cookies_from_file(self.cookie_file_path)
        async with await browser.new_page() as page:
            await page.goto(self.upload_url, timeout=30000)
            login_required = await self._check_login_required(page)
            if login_required:
                self.logger.warning("[!] Cookie已失效")
                return False
            else:
                self.logger.info("[+] Cookie有效")
                return True
```

## 3. 主上传流程

**模式**: 无头模式（headless=True）
**目的**: 执行完整的视频上传流程
**入口**: `BaseUploader.upload_video_flow()`

### 执行步骤

1. 调用 `verify_cookie_flow()` 验证登录状态
2. 创建 `StealthBrowser` 实例（headless=True）
3. 加载 Cookie 到浏览器上下文
4. 创建新页面并导航到上传页面
5. 调用平台特定的 `_upload_video()` 方法执行上传
6. 记录上传结果
7. 清理浏览器资源

### 关键代码

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
    if not await self.verify_cookie_flow(auto_login=auto_login):
        self.logger.error("[!] 登录失败，无法上传视频")
        return False

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

## 4. 平台特定上传流程

**目的**: 执行具体平台的视频上传逻辑
**入口**: 各平台上传器的 `_upload_video()` 方法

### 执行步骤（各平台实现可能不同）

1. 等待上传页面加载完成
2. 上传视频文件
3. 填写视频标题
4. 填写视频描述
5. 设置标签（如有）
6. 设置封面图片（如有）
7. 设置定时发布时间（如有）
8. 点击发布按钮
9. 验证发布结果
10. 返回上传成功/失败状态

## 5. 主认证流程

**目的**: 统一协调认证相关流程
**入口**: `BaseUploader.verify_cookie_flow(auto_login=False)`

### 执行步骤

1. 检查 Cookie 文件是否存在
2. 如果不存在：
   - 如果 `auto_login=True`，执行登录流程
   - 否则返回 False
3. 如果存在，调用 `_verify_cookie()` 验证有效性
4. 如果验证失败：
   - 如果 `auto_login=True`，执行登录流程
   - 否则返回 False
5. 验证成功，返回 True

### 流程图

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

## 6. 流程间关系

```
用户执行上传命令
       │
       ▼
cmd_upload (CLI)
       │
       ▼
upload_video_flow (主上传流程)
       │
       ├─ 调用 verify_cookie_flow (主认证流程)
       │           │
       │           ├─ Cookie文件存在? → _verify_cookie()
       │           │                        │
       │           │                        ├─ 有效 → 返回 True
       │           │                        │
       │           │                        └─ 失效 → auto_login?
       │           │                                   │
       │           │                                   ├─ True → login_flow
       │           │                                   └─ False → 返回 False
       │           │
       │           └─ Cookie文件不存在? → auto_login?
       │                                        │
       │                                        ├─ True → login_flow
       │                                        └─ False → 返回 False
       │
       ▼
     认证成功
       │
       ▼
_upload_video (平台特定上传)
       │
       ▼
   返回上传结果
```

## 7. 辅助方法

### 元素查找

`_find_first_element()` 方法提供灵活的元素查找功能：

```python
async def _find_first_element(
    self,
    page: Page,
    selectors: List[str],
    *,
    timeout: int = 5000,
    state: Literal['visible', 'attached', 'hidden', 'detached'] = 'visible',
    callback: Optional[Callable] = None,
    on_not_found: Optional[Callable] = None,
) -> Optional[Locator]:
```

### 登录状态检查

`_check_login_required()` 检查页面是否需要登录：

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

## 8. 开发调试建议

### 开发阶段

- 使用有头模式（headless=False）便于观察
- 查看详细的日志输出
- 调试页面交互问题

### 生产环境

- 使用无头模式（headless=True）
- 提高执行效率
- 减少资源占用

### 调试技巧

```bash
# 使用调试模式运行
spreado upload douyin --video video.mp4 --title "标题" --debug
```
