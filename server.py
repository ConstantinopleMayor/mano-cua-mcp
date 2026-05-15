"""
Mano-CUA MCP Server
提供桌面 GUI 自动化工具：截图、点击、输入、滚动等。
每个动作工具执行后可选择是否自动截图返回。
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent
import time

import executor as gui


def _norm(v: float) -> str:
    if v <= 1.0:
        return f"{v * gui.SCALE:.0f}"
    return f"{v:.0f}"


def _with_screenshot(action_name: str, action_fn, *args, screenshot: bool = True, **kwargs):
    action_fn(*args, **kwargs)
    if not screenshot:
        return [TextContent(type="text", text=action_name)]
    time.sleep(2)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=action_name + " 并截图"),
    ]


server = FastMCP("mano-cua")


@server.tool()
def left_click(x: float, y: float, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """在归一化坐标 (x, y) 处执行左键点击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"左键点击 ({_norm(x)}, {_norm(y)})", gui.left_click, x, y, screenshot=screenshot)


@server.tool()
def right_click(x: float, y: float, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """在归一化坐标 (x, y) 处执行右键点击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"右键点击 ({_norm(x)}, {_norm(y)})", gui.right_click, x, y, screenshot=screenshot)


@server.tool()
def double_click(x: float, y: float, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """在归一化坐标 (x, y) 处执行双击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"双击 ({_norm(x)}, {_norm(y)})", gui.double_click, x, y, screenshot=screenshot)


@server.tool()
def mouse_move(x: float, y: float, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """将鼠标移动到归一化坐标 (x, y) 处，不点击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"鼠标移动到 ({_norm(x)}, {_norm(y)})", gui.mouse_move, x, y, screenshot=screenshot)


@server.tool()
def left_click_drag(start_x: float, start_y: float, end_x: float, end_y: float, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """从 (start_x, start_y) 按住左键拖拽到 (end_x, end_y)。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(
        f"拖拽 ({_norm(start_x)},{_norm(start_y)}) -> ({_norm(end_x)},{_norm(end_y)})",
        gui.left_click_drag, start_x, start_y, end_x, end_y, screenshot=screenshot,
    )


@server.tool()
def scroll(x: float, y: float, scroll_x: int = 0, scroll_y: int = -3, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """在坐标 (x, y) 处滚动鼠标滚轮。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。scroll_y 正数向上滚动，负数向下滚动。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"滚动 ({_norm(x)}, {_norm(y)}) scroll_y={scroll_y}", gui.scroll, x, y, scroll_x, scroll_y, screenshot=screenshot)


@server.tool()
def type_text(text: str, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """在当前焦点位置输入文本。使用剪贴板粘贴方式，支持中文、特殊字符和换行。"""
    return _with_screenshot(f"输入文本 ({len(text)} 字符)", gui.type_text, text, screenshot=screenshot)


@server.tool()
def key_combination(keys: list[str], screenshot: bool = True) -> list[ImageContent | TextContent]:
    """发送键盘组合键。例如：['ctrl','c'] 复制，['ctrl','v'] 粘贴，['enter'] 发送，['alt','tab'] 切换窗口。"""
    return _with_screenshot(f"快捷键 {keys}", gui.key_combination, keys, screenshot=screenshot)


@server.tool()
def hotkey_click(x: float, y: float, keys: list[str], screenshot: bool = True) -> list[ImageContent | TextContent]:
    """按住修饰键的同时点击。例如：hotkey_click(x=500, y=300, keys=['ctrl']) 用于 Ctrl+点击在后台新标签页打开链接。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"快捷键+点击 {keys} ({_norm(x)},{_norm(y)})", gui.hotkey_click, x, y, keys, screenshot=screenshot)


@server.tool()
def wait(seconds: float) -> list[ImageContent | TextContent]:
    """等待指定秒数后自动截图返回。用于：任务开始时 wait(0) 看当前状态、等待应用/页面加载响应等。"""
    gui.wait(seconds)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=f"等待 {seconds}s 并截图"),
    ]


@server.tool()
def open_app(app_name: str, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """打开指定名称的应用程序（如 wechat、notepad、chrome）。打开后自动等待 5s 并截图返回。"""
    gui.open_app(app_name)
    if not screenshot:
        return [TextContent(type="text", text=f"正在打开应用：{app_name}")]
    time.sleep(5)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=f"打开应用 {app_name} 并截图"),
    ]


@server.tool()
def open_url(url: str, screenshot: bool = True) -> list[ImageContent | TextContent]:
    """在默认浏览器中打开指定的 URL。打开后自动等待 2s 并截图返回。"""
    gui.open_url(url)
    if not screenshot:
        return [TextContent(type="text", text=f"正在打开页面：{url}")]
    time.sleep(2)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=f"打开页面 {url} 并截图"),
    ]


if __name__ == "__main__":
    server.run(transport="stdio")