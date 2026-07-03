"""自由布局（手机画布）坐标工具。"""

from __future__ import annotations

import copy
from typing import Any

DESIGN_W = 720
DESIGN_H = 1280

DEFAULT_RECT: dict[str, int] = {
    "layout_x": 24,
    "layout_y": 120,
    "layout_w": 672,
    "layout_h": 56,
}


def panel_design_size(panel: dict[str, Any]) -> tuple[int, int]:
    return int(panel.get("design_width", DESIGN_W)), int(panel.get("design_height", DESIGN_H))


def is_free_mode(layout: dict[str, Any]) -> bool:
    return layout.get("panel", {}).get("layout_mode", "grid") == "free"


def min_rect_for_type(wtype: str) -> tuple[int, int]:
    """自由布局控件最小宽/高（设计像素）。"""
    if wtype == "divider":
        return 48, 4
    if wtype in ("text", "label"):
        return 48, 20
    if wtype in ("input", "textarea", "select", "radio", "multiselect"):
        return 160, 48
    if wtype in ("switch", "slider", "stepper", "time_range"):
        return 160, 44
    if wtype in ("start_script", "stop_script", "tap", "lua", "collapse"):
        return 80, 40
    return 120, 44


def estimate_text_layout_width(text: str, style: str = "normal") -> int:
    """按文字内容与样式估算文字框/标签所需宽度（设计像素）。"""
    t = (text or "").strip()
    if not t:
        return 80
    s = (style or "normal").lower()
    char_w = {"title": 14, "hint": 11, "normal": 12}.get(s, 12)
    pad_x = 24
    return min(DESIGN_W - 48, max(48, len(t) * char_w + pad_x))


def default_rect_for_type(wtype: str, index: int) -> dict[str, int]:
    y = 100 + max(0, index - 1) * 72
    if wtype in ("start_script", "stop_script", "tap", "lua", "collapse"):
        return {"layout_x": 24 + (index % 2) * 340, "layout_y": y, "layout_w": 320, "layout_h": 52}
    if wtype == "tabs":
        return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 360}
    if wtype == "label":
        return {"layout_x": 24, "layout_y": y, "layout_w": estimate_text_layout_width("说明文字"), "layout_h": 36}
    if wtype == "text":
        return {"layout_x": 24, "layout_y": y, "layout_w": estimate_text_layout_width("提示文字", "hint"), "layout_h": 36}
    if wtype == "switch":
        return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 52}
    if wtype == "time_range":
        return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 56}
    if wtype == "textarea":
        return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 120}
    if wtype == "divider":
        return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 16}
    if wtype == "slider":
        return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 52}
    if wtype == "stepper":
        return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 52}
    return {"layout_x": 24, "layout_y": y, "layout_w": 672, "layout_h": 52}


def ensure_widget_rect(w: dict[str, Any], index: int = 0) -> None:
    if all(k in w for k in ("layout_x", "layout_y", "layout_w", "layout_h")):
        return
    rect = default_rect_for_type(str(w.get("type", "input")), index)
    w.setdefault("layout_x", rect["layout_x"])
    w.setdefault("layout_y", rect["layout_y"])
    w.setdefault("layout_w", rect["layout_w"])
    w.setdefault("layout_h", rect["layout_h"])


def ensure_layout_rects(layout: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(layout)
    if not is_free_mode(out):
        return out
    for i, w in enumerate(out.get("widgets") or []):
        ensure_widget_rect(w, i + 1)
        if w.get("type") == "tabs":
            for tab in w.get("tabs") or []:
                for j, cw in enumerate(tab.get("widgets") or []):
                    ensure_widget_rect(cw, j + 1)
    return out


def clamp_widget_rect(
    dw: int,
    wtype: str,
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    max_y: int | None = None,
) -> tuple[int, int, int, int]:
    """将控件矩形限制在画布水平范围内；垂直方向仅保证 y>=0，可超出视口以滚动布局。"""
    min_w, min_h = min_rect_for_type(wtype)
    w = max(min_w, min(dw, int(w)))
    h = max(min_h, int(h))
    x = max(0, min(max(0, dw - w), int(x)))
    y = max(0, int(y))
    if max_y is not None:
        y = min(y, max(0, int(max_y) - h))
    w = min(w, dw - x)
    return x, y, w, h
