"""
Image tracer — 从图片自动提取轮廓，用于 freehand_draw 绘制。

流程：读取图片 → Canny 边缘检测 → 轮廓提取 → 坐标转换
"""

import cv2
import numpy as np

# 画图应用的画布边界（0-1000 归一化坐标）
# 调用 calibrate_canvas() 自动检测，也可手动覆盖
CANVAS_X_MIN = 15
CANVAS_X_MAX = 575
CANVAS_Y_MIN = 155
CANVAS_Y_MAX = 735

# 从 executor 导入屏幕分辨率（用于宽高比补偿）
try:
    from executor import actual_width, actual_height, SCALE, screenshot as _exec_screenshot
except ImportError:
    actual_width, actual_height, SCALE = 1920, 1080, 1000


def calibrate_canvas(debug_dir: str = "") -> dict:
    """
    通过截图自动检测画图画布位置。
    返回 {x_min, x_max, y_min, y_max} (0-1000 归一化坐标)。
    策略：检测白色矩形画布 → 找被灰色/蓝色边框包围的矩形白色区域。
    """
    import mss
    import screeninfo
    primary = next(m for m in screeninfo.get_monitors() if m.is_primary)
    with mss.mss() as sct:
        raw = sct.grab({"left": primary.x, "top": primary.y, "width": primary.width, "height": primary.height})
    arr = np.frombuffer(raw.rgb, dtype=np.uint8).reshape(raw.height, raw.width, 3)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    # 步骤1: 找白色区域（画布本身白，周围灰色/蓝色）
    _, white = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

    # 步骤2: 用形态学开运算去掉细小白噪（工具栏按钮、文字等）
    kernel = np.ones((15, 15), np.uint8)
    cleaned = cv2.morphologyEx(white, cv2.MORPH_OPEN, kernel)

    # 步骤3: 找所有白色连通区域，选最矩形化的那个
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {"x_min": CANVAS_X_MIN, "x_max": CANVAS_X_MAX, "y_min": CANVAS_Y_MIN, "y_max": CANVAS_Y_MAX}

    best = None
    best_rect_score = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < 20000:  # 太小的跳过
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        rect_area = cw * ch
        if rect_area == 0:
            continue
        # 矩形度 = contour area / bounding rect area (越接近1越矩形)
        rect_score = area / rect_area
        # 还要考虑画布应该在屏幕偏上的位置（y不太大）
        y_center = y + ch // 2
        if rect_score > best_rect_score and y_center < h * 0.85:
            best_rect_score = rect_score
            best = (x, y, cw, ch)

    if best is None:
        return {"x_min": CANVAS_X_MIN, "x_max": CANVAS_X_MAX, "y_min": CANVAS_Y_MIN, "y_max": CANVAS_Y_MAX}

    x, y, cw, ch = best

    # 转换为 0-1000 归一化坐标
    norm_x_min = int(x * SCALE / w)
    norm_x_max = int((x + cw) * SCALE / w)
    norm_y_min = int(y * SCALE / h)
    norm_y_max = int((y + ch) * SCALE / h)

    result = {
        "x_min": norm_x_min,
        "x_max": norm_x_max,
        "y_min": norm_y_min,
        "y_max": norm_y_max,
    }

    if debug_dir:
        import os as _os
        _os.makedirs(debug_dir, exist_ok=True)
        debug = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(debug, (x, y), (x + cw, y + ch), (0, 255, 0), 3)
        _p = _os.path.join(debug_dir, "canvas_calib.png")
        _ok_c, _buf_c = cv2.imencode('.png', debug)
        if _ok_c:
            with open(_p, 'wb') as _fw:
                _fw.write(_buf_c.tobytes())

    return result

def _m_path_trace(edges_inv: np.ndarray, min_area: int, max_contours: int = 0) -> list[list[tuple[int, int]]]:
    """
    m-path 双向贪心追踪（改进版 drawinline）。

    输入: edges_inv — 二值图，边缘=黑色(0)，背景=白色(255)
    返回: list of paths, each path = [(x, y), ...]

    算法:
       逐像素扫描 → 找到黑点开始笔画
       从该点向两个方向追踪（正向+反向），完整走完一整条线
       4-邻域优先，8-邻域回退
       分支在扫描循环中被重新拾取
    """
    img = edges_inv.copy()
    h, w = img.shape

    all_strokes = []
    cur = []

    # 主方向：从左上到右下扫描，收集所有笔画
    for y in range(h):
        for x in range(w):
            if img[y, x] != 0:
                continue

            # 提交上一笔画
            if cur and len(cur) >= min_area:
                all_strokes.append(cur)

            # 新笔画 — 双向追踪
            img[y, x] = 255  # 标记起点已访问

            # 正向：从起点向一个方向延伸
            forward = []
            cx, cy = x, y
            # 上一步的方向（未知则默认向下）
            last_dx, last_dy = 0, 1
            while True:
                found = False
                # 1) 优先延续当前方向
                nx, ny = cx + last_dx, cy + last_dy
                if 0 <= nx < w and 0 <= ny < h and img[ny, nx] == 0:
                    img[ny, nx] = 255
                    forward.append((nx, ny))
                    cx, cy = nx, ny
                    found = True
                    # last_dx/last_dy 不变
                    continue
                # 2) 其他 4 方向
                for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                    if dx == last_dx and dy == last_dy:
                        continue  # 已查过
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and img[ny, nx] == 0:
                        img[ny, nx] = 255
                        forward.append((nx, ny))
                        cx, cy = nx, ny
                        last_dx, last_dy = dx, dy
                        found = True
                        break
                if found:
                    continue
                # 3) 对角线
                for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and img[ny, nx] == 0:
                        img[ny, nx] = 255
                        forward.append((nx, ny))
                        cx, cy = nx, ny
                        last_dx, last_dy = dx, dy
                        found = True
                        break
                if not found:
                    break

            # 反向：从起点向相反方向延伸
            backward = []
            cx, cy = x, y
            last_dx, last_dy = 0, -1  # 默认向上
            while True:
                found = False
                # 1) 优先延续当前方向
                nx, ny = cx + last_dx, cy + last_dy
                if 0 <= nx < w and 0 <= ny < h and img[ny, nx] == 0:
                    img[ny, nx] = 255
                    backward.append((nx, ny))
                    cx, cy = nx, ny
                    found = True
                    continue
                # 2) 其他 4 方向
                for dx, dy in ((0, -1), (-1, 0), (0, 1), (1, 0)):
                    if dx == last_dx and dy == last_dy:
                        continue
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and img[ny, nx] == 0:
                        img[ny, nx] = 255
                        backward.append((nx, ny))
                        cx, cy = nx, ny
                        last_dx, last_dy = dx, dy
                        found = True
                        break
                if found:
                    continue
                # 3) 对角线
                for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and img[ny, nx] == 0:
                        img[ny, nx] = 255
                        backward.append((nx, ny))
                        cx, cy = nx, ny
                        last_dx, last_dy = dx, dy
                        found = True
                        break
                if not found:
                    break

            # 合并：反向(倒序) + 起点 + 正向
            cur = list(reversed(backward)) + [(x, y)] + forward

    if cur and len(cur) >= min_area:
        all_strokes.append(cur)

    return select_contours(all_strokes, max_contours)


def select_contours(all_strokes: list[list[tuple[int, int]]], n: int) -> list[list[tuple[int, int]]]:
    """
    从所有笔画中选择 n 条（网格分区法）。
    n <= 0 或 n >= 总条数时，返回全部。
    """
    if n <= 0 or len(all_strokes) <= n:
        return all_strokes

    # 需要数量 >= 总轮廓数，直接返回全部
    if n >= len(all_strokes):
        return sorted(all_strokes, key=lambda s: sum(p[1] for p in s) / len(s))

    # 网格分区法：把图分成多个水平区，每区取最长的轮廓
    # 确保均匀覆盖 + 每条轮廓都是重要的主线
    n_regions = n  # 每区取 1 条
    h_max = max(p[1] for s in all_strokes for p in s) + 1
    h_min = min(p[1] for s in all_strokes for p in s)
    h_range = h_max - h_min
    region_h = h_range / n_regions if n_regions > 0 else 1

    # 先把所有轮廓分到各个区域
    region_buckets = [[] for _ in range(n_regions)]
    for s in all_strokes:
        avg_y = sum(p[1] for p in s) / len(s)
        ri = min(int((avg_y - h_min) / region_h), n_regions - 1)
        region_buckets[ri].append(s)

    # 每个区域选最长的一条
    selected = []
    for bucket in region_buckets:
        if bucket:
            bucket.sort(key=len, reverse=True)
            selected.append(bucket[0])

    # 如果不够 n 条，从剩余轮廓补齐（选最长的）
    if len(selected) < n:
        used_ids = set(id(s) for s in selected)
        remaining = [s for s in all_strokes if id(s) not in used_ids]
        remaining.sort(key=len, reverse=True)
        needed = n - len(selected)
        selected.extend(remaining[:needed])

    # 按 y 排序确保绘制顺序上→下
    selected.sort(key=lambda s: sum(p[1] for p in s) / len(s))

    return selected


def extract_contours(
    image_path: str,
    max_contours: int = 0,
    min_area: int = 3,
    debug_dir: str = "",
    mode: str = "m-path",
    threshold1: int = 150,
    threshold2: int = 200,
) -> tuple[list[list[tuple[int, int]]], dict]:
    """
    从图片提取轮廓并转换到画布 0-1000 坐标。

    参数:
        image_path: 图片路径
        max_contours: 最大轮廓数量
        min_area: 最小轮廓长度（像素，过滤噪声）
        debug_dir: 调试输出目录
        mode: "m-path"（贪心线性追踪，无回画，推荐）或 "canny"（传统 findContours，有回画）
        threshold1: Canny 低阈值（仅 m-path 模式）
        threshold2: Canny 高阈值（仅 m-path 模式）

    返回:
        (contours, info)
        contours: list of [(x,y), ...]，每个轮廓在画布坐标
        info: 元信息字典
    """
    # 支持中文路径：用 numpy 读取字节再解码
    import os as _os
    if not _os.path.exists(image_path):
        raise FileNotFoundError(f"图片不存在: {image_path}")
    with open(image_path, "rb") as _f:
        _buf = np.frombuffer(_f.read(), dtype=np.uint8)
    img = cv2.imdecode(_buf, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"无法解码图片: {image_path}")

    img_h, img_w = img.shape[:2]

    # 自动校准画布位置
    calib = calibrate_canvas(debug_dir)
    _x_min, _x_max = calib["x_min"], calib["x_max"]
    _y_min, _y_max = calib["y_min"], calib["y_max"]
    # 使用检测到的画布边界覆盖硬编码值
    c_x_min, c_x_max = _x_min, _x_max
    c_y_min, c_y_max = _y_min, _y_max

    # 灰度化
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    debug_paths = {}
    if debug_dir:
        _os.makedirs(debug_dir, exist_ok=True)

    # === 共用边缘检测（双边滤波 + Canny） ===
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    edges = cv2.Canny(filtered, threshold1, threshold2)

    if mode == "m-path":
        # === m-path：Canny + 反相 + 贪心追踪（4向优先，无回画，推荐） ===
        edges_inv = 255 - edges

        if debug_dir:
            from datetime import datetime as _dt
            _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            _p = _os.path.join(debug_dir, f"edges_{_ts}.png")
            _ok, _buf = cv2.imencode('.png', edges)
            if _ok:
                with open(_p, 'wb') as _fw:
                    _fw.write(_buf.tobytes())
            debug_paths["edges"] = _p

        valid = _m_path_trace(edges_inv, min_area, max_contours)

    elif mode == "contour":
        # === contour：Canny + findContours（有来回画，备选） ===
        # 注意：不闭运算，避免密集区域边缘融合成实心块导致来回画严重

        if debug_dir:
            from datetime import datetime as _dt
            _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            _p = _os.path.join(debug_dir, f"edges_{_ts}.png")
            _ok, _buf = cv2.imencode('.png', edges)
            if _ok:
                with open(_p, 'wb') as _fw:
                    _fw.write(_buf.tobytes())
            debug_paths["edges"] = _p

        # findContours 提取轮廓（保留全部点，避免 CHAIN_APPROX_SIMPLE 的跨越问题）
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        valid = [c for c in contours if cv2.arcLength(c, False) >= min_area]
        valid.sort(key=lambda c: cv2.arcLength(c, False), reverse=True)
        if max_contours > 0:
            valid = valid[:max_contours]

    else:
        raise ValueError(f"未知模式: {mode}，仅支持 'm-path' 和 'canny'")

    # === 宽高比正确的画布映射 ===
    # 使用自动检测（或手动校准）的画布边界
    px_per_x = actual_width / SCALE   # e.g. 1920/1000 = 1.92
    px_per_y = actual_height / SCALE  # e.g. 1080/1000 = 1.08
    
    canvas_px_w = (c_x_max - c_x_min) * px_per_x
    canvas_px_h = (c_y_max - c_y_min) * px_per_y

    # 在物理像素空间计算统一缩放（保证图片不变形）
    px_scale = min(canvas_px_w / img_w, canvas_px_h / img_h)

    # 居中偏移（物理像素）
    img_px_w = img_w * px_scale
    img_px_h = img_h * px_scale
    center_px_x = (canvas_px_w - img_px_w) / 2
    center_px_y = (canvas_px_h - img_px_h) / 2

    # 画布左上角屏幕像素坐标
    canvas_left_px = c_x_min * px_per_x
    canvas_top_px = c_y_min * px_per_y

    # 坐标转换
    result = []
    for c in valid:
        # m-path 模式：pts_list = list of (x, y)
        # canny 模式：numpy 轮廓数组
        if mode == "contour":
            pts_list = [(int(pt[0][0]), int(pt[0][1])) for pt in c]
        else:
            pts_list = c

        norm = [
            (
                int((canvas_left_px + center_px_x + px * px_scale) / px_per_x),
                int((canvas_top_px + center_px_y + py * px_scale) / px_per_y),
            )
            for px, py in pts_list
        ]

        if len(norm) < 2:
            continue

        result.append(norm)

    info = {
        "image_size": f"{img_w}x{img_h}",
        "total_contours": len(valid),
        "px_scale": round(px_scale, 4),
        "canvas_px_size": f"{int(canvas_px_w)}x{int(canvas_px_h)}",
        "canvas_bounds": f"x=[{c_x_min},{c_x_max}] y=[{c_y_min},{c_y_max}]",
        "debug_paths": debug_paths,
    }
    return result, info
