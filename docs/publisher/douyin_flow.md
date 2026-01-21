# 抖音视频上传器工作流程

## 1. 项目概述

抖音视频上传器是一个自动化工具，用于将视频上传到抖音平台。它提供了完整的视频上传流程，包括视频上传、信息填写、封面设置、定时发布、第三方平台同步和最终发布等功能。

## 2. 核心类与结构

### 2.1 DouYinUploader 类

`DouYinUploader` 是上传器的核心类，继承自 `BaseUploader`，实现了抖音平台的视频上传功能。

### 2.2 主要属性

| 属性名 | 类型 | 描述 |
|-------|------|------|
| platform_name | str | 平台名称（"douyin"） |
| login_url | str | 登录页面URL（https://creator.douyin.com/） |
| login_success_url | str | 登录成功后的跳转URL（https://creator.douyin.com/creator-micro/home） |
| upload_url | str | 视频上传页面URL（https://creator.douyin.com/creator-micro/content/upload） |
| success_url_pattern | str | 上传成功页面URL模式（https://creator.douyin.com/creator-micro/content/manage?enter_from=publish） |
| _login_selectors | List[str] | 登录相关元素选择器列表 |

## 3. 完整工作流程

### 3.1 主流程 (`upload_video_flow`)

`upload_video_flow` 是上传器的主要入口方法，协调整个视频上传流程：

```
1. 调用 verify_cookie_flow() 确保已登录
2. 初始化浏览器和上下文（无头模式）
3. 加载Cookie到浏览器上下文
4. 创建新页面并跳转到上传页面
5. 调用 _upload_video() 执行平台特定上传
6. 上传完成后清理资源
7. 返回上传结果
```

### 3.2 详细步骤分解

#### 3.2.1 认证验证

- **调用 verify_cookie_flow()**：确保已登录，如果未登录则根据auto_login参数决定是否执行登录
- **Cookie加载**：将保存的Cookie加载到浏览器上下文

#### 3.2.2 打开上传页面

- 导航到抖音创作者平台上传页面（`https://creator.douyin.com/creator-micro/content/upload`）
- 等待页面加载完成

#### 3.2.3 视频上传 (`_upload_video_file`)

- 定位视频上传输入框（`div[class^='container'] input`）
- 设置视频文件路径
- 触发文件上传

#### 3.2.4 等待上传完成 (`_wait_for_upload_complete`)

- 使用多种方法检测上传状态：
  - 检查预览元素是否出现（重新上传按钮）
  - 检查上传成功文本（"上传成功"、"已上传"、"完成"）
  - 检查进度条是否消失
  - 检查视频信息编辑区域是否出现
- 最多等待2分钟
- 如超时，记录警告但继续后续操作

#### 3.2.5 填写视频信息 (`_fill_video_info`)

- **填写标题**：
  - 定位标题输入框（支持多种选择器适配）
  - 限制标题长度为30个字符
- **填写描述**：
  - 定位描述编辑区域（`.zone-container`）
  - 输入视频描述内容
- **添加标签**：
  - 清理标签格式（去除多余#号）
  - 按照标准流程添加每个标签：
    1. 确保光标在编辑器末尾
    2. 输入空格作为分隔符
    3. 输入#号
    4. 输入标签文字
    5. 按回车键确认
  - 如遇到问题，尝试直接追加标签到内容后
  - 记录添加结果

#### 3.2.6 设置视频封面 (`_set_thumbnail`)

- **检查封面文件**：验证封面文件是否存在
- **打开封面设置**：
  - 定位并点击封面设置按钮（支持多种选择器）
  - 等待封面设置模态框出现
- **设置竖封面**：点击"设置竖封面"按钮
- **上传封面图片**：
  - 查找接受图片的文件输入框
  - 上传封面图片
- **确认封面设置**：点击完成按钮

#### 3.2.7 设置第三方平台同步 (`_set_third_party_platforms`)

- 定位第三方平台同步开关
- 如果开关未选中，则点击开启同步

#### 3.2.8 设置定时发布 (`_set_schedule_time`)

- 点击"定时发布"选项
- 定位日期时间输入框
- 设置发布时间（格式：YYYY-MM-DD HH:MM）
- 确认时间设置

#### 3.2.9 处理必须设置封面的情况 (`_handle_auto_video_cover`)

- 检测是否有"请设置封面后再发布"提示
- 如果有提示，选择第一个推荐封面
- 确认应用封面

#### 3.2.10 设置地理位置 (`_set_location`)

- 点击地点输入框
- 清除默认提示文字
- 输入位置名称
- 等待并选择位置选项

#### 3.2.11 设置商品链接 (`_set_product_link`)

- 定位并点击"添加标签"下拉框
- 选择"购物车"选项
- 输入商品链接
- 点击"添加链接"按钮
- 验证商品链接有效性
- 处理商品编辑弹窗

#### 3.2.12 发布视频 (`_publish_video`)

- 定位并点击发布按钮
- 验证发布结果

## 4. 技术特点

### 4.1 可靠性设计

- **多重选择器**：使用多个选择器尝试定位同一个元素，提高兼容性
- **超时保护**：为每个操作设置合理的超时时间，避免无限等待
- **错误处理**：捕获并处理各种异常，确保流程的连续性
- **状态验证**：使用多种方法验证操作结果

### 4.2 性能优化

- **异步操作**：使用asyncio实现异步执行，提高效率
- **精确等待**：只等待必要的元素和状态，减少不必要的等待时间
- **直接操作**：直接操作DOM元素，避免模拟复杂的用户交互

### 4.3 调试与监控

- **详细日志**：记录每个关键步骤的执行状态
- **导航跟踪**：记录所有页面导航URL，便于调试
- **性能统计**：记录每个步骤的执行时间，便于性能分析

## 5. 通用工具方法

### 5.1 _click_first_visible_element

点击第一个可见的元素，支持多种选择器适配：

- **参数**：
  - `page`：页面实例
  - `selectors`：选择器列表
  - `description`：元素描述（用于日志）
  - `wait_after`：点击后等待时间（毫秒）
- **返回值**：是否成功点击

### 5.2 _upload_file_to_first_input

上传文件到第一个匹配的输入框，支持多种选择器适配：

- **参数**：
  - `page`：页面实例
  - `selectors`：选择器列表
  - `file_path`：文件路径
  - `accept_type`：接受的文件类型
- **返回值**：是否成功上传

## 6. 使用示例

```python
import asyncio
from pathlib import Path
from publisher.douyin_uploader import DouYinUploader

async def main():
    # 初始化上传器
    cookie_file_path = Path("cookies/douyin_uploader/account.json")
    uploader = DouYinUploader(cookie_file_path=cookie_file_path)

    # 确保已登录
    if not await uploader.verify_cookie_flow(auto_login=True):
        print("登录失败")
        return

    # 上传视频
    result = await uploader.upload_video_flow(
        file_path="video.mp4",
        title="我的视频",
        content="视频描述",
        tags=["标签1", "标签2"],
        thumbnail_path="cover.png",
        auto_login=True
    )

    if result:
        print("上传成功")
    else:
        print("上传失败")

asyncio.run(main())
```

## 7. 常见问题与解决方案

### 7.1 上传超时

**问题**：视频上传超过最大等待时间（2分钟）

**解决方案**：
- 检查网络连接
- 检查视频文件大小和格式
- 增加最大等待时间（修改`_wait_for_upload_complete`方法中的`max_retries`参数）

### 7.2 元素定位失败

**问题**：无法定位某个页面元素

**解决方案**：
- 更新选择器（检查页面结构是否变化）
- 增加等待时间
- 添加更多备选选择器

### 7.3 发布超时

**问题**：点击发布按钮后等待超时

**解决方案**：
- 检查网络连接
- 增加超时时间（修改`_publish_video`方法中的`timeout`参数）
- 检查是否有弹出的确认对话框

### 7.4 封面设置失败

**问题**：无法设置视频封面

**解决方案**：
- 检查封面文件是否存在
- 检查封面文件格式是否支持（PNG、JPEG等）
- 增加封面设置步骤的等待时间

### 7.5 商品链接无效

**问题**：设置商品链接时提示"未搜索到对应商品"

**解决方案**：
- 检查商品链接是否有效
- 确认商品已在抖音商品库中
- 尝试使用其他商品链接

## 8. 总结

抖音视频上传器提供了完整的自动化上传流程，通过合理的设计和可靠的实现，确保了视频能够高效、稳定地上传到抖音平台。它具有良好的扩展性和可维护性，可以根据平台的变化进行相应的调整和优化。