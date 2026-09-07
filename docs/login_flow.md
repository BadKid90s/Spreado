# 登录与认证状态

认证代码位于 `core/authentication.py`，与发布器实现分离。

## 状态来源

认证会同时使用两类持久状态：

| 状态 | 用途 |
|---|---|
| 浏览器 profile | 浏览器原生 Cookie、站点存储和设备状态，是主要状态来源 |
| `account.json` | Playwright storage state 备份，用于恢复 Session Cookie 和 LocalStorage |

默认浏览器 profile 在 Windows 上位于 `%LOCALAPPDATA%\Spreado\browser-profile`。`account.json` 默认写入当前运行目录下的 `cookies/{platform}_uploader/`。

## AuthenticationConfig

每个平台用一个配置对象声明认证规则：

```python
AuthenticationConfig(
    login_url="...",
    verification_url="...",
    login_selectors=(...),
    authenticated_selectors=(...),
    browser_channel=None,
)
```

- `login_url`：需要人工认证时打开的页面。
- `verification_url`：用于确认认证状态的页面，通常也是发布入口。
- `login_selectors`：出现任意一个即表示仍需登录。
- `authenticated_selectors`：出现任意一个即表示已经登录。
- `browser_channel`：可选的系统浏览器类型。

## 验证顺序

`AuthenticationManager` 打开验证页后按以下顺序判断：

1. 登录后元素可见，认证有效。
2. 登录元素可见，认证无效。
3. 页面仍停留在验证域名且没有登录元素，认证有效。
4. 未配置登录后元素且没有登录元素，使用兼容性兜底。
5. 其他状态保守判定为无效。

## 公开流程

### login_flow

先尝试恢复并验证已有状态。只有状态无效时才打开登录页等待用户操作。登录完成后会返回验证页二次确认并保存状态。

### verify_cookie_flow

在无头浏览器中恢复并验证状态。设置 `auto_login=True` 时，验证失败后改用有头浏览器执行交互登录。

### upload_video_flow

通过 `AuthenticationManager.authenticated_page()` 获得已认证页面。恢复、验证、可选登录和实际发布始终发生在同一个浏览器会话中。

## 状态文件格式

标准格式为 Playwright storage state：

```json
{
  "cookies": [],
  "origins": [
    {
      "origin": "https://creator.example.com",
      "localStorage": []
    }
  ]
}
```

为兼容旧数据，也接受纯 Cookie 数组。过期文件不会注入浏览器，但持久 profile 仍会独立参与验证。
