"""
底层 GUI 动作执行器。
使用 mss 截图 + pynput 鼠标键盘控制。
坐标使用 0~1000 归一化坐标系，内部自动缩放。
"""

from __future__ import annotations

import base64
import io
import os
import subprocess
import tempfile
import time
import webbrowser
from datetime import datetime

from PIL import Image
from PIL import ImageDraw, ImageFont

import mss
import screeninfo
from pynput import keyboard, mouse
import pyautogui

SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
SCALE = 1000

sct = mss.mss()
primary = next(m for m in screeninfo.get_monitors() if m.is_primary)
actual_width = primary.width
actual_height = primary.height
offset_x = primary.x
offset_y = primary.y

mouse_ctrl = mouse.Controller()
keyboard_ctrl = keyboard.Controller()


def _key_to_pynput(k: str):
    mapping = {
        "ctrl": keyboard.Key.ctrl,
        "control": keyboard.Key.ctrl,
        "alt": keyboard.Key.alt,
        "shift": keyboard.Key.shift,
        "cmd": keyboard.Key.cmd,
        "win": keyboard.Key.cmd,
        "super": keyboard.Key.cmd,
        "enter": keyboard.Key.enter,
        "return": keyboard.Key.enter,
        "escape": keyboard.Key.esc,
        "esc": keyboard.Key.esc,
        "space": keyboard.Key.space,
        "tab": keyboard.Key.tab,
        "backspace": keyboard.Key.backspace,
        "delete": keyboard.Key.delete,
        "up": keyboard.Key.up,
        "down": keyboard.Key.down,
        "left": keyboard.Key.left,
        "right": keyboard.Key.right,
        "home": keyboard.Key.home,
        "end": keyboard.Key.end,
        "page_up": keyboard.Key.page_up,
        "page_down": keyboard.Key.page_down,
        "f1": keyboard.Key.f1,
        "f2": keyboard.Key.f2,
        "f3": keyboard.Key.f3,
        "f4": keyboard.Key.f4,
        "f5": keyboard.Key.f5,
        "f6": keyboard.Key.f6,
        "f7": keyboard.Key.f7,
        "f8": keyboard.Key.f8,
        "f9": keyboard.Key.f9,
        "f10": keyboard.Key.f10,
        "f11": keyboard.Key.f11,
        "f12": keyboard.Key.f12,
        "caps_lock": keyboard.Key.caps_lock,
        "print_screen": keyboard.Key.print_screen,
        "scroll_lock": keyboard.Key.scroll_lock,
        "pause": keyboard.Key.pause,
        "insert": keyboard.Key.insert,
        "menu": keyboard.Key.menu,
    }
    kl = k.lower()
    if kl in mapping:
        return mapping[kl]
    if len(k) == 1:
        return keyboard.KeyCode.from_char(k)
    return k


def scale_pos(x: float, y: float) -> tuple[int, int]:
    if max(x, y) <= 1.0:
        x *= SCALE
        y *= SCALE
    return int(x * actual_width / SCALE + offset_x), int(y * actual_height / SCALE + offset_y)


TARGET_SHORT_SIDE = 1080


def _draw_grid(img: Image.Image) -> None:
    draw = ImageDraw.ImageDraw(img, "RGBA")
    try:
        font = ImageFont.truetype("consola.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
    w, h = img.size
    x_step = w / 10
    y_step = h / 10
    grid_alpha = 55
    label_alpha = 180
    right_pad = 25
    bottom_pad = 16

    for i in range(11):
        x = int(i * x_step)
        y = int(i * y_step)
        draw.line([(x, 0), (x, h)], fill=(40, 40, 40, grid_alpha), width=1)
        draw.line([(0, y), (w, y)], fill=(40, 40, 40, grid_alpha), width=1)
        v = str(i * 100)
        if i < 10:
            draw.text((x + 2, 2), v, fill=(40, 40, 40, label_alpha), font=font)
            draw.text((2, y + 2), v, fill=(40, 40, 40, label_alpha), font=font)
        else:
            draw.text((x - right_pad - 2, 2), "1000", fill=(40, 40, 40, label_alpha), font=font)
            draw.text((2, y - bottom_pad), "1000", fill=(40, 40, 40, label_alpha), font=font)


def screenshot() -> tuple[str, str]:
    region = {"left": primary.x, "top": primary.y, "width": primary.width, "height": primary.height}
    raw = sct.grab(region)
    img = Image.frombytes("RGB", raw.size, raw.rgb)
    w, h = img.size
    if w > TARGET_SHORT_SIDE and h > TARGET_SHORT_SIDE:
        scale = TARGET_SHORT_SIDE / min(w, h)
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
    _draw_grid(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    filename = datetime.now().strftime("screenshot_%Y%m%d_%H%M%S_%f")[:-3] + ".png"
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(png)
    return base64.b64encode(png).decode("utf-8"), filepath


def left_click(x: float, y: float) -> None:
    px, py = scale_pos(x, y)
    mouse_ctrl.position = (px, py)
    mouse_ctrl.click(mouse.Button.left)


def right_click(x: float, y: float) -> None:
    px, py = scale_pos(x, y)
    mouse_ctrl.position = (px, py)
    mouse_ctrl.click(mouse.Button.right)


def double_click(x: float, y: float) -> None:
    px, py = scale_pos(x, y)
    mouse_ctrl.position = (px, py)
    mouse_ctrl.click(mouse.Button.left, 2)


def mouse_move(x: float, y: float) -> None:
    px, py = scale_pos(x, y)
    mouse_ctrl.position = (px, py)


def left_click_drag(start_x: float, start_y: float, end_x: float, end_y: float) -> None:
    sx, sy = scale_pos(start_x, start_y)
    ex, ey = scale_pos(end_x, end_y)
    mouse_ctrl.position = (sx, sy)
    mouse_ctrl.press(mouse.Button.left)
    mouse_ctrl.position = (ex, ey)
    mouse_ctrl.release(mouse.Button.left)


_FREEHAND_DURATION = 0.002  # seconds per drag segment (tunable: slower=more reliable)

# 紧急停止标志：用于中断正在进行的绘制
_stop_requested = False
_esc_listener = None


def _start_esc_listener():
    """启动全局 Escape 键监听（通过 pynput）。"""
    global _esc_listener, _stop_requested
    if _esc_listener is not None:
        return
    from pynput import keyboard
    def _on_press(key):
        global _stop_requested
        try:
            if key == keyboard.Key.esc:
                _stop_requested = True
        except Exception:
            pass
    _esc_listener = keyboard.Listener(on_press=_on_press)
    _esc_listener.daemon = True
    _esc_listener.start()


def _is_escape_pressed() -> bool:
    """备用方案：用 ctypes 检查 Escape 键状态。"""
    try:
        import ctypes
        return (ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000) != 0
    except Exception:
        return False

def request_stop() -> None:
    """请求停止当前绘制"""
    global _stop_requested
    _stop_requested = True

def clear_stop() -> None:
    """清除停止标志"""
    global _stop_requested
    _stop_requested = False


def freehand_draw(x: list[float], y: list[float]) -> None:
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("x and y must have same length and at least 2 points")
    points = [scale_pos(xi, yi) for xi, yi in zip(x, y)]

    global _stop_requested
    _start_esc_listener()
    _stop_requested = False

    # mouseDown 按住 + dragTo 循环
    pyautogui.FAILSAFE = False  # 禁用角落 FailSafe（改用 Escape 停止）
    pyautogui.PAUSE = 0.001

    try:
        pyautogui.moveTo(points[0][0], points[0][1])
        pyautogui.mouseDown(button='left')
        for px, py in points[1:]:
            if _stop_requested or _is_escape_pressed():
                break
            pyautogui.dragTo(px, py, button='left', duration=_FREEHAND_DURATION)
    finally:
        pyautogui.mouseUp(button='left')


def scroll(x: float, y: float, scroll_x: int = 0, scroll_y: int = -3) -> None:
    px, py = scale_pos(x, y)
    mouse_ctrl.position = (px, py)
    dy = int(scroll_y * actual_height / 240)
    mouse_ctrl.scroll(scroll_x, dy)


def type_text(text: str) -> None:
    """在当前焦点位置输入文本。使用剪贴板+粘贴方式以支持中文等 Unicode 字符。"""
    _paste_text(text)


def key_combination(keys: list[str]) -> None:
    pynput_keys = [_key_to_pynput(k) for k in keys]
    for k in pynput_keys:
        keyboard_ctrl.press(k)
    time.sleep(0.02)
    for k in reversed(pynput_keys):
        keyboard_ctrl.release(k)


def hotkey_click(x: float, y: float, keys: list[str]) -> None:
    px, py = scale_pos(x, y)
    pynput_keys = [_key_to_pynput(k) for k in keys]
    for k in pynput_keys:
        keyboard_ctrl.press(k)
    time.sleep(0.02)
    mouse_ctrl.position = (px, py)
    mouse_ctrl.click(mouse.Button.left)
    time.sleep(0.02)
    for k in reversed(pynput_keys):
        keyboard_ctrl.release(k)


def wait(seconds: float) -> None:
    time.sleep(seconds)


def _paste_text(text: str) -> None:
    """将文本写入剪贴板并通过 Ctrl+V 粘贴到当前焦点。"""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write(text)
            tmp = f.name
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-Content '{tmp}' -Encoding UTF8 | Set-Clipboard; ri '{tmp}' -Force"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        tmp = None
        time.sleep(0.05)
        with keyboard_ctrl.pressed(keyboard.Key.ctrl):
            keyboard_ctrl.press("v")
            keyboard_ctrl.release("v")
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def open_app(app_name: str) -> None:
    powertoys_running = False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq PowerToys*"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        powertoys_running = "PowerToys" in result.stdout
    except Exception:
        pass

    if powertoys_running:
        keyboard_ctrl.press(keyboard.Key.cmd)
        keyboard_ctrl.press(keyboard.Key.alt)
        keyboard_ctrl.press(keyboard.Key.space)
        time.sleep(0.05)
        keyboard_ctrl.release(keyboard.Key.space)
        keyboard_ctrl.release(keyboard.Key.alt)
        keyboard_ctrl.release(keyboard.Key.cmd)
        time.sleep(0.3)
    else:
        keyboard_ctrl.press(keyboard.Key.cmd)
        time.sleep(0.05)
        keyboard_ctrl.release(keyboard.Key.cmd)
        time.sleep(0.5)

    _paste_text(app_name)
    time.sleep(0.5)
    keyboard_ctrl.press(keyboard.Key.enter)
    keyboard_ctrl.release(keyboard.Key.enter)
    time.sleep(0.5)


def open_url(url: str) -> None:
    webbrowser.open(url)