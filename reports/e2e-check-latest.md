# E2E 测试报告

- 生成时间: `2026-05-02T12:46:20+08:00`
- 测试视频: `/home/runner/work/Spreado/Spreado/src/spreado/examples/videos/demo.mp4`

## 结果汇总

| 平台 | 状态 | 通过步骤 | 总步骤 | 耗时 |
|---|---|---|---|---|
| 抖音 (`douyin`) | — 跳过 | — | — | 原因: cookie 文件不存在 |
| 小红书 (`xiaohongshu`) | **✗ FAIL** | 3/6 | 6 | 42.9s |
| 快手 (`kuaishou`) | — 跳过 | — | — | 原因: cookie 文件不存在 |
| 视频号 (`shipinhao`) | — 跳过 | — | — | 原因: cookie 文件不存在 |

## 详细结果

### 抖音 (`douyin`) — 跳过

原因: cookie 文件不存在

### 小红书 (`xiaohongshu`) — ✗ FAIL

| # | 步骤 | 状态 | 耗时 | 说明 |
|---|---|---|---|---|
| 1 | verify_cookie | ✓ | 10.2s |  |
| 2 | goto_upload_page | ✓ | 0.8s |  |
| 3 | upload_video_file | ✓ | 5.1s |  |
| 4 | wait_for_upload_complete | ✗ | 0.5s |  |
| 5 | upload_video | ✗ | 6.3s |  |
| 6 | upload_video_flow | ✗ | 20.0s |  |

### 快手 (`kuaishou`) — 跳过

原因: cookie 文件不存在

### 视频号 (`shipinhao`) — 跳过

原因: cookie 文件不存在

## 测试说明

- **✓ PASS**: 所有步骤通过（`verify_publish_button` 仅检查按钮存在，不点击）
- **✗ FAIL**: 任一步骤失败
- **— 跳过**: 无 cookie 文件，未执行测试
- 本测试**不会实际发布**内容，发布按钮仅做可见性验证
