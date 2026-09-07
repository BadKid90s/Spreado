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
    login_url_patterns=(...),
    challenge_selectors=(...),
    probe=None,
    browser_channel=None,
)
```

- `login_url`：需要人工认证时打开的页面。
- `verification_url`：用于确认认证状态的页面，通常也是发布入口。
- `login_selectors`：出现任意一个即表示仍需登录。
- `authenticated_selectors`：出现任意一个即表示已经登录。
- `login_url_patterns`：当前 URL 命中任意正则时表示仍需登录。
- `challenge_selectors`：出现验证码或安全验证元素时表示认证被拦截。
- `probe`：可选的平台专用异步探针，用于补充 DOM 无法覆盖的判定。
- `browser_channel`：可选的系统浏览器类型。

## 认证结果

认证检查返回 `AuthResult`，而不是含义模糊的布尔值：

| 状态 | 含义 |
|---|---|
| `AUTHENTICATED` | 有明确的已登录证据 |
| `UNAUTHENTICATED` | 登录页面、登录表单或登录 URL 已出现 |
| `CHALLENGE` | 出现验证码或安全验证，不能视为已登录 |
| `UNKNOWN` | 当前证据不足，保守拒绝继续发布 |

## 验证顺序

`AuthenticationManager` 打开验证页后按以下顺序判断：

1. 安全验证元素可见，返回 `CHALLENGE`。
2. 登录元素可见，返回 `UNAUTHENTICATED`。
3. 当前 URL 命中登录页规则，返回 `UNAUTHENTICATED`。
4. 平台探针给出明确结果时采用探针结果。
5. 登录后元素可见，返回 `AUTHENTICATED`。
6. 没有确切证据时返回 `UNKNOWN`。

为避免页面跳转和组件短暂闪现造成误判，同一个明确状态必须连续出现两次才会被接受。超时后统一返回 `UNKNOWN`。验证域名相同、登录元素暂未出现或 Cookie 文件未过期，都不再单独作为登录成功依据。

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
