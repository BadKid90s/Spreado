from pathlib import Path

from conf import BASE_DIR


async def set_init_script(context):
    """
    设置浏览器初始化脚本，加载反检测脚本

    Args:
        context: 浏览器上下文实例

    Returns:
        配置好的浏览器上下文实例
    """
    stealth_js_path = Path(BASE_DIR / "utils/stealth.min.js")
    await context.add_init_script(path=stealth_js_path)
    return context
