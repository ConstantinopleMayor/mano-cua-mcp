"""
Mano-CUA MCP Server
提供桌面 GUI 自动化工具：截图、点击、输入、滚动等。
每个动作工具执行后可选择是否自动截图返回。
"""

from collections.abc import Sequence

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent
import time

import executor as gui

try:
    import tracer as tr
    HAS_TRACER = True
except ImportError:
    HAS_TRACER = False


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
        TextContent(type="text", text=action_name),
    ]


server = FastMCP("mano-cua")


@server.tool()
def left_click(x: float, y: float, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """在归一化坐标 (x, y) 处执行左键点击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"左键点击 ({_norm(x)}, {_norm(y)})", gui.left_click, x, y, screenshot=screenshot)


@server.tool()
def right_click(x: float, y: float, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """在归一化坐标 (x, y) 处执行右键点击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"右键点击 ({_norm(x)}, {_norm(y)})", gui.right_click, x, y, screenshot=screenshot)


@server.tool()
def double_click(x: float, y: float, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """在归一化坐标 (x, y) 处执行双击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"双击 ({_norm(x)}, {_norm(y)})", gui.double_click, x, y, screenshot=screenshot)


@server.tool()
def mouse_move(x: float, y: float, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """将鼠标移动到归一化坐标 (x, y) 处，不点击。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"鼠标移动到 ({_norm(x)}, {_norm(y)})", gui.mouse_move, x, y, screenshot=screenshot)


@server.tool()
def left_click_drag(start_x: float, start_y: float, end_x: float, end_y: float, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """从 (start_x, start_y) 按住左键拖拽到 (end_x, end_y)。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。0 是左/上边界，1000 是右/下边界，500 是中心。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(
        f"拖拽 ({_norm(start_x)},{_norm(start_y)}) -> ({_norm(end_x)},{_norm(end_y)})",
        gui.left_click_drag, start_x, start_y, end_x, end_y, screenshot=screenshot,
    )


@server.tool()
def freehand_draw(x: list[float], y: list[float], screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """多点自由绘制：按住左键沿路径移动形成平滑曲线。适合绘画、签名等复杂轨迹。x 和 y 是等长数组，一一对应。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。"""
    n = len(x)
    start = f"({_norm(x[0])},{_norm(y[0])})"
    end = f"({_norm(x[-1])},{_norm(y[-1])})"
    return _with_screenshot(f"自由绘制 {n} 个控制点 {start} -> ... -> {end}", gui.freehand_draw, x, y, screenshot=screenshot)


@server.tool()
def preview(
    image_path: str,
    min_area: int = 3,
    mode: str = "m-path",
    threshold1: int = 20,
    threshold2: int = 60,
) -> Sequence[TextContent]:
    """预览边缘检测效果（不画画）。输出边缘图路径供 AI 判断阈值是否合适。
    AI 会自己看图并调整阈值，直到边缘图满意后再调用 trace_image。

    mode 参数: "m-path" | "contour"
    """
    if not HAS_TRACER:
        return [TextContent(type="text", text="错误：缺少 tracer 模块（需要 opencv-python）")]

    all_contours, info = tr.extract_contours(image_path, max_contours=0, min_area=min_area, debug_dir=gui.SCREENSHOTS_DIR, mode=mode, threshold1=threshold1, threshold2=threshold2)
    total = len(all_contours)
    debug_paths = info.get("debug_paths", {})
    parts = [f"检测到 {total} 个轮廓 ({info['image_size']})"]
    if "edges" in debug_paths:
        parts.append(f"边缘图: {debug_paths['edges']}")
    return [
        TextContent(type="text", text="\n".join(parts)),
    ]


@server.tool()
def trace_image(
    image_path: str,
    contour_ratio: float = 0.6,
    min_area: int = 3,
    mode: str = "m-path",
    threshold1: int = 20,
    threshold2: int = 60,
) -> Sequence[ImageContent | TextContent]:
    """从图片自动提取轮廓并绘制到画图中。自动进行边缘检测和轮廓追踪，适合临摹照片、线稿等。

    mode 参数: "m-path"（Canny + 贪心追踪，4向优先无回画，推荐）
                "contour"（Canny + findContours，有来回画，备选）
    threshold1 和 threshold2 为 Canny 双阈值参数
    contour_ratio: 绘制轮廓占总轮廓的比例 (0~1.0)。0.3=画30%，1.0=画全部
    """
    if not HAS_TRACER:
        return [TextContent(type="text", text="错误：缺少 tracer 模块（需要 opencv-python）")]

    # 清除上次可能的停止标志
    gui.clear_stop()

    # 提取所有轮廓
    all_contours, info = tr.extract_contours(image_path, max_contours=0, min_area=min_area, debug_dir=gui.SCREENSHOTS_DIR, mode=mode, threshold1=threshold1, threshold2=threshold2)
    total = len(all_contours)

    # 网格分区选择：均匀覆盖全图，每区取最长轮廓
    if contour_ratio <= 0 or contour_ratio >= 1.0:
        contours = all_contours
    else:
        n = max(1, int(total * contour_ratio))
        contours = tr.select_contours(all_contours, n)

    n_actual = 0
    for i, contour in enumerate(contours):
        # 检查停止标志（安全停止或 Escape 键）
        if gui._stop_requested:
            gui.clear_stop()
            break
        xs = [float(p[0]) for p in contour]
        ys = [float(p[1]) for p in contour]
        if len(xs) >= 2:
            # 下采样：保留最多 120 个点
            if len(xs) > 120:
                step = max(1, len(xs) // 120)
                xs = xs[::step]
                ys = ys[::step]
            gui.freehand_draw(xs, ys)
            n_actual += 1
            if n_actual < len(contours):
                time.sleep(0.02)  # 给 Paint 时间渲染当前轮廓
    time.sleep(2)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=f"追踪图片 {n_actual}/{total} 个轮廓 ({info['image_size']})"),
    ]


@server.tool()
def calibrate(screenshot: bool = True) -> Sequence[ImageContent | TextContent]:
    """自动检测画图画布在屏幕上的位置并返回归一化坐标。在画图窗口打开后调用一次即可。"""
    if not HAS_TRACER:
        return [TextContent(type="text", text="错误：缺少 tracer 模块（需要 opencv-python）")]
    bounds = tr.calibrate_canvas(debug_dir=gui.SCREENSHOTS_DIR)
    time.sleep(1)
    b64, filepath = gui.screenshot()
    return [
        TextContent(type="text", text=f"画布边界: x=[{bounds['x_min']}, {bounds['x_max']}] y=[{bounds['y_min']}, {bounds['y_max']}] → {filepath}"),
    ]


@server.tool()
def stop_drawing(screenshot: bool = True) -> Sequence[ImageContent | TextContent]:
    """紧急停止当前正在进行的绘制操作。当 trace_image 画过头/卡住时调用。"""
    gui.request_stop()
    time.sleep(0.5)
    b64, filepath = gui.screenshot()
    return [
        TextContent(type="text", text=f"已请求停止绘制 → {filepath}"),
    ]


@server.tool()
def scroll(x: float, y: float, scroll_x: int = 0, scroll_y: int = -3, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """在坐标 (x, y) 处滚动鼠标滚轮。坐标基于 0~1000 归一化坐标系（也兼容 0.0~1.0 格式）。scroll_y 正数向上滚动，负数向下滚动。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"滚动 ({_norm(x)}, {_norm(y)}) scroll_y={scroll_y}", gui.scroll, x, y, scroll_x, scroll_y, screenshot=screenshot)


@server.tool()
def type_text(text: str, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """在当前焦点位置输入文本。使用剪贴板粘贴方式，支持中文、特殊字符和换行。"""
    return _with_screenshot(f"输入文本 ({len(text)} 字符)", gui.type_text, text, screenshot=screenshot)


@server.tool()
def key_combination(keys: list[str], screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """发送键盘组合键。例如：['ctrl','c'] 复制，['ctrl','v'] 粘贴，['enter'] 发送，['alt','tab'] 切换窗口。"""
    return _with_screenshot(f"快捷键 {keys}", gui.key_combination, keys, screenshot=screenshot)


@server.tool()
def hotkey_click(x: float, y: float, keys: list[str], screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """按住修饰键的同时点击。例如：hotkey_click(x=500, y=300, keys=['ctrl']) 用于 Ctrl+点击在后台新标签页打开链接。注意：x 和 y 是两个独立的 float 参数，不能合并为数组；坐标值必须在 0~1000 范围内。"""
    return _with_screenshot(f"快捷键+点击 {keys} ({_norm(x)},{_norm(y)})", gui.hotkey_click, x, y, keys, screenshot=screenshot)


@server.tool()
def wait(seconds: float) -> Sequence[ImageContent | TextContent]:
    """等待指定秒数后自动截图返回。用于：任务开始时 wait(0) 看当前状态、等待应用/页面加载响应等。"""
    gui.wait(seconds)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=f"等待 {seconds}s"),
    ]


@server.tool()
def open_app(app_name: str, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """打开指定名称的应用程序（如 wechat、notepad、chrome）。打开后自动等待 5s 并截图返回。"""
    gui.open_app(app_name)
    if not screenshot:
        return [TextContent(type="text", text=f"正在打开应用：{app_name}")]
    time.sleep(5)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=f"打开应用 {app_name}"),
    ]


@server.tool()
def open_url(url: str, screenshot: bool = True    ) -> Sequence[ImageContent | TextContent]:
    """在默认浏览器中打开指定的 URL。打开后自动等待 2s 并截图返回。"""
    gui.open_url(url)
    if not screenshot:
        return [TextContent(type="text", text=f"正在打开页面：{url}")]
    time.sleep(2)
    b64, filepath = gui.screenshot()
    return [
        ImageContent(type="image", data=b64, mimeType="image/png"),
        TextContent(type="text", text=f"打开页面 {url}"),
    ]


if __name__ == "__main__":
    server.run(transport="stdio")