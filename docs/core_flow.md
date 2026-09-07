# 核心执行流程

Spreado 使用组合式核心架构。平台插件继承 `BasePublisher`，认证、浏览器和页面操作由独立服务负责。

## 组件职责

| 组件 | 职责 |
|---|---|
| `BasePublisher` | 平台契约、认证与发布编排、Task 分发 |
| `AccountContext` | 聚合一个账号的状态、profile、元数据和锁路径 |
| `AccountManager` | 校验账号标识并解析账号级资源路径 |
| `AuthenticationManager` | 恢复状态、验证登录、交互登录、提供已认证页面 |
| `AuthenticationStateStore` | 读写 `account.json` |
| `StealthBrowser` | 系统浏览器发现、CDP 连接、profile 生命周期 |
| `PageActions` | 元素查找、点击、文件注入和轮询等页面操作 |
| 平台插件 | 提供 `AuthenticationConfig` 并实现 `_upload_video()` |

`BasePublisher` 不包含登录选择器，也不实现浏览器细节。平台认证信息集中定义在一个不可变配置对象中：

```python
authentication_config = AuthenticationConfig(
    login_url="https://passport.example.com/login",
    verification_url="https://creator.example.com/publish",
    login_selectors=(".login-form",),
    authenticated_selectors=(".publish-editor",),
    login_url_patterns=(r"/login(?:[/?#]|$)",),
    challenge_selectors=(".captcha",),
)
```

认证判断返回 `AUTHENTICATED`、`UNAUTHENTICATED`、`CHALLENGE` 或 `UNKNOWN`。只有连续两次检测到 `AUTHENTICATED` 才允许进入发布流程；同域名和“暂未发现登录框”不再被当作成功证据。

## 发布流程

`upload_video_flow()` 在同一个浏览器会话中完成全部步骤：

```text
解析 (platform, account_id) 并获取账号锁
        |
使用账号专属 profile 创建 CDP 浏览器会话
        |
恢复 account.json，并复用浏览器 profile
        |
打开 verification_url 验证认证状态
        |
认证无效且 auto_login=True?
   |                    |
  否                   是
返回失败          在当前会话交互登录
                        |
                  保存最新认证状态
                        |
                  调用平台 _upload_video()
```

认证验证和发布不再分别启动浏览器，因此设备指纹、Session Cookie 和页面存储保持一致。锁覆盖完整浏览器生命周期，同一账号不能并发操作，不同账号则可安全并行。

## 登录流程

`login_flow()` 表示“确保已经登录”，不是无条件重新登录：

1. 恢复 `account.json` 中的 Cookie 和 LocalStorage。
2. 使用持久浏览器 profile 打开验证页。
3. 已认证时刷新认证备份并返回。
4. 未认证时打开登录页，等待用户完成操作。
5. 返回验证页二次确认并保存最新状态。

## Task 入口

业务代码可以调用 `BasePublisher.execute(task)`。`Task.account_id` 必须与发布器构造时的 `account_id` 一致；视频任务会分发到 `publish_video()`，再进入 `upload_video_flow()`；图文任务由支持的平台覆盖 `publish_image_text()`。

CLI 仍可直接调用以下稳定接口：

- `login_flow()`
- `verify_cookie_flow(auto_login=False)`
- `upload_video_flow(...)`

## 平台插件

新平台只需要继承 `BasePublisher`：

```python
class ExamplePublisher(BasePublisher):
    authentication_config = AuthenticationConfig(...)

    @property
    def platform_name(self) -> str:
        return "example"

    @property
    def display_name(self) -> str:
        return "示例平台"

    async def _upload_video(self, page, file_path, **options) -> bool:
        await self.actions.upload_file_to_first(
            page, ["input[type=file]"], file_path
        )
        return True
```

平台通用页面操作通过 `self.actions` 显式调用，不再作为 `BasePublisher` 的隐式私有方法。
