import gradio as gr
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.files_times import get_title_and_hashtags
from conf import BASE_DIR

# 导入各平台的上传类
try:
    from uploader.douyin_uploader.main import DouYinVideo

    DOUYIN_AVAILABLE = True
except ImportError:
    DOUYIN_AVAILABLE = False
    print("抖音上传模块不可用")

try:
    from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo

    XIAOHONGSHU_AVAILABLE = True
except ImportError:
    XIAOHONGSHU_AVAILABLE = False
    print("小红书上传模块不可用")

try:
    from uploader.tencent_uploader.main import TencentVideo

    TENCENT_AVAILABLE = True
except ImportError:
    TENCENT_AVAILABLE = False
    print("腾讯视频号上传模块不可用")


# 处理视频文件上传并提取信息
def process_video_file(video_file_obj):
    """处理上传的视频文件，提取标题和标签信息"""
    if not video_file_obj:
        return "", "", ""

    try:
        # 获取视频文件路径
        # 处理不同类型的输入参数
        if hasattr(video_file_obj, 'name'):
            # 如果是文件对象，获取其name属性
            video_path = video_file_obj.name
        else:
            # 如果是字符串路径，直接使用
            video_path = video_file_obj

        # 查找同名的txt文件
        txt_path = video_path.rsplit('.', 1)[0] + '.txt'

        if os.path.exists(txt_path):
            title, content, tags = get_title_and_hashtags(video_path)
            tags_str = ' '.join(tags)
            return title, content, tags_str
        else:
            # 如果没有txt文件，则使用文件名作为标题
            title = os.path.basename(video_path).rsplit('.', 1)[0]
            return title, "", ""
    except Exception as e:
        return "", "", ""


# 模拟发布函数 - 实际使用时替换为真实的发布逻辑
def publish_to_platform(platform, video_path, title, description, tags, scheduled_time=None, thumbnail_path=None):
    """发布到各平台的函数"""
    result = f"  📝 标题: {title}\n"
    result += f"  📄 描述: {description}\n"
    result += f"  🏷️ 标签: {', '.join(tags)}\n"
    if scheduled_time:
        result += f"  🕒 定时发布: {scheduled_time}\n"
    if thumbnail_path:
        result += f"  🖼️ 封面图: {os.path.basename(thumbnail_path)}\n"

    # 处理publish_date参数
    # 数据类型转换和验证
    try:
        if scheduled_time:
            # 验证scheduled_time是否为有效的时间格式
            if isinstance(scheduled_time, str):
                # 如果是字符串，尝试解析为datetime对象
                try:
                    publish_date = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                except ValueError:
                    # 如果解析失败，设为None
                    publish_date = None
            elif isinstance(scheduled_time, (datetime,)):
                # 如果已经是datetime对象，直接使用
                publish_date = scheduled_time
            else:
                # 其他情况设为None
                publish_date = None
        else:
            publish_date = None
    except Exception:
        # 如果出现任何异常，设为None
        publish_date = None

    # 根据平台类型调用不同的上传实现
    if platform == "douyin" and DOUYIN_AVAILABLE:
        try:
            # 创建抖音视频对象
            douyin_video = DouYinVideo(
                title=title,
                content=description,
                tags=tags,
                file_path=Path(video_path),
                account_file=str(Path(BASE_DIR) / "cookies" / "douyin_uploader" / "account.json"),
                publish_date=publish_date
            )
            asyncio.run(douyin_video.main(), debug=False)
            result = f"✅ 抖音发布成功!\n"
        except Exception as e:
            result = f"❌ 抖音发布失败: {str(e)}\n"
    elif platform == "xiaohongshu" and XIAOHONGSHU_AVAILABLE:
        try:
            # 创建小红书视频对象
            xiaohongshu_video = XiaoHongShuVideo(
                title=title,
                content=description,
                tags=tags,
                file_path=Path(video_path),
                account_file=str(Path(BASE_DIR) / "cookies" / "xiaohongshu_uploader" / "account.json"),
                publish_date=publish_date
            )
            # 运行异步上传任务
            asyncio.run(xiaohongshu_video.main())
            result = f"✅ 小红书发布成功!\n"
        except Exception as e:
            result = f"❌ 小红书发布失败: {str(e)}\n"
    elif platform == "tencent" and TENCENT_AVAILABLE:
        try:
            # 创建腾讯视频号视频对象
            tencent_video = TencentVideo(
                title=title,
                content=description,
                tags=tags,
                file_path=Path(video_path),
                account_file=str(Path(BASE_DIR) / "cookies" / "tencent_uploader" / "account.json"),
                publish_date=publish_date
            )
            # 运行异步上传任务
            asyncio.run(tencent_video.main())
            result = f"✅ 腾讯视频号发布成功!\n"
        except Exception as e:
            result = f"❌ 腾讯视频号发布失败: {str(e)}\n"
    else:
        # 这里可以添加快手和微信视频号的实现
        result = f"✅ {platform}暂不支持发布哦！\n"

    return result


# 主发布函数
def publish_video(video_file_obj, thumbnail_file_obj, title, description, tags, scheduled_time, platforms):
    """主发布函数"""
    if not video_file_obj:
        return "❌ 请先上传视频文件"

    # 处理标签
    if tags:
        # 分割标签，支持中英文逗号和空格
        import re
        tag_list = re.split(r'[,，\s]+', tags.strip())
        # 过滤空标签并去除多余的#
        tag_list = [tag.lstrip('#') for tag in tag_list if tag]
    else:
        tag_list = []

    # 获取文件路径
    # 处理不同类型的输入参数
    if hasattr(video_file_obj, 'name'):
        # 如果是文件对象，获取其name属性
        video_path = video_file_obj.name
    else:
        # 如果是字符串路径，直接使用
        video_path = video_file_obj
    
    # 处理缩略图路径
    if thumbnail_file_obj:
        if hasattr(thumbnail_file_obj, 'name'):
            thumbnail_path = thumbnail_file_obj.name
        else:
            thumbnail_path = thumbnail_file_obj
    else:
        thumbnail_path = None

    # 准备结果日志
    log_result = f"🎬 开始发布视频: {os.path.basename(video_path)}\n\n"

    # 发布到各平台
    platform_display_mapping = {
        "douyin": "抖音",
        "xiaohongshu": "小红书",
        "kuaishou": "快手",
        "tencent": "微信视频号"
    }

    for platform_value in platforms:
        if platform_value in platform_display_mapping:
            display_name = platform_display_mapping[platform_value]
            log_result += f"➡️ 正在发布到{display_name}...\n"
            try:
                result = publish_to_platform(
                    platform_value,
                    video_path,
                    title,
                    description,
                    tag_list,
                    scheduled_time,
                    thumbnail_path
                )
                log_result += result + "\n" if result else "\n"
            except Exception as e:
                log_result += f"❌ {display_name}发布失败: {str(e)}\n\n"

    log_result += "🎉 所有选定平台发布完成！"
    return log_result


# Gradio界面
with gr.Blocks(title="多平台视频发布工具") as demo:
    gr.Markdown("# 🎬 多平台视频发布工具")
    gr.Markdown("支持抖音、小红书、快手、微信视频号等平台的视频发布")

    with gr.Row(elem_classes="upload-section"):
        with gr.Column(scale=5, elem_classes="content-left"):
            # 视频上传组件
            video_file = gr.PlayableVideo(label="上传视频文件并预览", elem_classes="video-upload")

        with gr.Column(scale=5, elem_classes="content-right"):
            # 封面图片上传组件
            thumbnail_file = gr.Image(label="上传封面图(可选)", type="filepath", elem_classes="image-upload")

    # 标题输入
    title = gr.Textbox(label="视频标题", placeholder="请输入视频标题(建议15-30个字符)")

    # 内容输入
    description = gr.Textbox(label="视频描述", placeholder="请输入视频描述内容", lines=4)

    # 标签添加
    tags = gr.Textbox(label="话题标签", placeholder="请输入话题标签，用空格分隔，例如：科技 数码 AI")

    # 定时发布开关
    schedule_switch = gr.Checkbox(label="定时发布", value=False)

    # 定时发布时间（默认隐藏）
    scheduled_time = gr.DateTime(value=None, info="留空表示立即发布", visible=False)

    # 平台选择
    platforms = gr.CheckboxGroup(
        label="选择发布平台",
        choices=[("抖音", "douyin"), ("小红书", "xiaohongshu"), ("快手", "kuaishou"),
                 ("微信视频号", "tencent")],
        value=["douyin"]
    )

    # 发布按钮
    publish_btn = gr.Button("🚀 开始发布", variant="primary", size="lg")

    # 日志输出
    logs = gr.Textbox(label="发布日志", interactive=False, lines=15, max_lines=15)


    # 定时发布开关事件处理
    def toggle_schedule_time_visibility(schedule_checked):
        if schedule_checked:
            # 当开关打开时，设置默认时间为一小时后
            default_time = datetime.now() + timedelta(hours=1)
            return gr.update(visible=True, value=default_time)
        else:
            # 当开关关闭时，隐藏组件并将值设为None
            return gr.update(visible=False, value=None)


    # 视频上传事件监听 - 更新视频信息
    video_file.change(
        fn=process_video_file,
        inputs=video_file,
        outputs=[title, description, tags]
    )

    schedule_switch.change(
        fn=toggle_schedule_time_visibility,
        inputs=schedule_switch,
        outputs=scheduled_time
    )

    publish_btn.click(
        fn=publish_video,
        inputs=[video_file, thumbnail_file, title, description, tags, scheduled_time, platforms],
        outputs=logs
    )

# 运行应用
if __name__ == "__main__":
    custom_css = """
    .video-upload, .image-upload { 
        max-height: 400px; 
        height: 400px; 
        min-height: 400px;
        margin-bottom: 20px;
    }
    .video-upload video, .image-upload img {
        max-height: 380px;
        height: 380px;
        object-fit: contain;
    }
    .gr-textbox, .gr-checkbox, .gr-datetime, .gr-checkboxgroup, .gr-button {
        margin-bottom: 15px;
    }
    @media (max-width: 768px) {
        .video-upload, .image-upload { 
            height: auto; 
            max-height: 300px;
            min-height: 200px;
        }
        .video-upload video, .image-upload img {
            max-height: 280px;
            height: auto;
        }
    }
    """
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, css=custom_css)
