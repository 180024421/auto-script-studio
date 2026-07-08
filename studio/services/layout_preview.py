"""在设备截图上绘制浮动面板预览（与 Android OverlayService 布局语义对齐）。"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen


def _parse_color(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color if hex_color.startswith("#") else f"#{hex_color}")
    c.setAlpha(alpha)
    return c


def dp_to_px(dp: float, image_width: int) -> int:
    """按截图宽度估算 dp→px（与常见 360dp 屏宽一致）。"""
    density = max(1.0, image_width / 360.0)
    return max(1, int(dp * density))


def _paint_free_layout_overlay(
    painter: QPainter,
    layout: dict[str, Any],
    image_w: int,
    image_h: int,
    scale: float = 1.0,
) -> None:
    """自由布局：面板外框 + 当前界面控件虚线框。"""
    from studio.services.panel_geometry import compute_free_panel_overlay_metrics
    from studio.services.screen_layout import active_screen_widgets

    panel = layout.get("panel", {})
    start_x = int(panel.get("start_x", 20))
    start_y = int(panel.get("start_y", 200))
    title = str(panel.get("title", "脚本助手"))
    theme = str(panel.get("theme", "light")).lower()
    is_dark = theme == "dark"

    metrics = compute_free_panel_overlay_metrics(
        layout, image_w, image_h, dp_to_px_fn=dp_to_px
    )
    panel_w = metrics.panel_w_px
    panel_h = metrics.panel_h_px
    inner_scale = metrics.inner_scale
    header_off = metrics.header_off_design * inner_scale

    sx = start_x * scale
    sy = start_y * scale
    pw = panel_w * scale
    ph = panel_h * scale
    pad = max(4, int(8 * scale))

    border_color = "#4caf50" if is_dark else "#2563eb"
    painter.setBrush(Qt.NoBrush)
    pen = QPen(_parse_color(border_color, 210), max(1, int(2 * scale)), Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.drawRoundedRect(QRectF(sx, sy, pw, ph), 10 * scale, 10 * scale)

    title_color = QColor(37, 99, 235, 220) if not is_dark else QColor(76, 175, 80, 220)
    painter.setPen(title_color)
    font = QFont()
    font.setPointSizeF(max(7.0, 9 * scale))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(
        QRectF(sx + pad, sy + pad, pw - pad * 2, 20 * scale),
        Qt.AlignLeft | Qt.AlignVCenter,
        f"{title}（预览框）",
    )

    widget_pen = QPen(_parse_color("#94A3B8", 160), max(1, int(1 * scale)), Qt.PenStyle.DotLine)
    painter.setPen(widget_pen)
    for w in active_screen_widgets(layout):
        wx = sx + pad + int(w.get("layout_x", 0)) * inner_scale
        wy = sy + pad + header_off + int(w.get("layout_y", 0)) * inner_scale
        ww = max(4, int(w.get("layout_w", 48)) * inner_scale)
        wh = max(4, int(w.get("layout_h", 24)) * inner_scale)
        painter.drawRect(QRectF(wx, wy, ww, wh))

    font.setBold(False)
    font.setPointSizeF(max(6.0, 7.5 * scale))
    painter.setFont(font)
    hint_color = QColor(100, 116, 139, 180)
    painter.setPen(hint_color)
    painter.drawText(
        QRectF(sx + pad, sy + ph - 24 * scale, pw - pad * 2, 18 * scale),
        Qt.AlignCenter,
        "自由布局 · 虚线框为控件区域",
    )


def paint_layout_overlay(
    painter: QPainter,
    layout: dict[str, Any],
    image_w: int,
    image_h: int,
    scale: float = 1.0,
) -> None:
    """在已缩放的 pixmap 上绘制面板与动作坐标标记。"""
    if not layout.get("enabled", True):
        return

    from studio.services.free_layout import is_free_mode

    if is_free_mode(layout):
        _paint_free_layout_overlay(painter, layout, image_w, image_h, scale)
        return

    panel = layout.get("panel", {})
    widgets: list[dict[str, Any]] = layout.get("widgets") or layout.get("buttons", [])
    start_x = int(panel.get("start_x", 20))
    start_y = int(panel.get("start_y", 200))
    panel_w = dp_to_px(int(panel.get("width_dp", 220)), image_w)
    cols = max(1, min(3, int(panel.get("columns", 2))))
    opacity = float(panel.get("opacity", 0.96))
    title = str(panel.get("title", "脚本助手"))
    show_log = bool(panel.get("show_log", True))
    theme = str(panel.get("theme", "light")).lower()
    is_dark = theme == "dark"

    sx = start_x * scale
    sy = start_y * scale
    pw = panel_w * scale
    pad = max(4, int(8 * scale))
    btn_h = max(18, int(40 * scale))
    title_h = max(16, int(22 * scale))
    log_h = max(30, int(80 * scale)) if show_log else 0
    gap = max(2, int(pad // 2))

    rows: list[list[dict[str, Any]]] = []
    current_row: list[dict[str, Any]] = []
    col_used = 0
    for b in widgets:
        span = max(1, min(cols, int(b.get("width", 1))))
        if col_used + span > cols and current_row:
            rows.append(current_row)
            current_row = []
            col_used = 0
        current_row.append(b)
        col_used += span
        if col_used >= cols:
            rows.append(current_row)
            current_row = []
            col_used = 0
    if current_row:
        rows.append(current_row)
    row_count = len(rows)

    panel_h = pad * 2 + title_h + row_count * btn_h + max(0, row_count - 1) * gap + log_h

    # 面板背景
    bg_alpha = int(245 * opacity) if not is_dark else int(235 * opacity)
    panel_bg = "#282830" if is_dark else "#ffffff"
    border_color = "#4caf50" if is_dark else "#2563eb"
    painter.setBrush(_parse_color(panel_bg, bg_alpha))
    accent = _parse_color(border_color, int(220 * opacity))
    painter.setPen(QPen(accent, max(1, int(2 * scale))))
    painter.drawRoundedRect(QRectF(sx, sy, pw, panel_h), 10 * scale, 10 * scale)

    # 标题栏
    title_bar_h = pad + title_h
    painter.setPen(Qt.NoPen)
    title_bar_bg = "#1e2838" if is_dark else "#eff6ff"
    painter.setBrush(_parse_color(title_bar_bg, int(230 * opacity)))
    painter.drawRoundedRect(QRectF(sx + 1, sy + 1, pw - 2, title_bar_h), 10 * scale, 10 * scale)

    # 标题
    title_color = QColor(232, 238, 246, int(255 * opacity)) if is_dark else QColor(26, 35, 50, int(255 * opacity))
    log_text = QColor(176, 190, 197, int(220 * opacity)) if is_dark else QColor(74, 93, 117, int(220 * opacity))
    painter.setPen(title_color)
    font = QFont()
    font.setPointSizeF(max(7.0, 9 * scale))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRectF(sx + pad, sy + pad // 2, pw - pad * 2, title_h), Qt.AlignCenter, title)

    # 按钮网格
    font.setBold(False)
    font.setPointSizeF(max(6.0, 8 * scale))
    painter.setFont(font)
    cell_w = (pw - pad * 2 - pad * (cols - 1)) / cols
    y = sy + pad + title_h
    row = 0
    col = 0

    def next_row() -> None:
        nonlocal row, col, y
        row += 1
        col = 0
        y += btn_h + gap

    for b in widgets:
        span = max(1, min(cols, int(b.get("width", 1))))
        if col + span > cols:
            next_row()
        bx = sx + pad + col * (cell_w + pad)
        by = y
        bw = cell_w * span + pad * (span - 1)
        wtype = str(b.get("type", ""))
        if wtype in ("label", "text"):
            style = str(b.get("text_style", "title" if wtype == "label" else "normal"))
            painter.setPen(title_color if style == "title" else log_text)
            align = Qt.AlignLeft | Qt.AlignVCenter
            if str(b.get("align", "")) == "center":
                align = Qt.AlignCenter
            elif str(b.get("align", "")) == "right":
                align = Qt.AlignRight | Qt.AlignVCenter
            painter.drawText(
                QRectF(bx, by, bw, btn_h),
                align,
                str(b.get("text") or b.get("label", "提示文字")),
            )
        elif wtype in ("input", "select"):
            label_w = bw * 0.18
            ctrl_x = bx + label_w + 4 * scale
            ctrl_w = bw - label_w - 4 * scale
            painter.setPen(log_text)
            painter.drawText(
                QRectF(bx, by, label_w, btn_h),
                Qt.AlignRight | Qt.AlignVCenter,
                str(b.get("label", "") or "标签"),
            )
            painter.setBrush(_parse_color("#f8fafc" if not is_dark else "#1a1a1a", int(220 * opacity)))
            painter.setPen(QPen(_parse_color("#dce3ed" if not is_dark else "#444", 160), 1))
            painter.drawRoundedRect(QRectF(ctrl_x, by + 2 * scale, ctrl_w, btn_h - 4 * scale), 5 * scale, 5 * scale)
            hint = b.get("placeholder", wtype) if wtype == "input" else "▼"
            painter.setPen(log_text)
            painter.drawText(
                QRectF(ctrl_x + 4 * scale, by, ctrl_w - 8 * scale, btn_h),
                Qt.AlignVCenter,
                str(hint),
            )
        elif wtype == "radio":
            label_w = bw * 0.18
            painter.setPen(log_text)
            painter.drawText(
                QRectF(bx, by, label_w, btn_h),
                Qt.AlignRight | Qt.AlignTop,
                str(b.get("label", "单选")),
            )
            oy = by + 2 * scale
            for i, opt in enumerate((b.get("options") or ["A", "B"])[:3]):
                painter.drawText(
                    QRectF(bx + label_w + 4 * scale, oy + i * btn_h * 0.22, bw - label_w, btn_h * 0.2),
                    Qt.AlignLeft,
                    f"○ {opt}",
                )
        elif wtype == "multiselect":
            label_w = bw * 0.18
            painter.setPen(log_text)
            painter.drawText(
                QRectF(bx, by, label_w, btn_h),
                Qt.AlignRight | Qt.AlignVCenter,
                str(b.get("label", "多选")),
            )
            opts = (b.get("options") or ["A", "B"])[:4]
            opt_w = (bw - label_w - 8 * scale) / max(1, len(opts))
            for i, opt in enumerate(opts):
                ox = bx + label_w + 4 * scale + i * opt_w
                painter.drawText(
                    QRectF(ox, by, opt_w, btn_h),
                    Qt.AlignLeft | Qt.AlignVCenter,
                    f"☑ {opt}",
                )
        elif wtype == "tabs":
            tab_w = bw / max(1, len(b.get("tabs") or [{"title": "1"}, {"title": "2"}]))
            for i, tab in enumerate((b.get("tabs") or [])[:3]):
                tx = bx + i * tab_w
                painter.setBrush(_parse_color("#2563eb" if i == 0 else "#e2e8f0", int(200 * opacity)))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(tx, by, tab_w - 2, btn_h * 0.35), 3 * scale, 3 * scale)
                painter.setPen(QColor(255, 255, 255) if i == 0 else title_color)
                painter.drawText(QRectF(tx, by, tab_w - 2, btn_h * 0.35), Qt.AlignCenter, str(tab.get("title", "页")))
        else:
            color = b.get("color", "#607D8B")
            painter.setBrush(_parse_color(color, int(240 * opacity)))
            painter.setPen(QPen(_parse_color("#ffffff", 80), max(1, int(1 * scale))))
            painter.drawRoundedRect(QRectF(bx, by, bw, btn_h), 6 * scale, 6 * scale)
            lum = _color_luminance(color)
            text_color = QColor(26, 35, 50, int(255 * opacity)) if lum > 165 else QColor(255, 255, 255, int(255 * opacity))
            painter.setPen(text_color)
            label = str(b.get("label", "按钮"))
            painter.drawText(QRectF(bx, by, bw, btn_h), Qt.AlignCenter, label)
        col += span
        if col >= cols:
            next_row()

    if show_log:
        log_y = sy + panel_h - log_h - pad // 2
        log_bg = "#1a1a1a" if is_dark else "#f8fafc"
        log_border = "#2e3d52" if is_dark else "#dce3ed"
        painter.setBrush(_parse_color(log_bg, int(230 * opacity)))
        painter.setPen(QPen(_parse_color(log_border, 180), max(1, int(1 * scale))))
        painter.drawRoundedRect(QRectF(sx + pad, log_y, pw - pad * 2, log_h - pad // 2), 5 * scale, 5 * scale)
        painter.setPen(log_text)
        font.setPointSizeF(max(5.0, 7 * scale))
        painter.setFont(font)
        painter.drawText(QRectF(sx + pad * 2, log_y, pw - pad * 4, log_h), Qt.AlignLeft | Qt.AlignTop, "日志…")

    # 收起小球（右侧）
    ball = dp_to_px(int(panel.get("ball_size_dp", 48)), image_w)
    ball_s = ball * scale
    ball_x = (image_w - ball - 24) * scale
    ball_y = sy
    ball_color = "#4caf50" if is_dark else "#2563eb"
    ball_border = "#388e3c" if is_dark else "#1d4ed8"
    ball_text = QColor(255, 255, 255) if is_dark else QColor(255, 255, 255)
    painter.setBrush(_parse_color(ball_color, int(230 * opacity)))
    painter.setPen(QPen(_parse_color(ball_border, 180), max(1, int(1 * scale))))
    painter.drawEllipse(QRectF(ball_x, ball_y, ball_s, ball_s))
    painter.setPen(ball_text)
    painter.drawText(QRectF(ball_x, ball_y, ball_s, ball_s), Qt.AlignCenter, "▶")

    # 动作坐标标记（tap / swipe / long_press）
    _paint_action_markers(painter, widgets, scale)


def _color_luminance(hex_color: str) -> float:
    c = QColor(hex_color if hex_color.startswith("#") else f"#{hex_color}")
    return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()


def _paint_action_markers(painter: QPainter, widgets: list[dict[str, Any]], scale: float) -> None:
    pen_action = QPen(QColor(217, 119, 6, 220), max(1, int(2 * scale)))
    pen_swipe = QPen(QColor(37, 99, 235, 220), max(1, int(2 * scale)))
    font = QFont()
    font.setPointSizeF(max(6.0, 8 * scale))
    painter.setFont(font)

    for b in widgets:
        btype = str(b.get("type", "")).lower()
        label = str(b.get("label", ""))

        if btype in ("tap", "long_press") and (b.get("x") or b.get("y")):
            x = int(b.get("x", 0)) * scale
            y = int(b.get("y", 0)) * scale
            r = max(6, int(10 * scale))
            painter.setPen(pen_action)
            painter.setBrush(QColor(217, 119, 6, 50))
            painter.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))
            painter.drawLine(int(x - r - 4), int(y), int(x + r + 4), int(y))
            painter.drawLine(int(x), int(y - r - 4), int(x), int(y + r + 4))
            painter.setPen(QColor(180, 83, 9))
            painter.drawText(int(x + r + 2), int(y - 2), label)

        elif btype == "swipe":
            x1 = int(b.get("x1", 0)) * scale
            y1 = int(b.get("y1", 0)) * scale
            x2 = int(b.get("x2", 0)) * scale
            y2 = int(b.get("y2", 0)) * scale
            if x1 == x2 and y1 == y2:
                continue
            painter.setPen(pen_swipe)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            # 箭头
            painter.setBrush(QColor(37, 99, 235, 160))
            painter.drawEllipse(QRectF(x1 - 4 * scale, y1 - 4 * scale, 8 * scale, 8 * scale))
            painter.drawEllipse(QRectF(x2 - 5 * scale, y2 - 5 * scale, 10 * scale, 10 * scale))
            painter.setPen(QColor(29, 78, 216))
            painter.drawText(int((x1 + x2) / 2 + 4), int((y1 + y2) / 2 - 4), label)


def current_layout_dict(editor_layout: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if editor_layout is None:
        return None
    return editor_layout
