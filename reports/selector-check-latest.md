# 平台元素健康度报告

- 生成时间: `2026-05-02T03:40:59+00:00`
- 平台总数: 1

## 状态汇总

| 平台 | 状态 | 登录页 | login_selectors | publish 页 | authed_selectors |
|---|---|---|---|---|---|
| 小红书 (`xiaohongshu`) | **OK** | ✓ | 2/4 | ✓ | 1/2 |

## 详细结果

### 小红书 (`xiaohongshu`) — OK

**登录页** `https://creator.xiaohongshu.com/` — reachable=True
  - ✓ `text="短信登录"`
  - ✗ `text="扫码登录"` (found=False, visible=False)
  - ✓ `button:has-text("登")`
  - ✗ `.login-btn` (found=False, visible=False)

**publish 页** `https://creator.xiaohongshu.com/publish/publish` — reachable=True
  - ✗ `input.upload-input` (found=True, visible=False)
  - ✓ `button:has-text("上传视频")`

## 状态说明

- **OK**: 登录页 + publish 页选择器全通过
- **PARTIAL**: 登录页通过，publish 页因无 cookie 未验证
- **BROKEN**: 登录页选择器全部失效（**需立即修复**）
- **AUTHED_BROKEN**: cookie 有效但 publish 页选择器失效
- **UNREACHABLE**: 登录页无法访问（可能是 GitHub Actions 出口 IP 被封）
