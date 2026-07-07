"""全局标签页（界面）布局 — 按键精灵式 screens[] 模型。"""

from __future__ import annotations

import copy
from typing import Any

from studio.services.free_layout import (
    DESIGN_W,
    clamp_widget_rect,
    ensure_widget_rect,
    estimate_text_layout_width,
    min_rect_for_type,
    panel_design_size,
)

CHROME_PATH_TAG = -1


def is_host_display(panel: dict[str, Any] | None = None) -> bool:
    """APK 主页面承载表单，悬浮球启停，无底部 chrome 按钮区。"""
    mode = (panel or {}).get("display_mode", "host")
    return mode in ("host", "form")


def strip_action_widgets_from_screens(layout: dict[str, Any]) -> None:
    """host 模式：界面内不应出现开始/停止等动作按钮（仅悬浮窗启停）。"""
    from studio.services.layout_defaults import is_action_type

    for sc in layout.get("screens") or []:
        sc["widgets"] = [
            w for w in sc.get("widgets") or [] if not is_action_type(w.get("type", ""))
        ]


def ensure_migrated(layout: dict[str, Any]) -> None:
    """旧 widgets + 嵌套 tabs → screens[]，就地迁移（不拷贝）。"""
    if layout.get("screens"):
        layout.setdefault("panel", {}).setdefault("active_screen", 0)
        layout["widgets"] = normalize_chrome_widgets(layout.get("widgets") or [], layout.get("panel"))
        return
    screens_list: list[dict[str, Any]] = []
    chrome: list[dict[str, Any]] = []
    loose: list[dict[str, Any]] = []
    for w in layout.get("widgets") or []:
        if w.get("type") == "tabs":
            for tab in w.get("tabs") or []:
                screens_list.append(
                    {
                        "title": tab.get("title", "界面"),
                        "widgets": copy.deepcopy(tab.get("widgets") or []),
                    }
                )
        elif w.get("type") in ("start_script", "stop_script"):
            chrome.append(copy.deepcopy(w))
        else:
            loose.append(copy.deepcopy(w))
    if not screens_list:
        screens_list = [
            {"title": "标签页1", "widgets": []},
            {"title": "界面1", "widgets": loose or []},
        ]
    elif loose:
        screens_list[0].setdefault("widgets", []).extend(loose)
    if not chrome:
        chrome = [
            {
                "id": "start",
                "type": "start_script",
                "label": "开始",
                "color": "#2563EB",
                "layout_x": 24,
                "layout_y": 4,
                "layout_w": 672,
                "layout_h": 52,
            },
        ]
    layout["screens"] = screens_list
    layout["widgets"] = normalize_chrome_widgets(chrome, layout.get("panel"))
    layout["version"] = max(3, int(layout.get("version", 2)))
    layout.setdefault("panel", {}).setdefault("active_screen", 0)


def migrate_layout(layout: dict[str, Any]) -> dict[str, Any]:
    """返回迁移后的深拷贝（只读场景）。"""
    out = copy.deepcopy(layout)
    ensure_migrated(out)
    return out


def screens(layout: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_migrated(layout)
    return layout.setdefault("screens", [])


def chrome_widgets(layout: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_migrated(layout)
    normalized = normalize_chrome_widgets(layout.setdefault("widgets", []), layout.get("panel"))
    layout["widgets"] = normalized
    return normalized


def normalize_chrome_widgets(
    widgets: list[dict[str, Any]],
    panel: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """底部 chrome：host/form 无 chrome；minimal 悬浮窗保留开始+停止小图标。"""
    if is_host_display(panel):
        return []
    mode = (panel or {}).get("display_mode", "host")
    minimal = mode == "minimal"
    if minimal:
        out = [copy.deepcopy(w) for w in widgets]
    else:
        out = [w for w in widgets if w.get("type") != "stop_script"]
    has_start = any(w.get("type") == "start_script" for w in out)
    if not has_start:
        out.insert(
            0,
            {
                "id": "start",
                "type": "start_script",
                "label": "开始",
                "color": "#2563EB",
                "layout_x": 0 if minimal else 24,
                "layout_y": 8 if minimal else 4,
                "layout_w": 32 if minimal else 672,
                "layout_h": 32 if minimal else 52,
            },
        )
    if minimal and not any(w.get("type") == "stop_script" for w in out):
        out.append(
            {
                "id": "stop",
                "type": "stop_script",
                "label": "结束",
                "color": "#DC2626",
                "layout_x": 34,
                "layout_y": 8,
                "layout_w": 32,
                "layout_h": 32,
            },
        )
    for w in out:
        if w.get("type") == "start_script":
            if minimal:
                w.setdefault("layout_x", 0)
                w.setdefault("layout_y", 8)
                w.setdefault("layout_w", 32)
                w.setdefault("layout_h", 32)
            else:
                w.setdefault("layout_x", 24)
                w.setdefault("layout_y", 4)
                w.setdefault("layout_w", 672)
                w.setdefault("layout_h", 52)
        if minimal and w.get("type") == "stop_script":
            w.setdefault("layout_x", 34)
            w.setdefault("layout_y", 8)
            w.setdefault("layout_w", 32)
            w.setdefault("layout_h", 32)
    return out


def active_screen_index(layout: dict[str, Any]) -> int:
    panel = layout.get("panel", {})
    idx = int(panel.get("active_screen", 0))
    sc = screens(layout)
    if not sc:
        return 0
    return max(0, min(len(sc) - 1, idx))


def active_screen_widgets(layout: dict[str, Any]) -> list[dict[str, Any]]:
    sc = screens(layout)
    idx = active_screen_index(layout)
    if not sc:
        return []
    return sc[idx].setdefault("widgets", [])


def editor_widget_list(layout: dict[str, Any]) -> list[dict[str, Any]]:
    """布局编辑器「当前界面控件」列表（自由/网格均读 screens[active]）。"""
    ensure_migrated(layout)
    if screens(layout):
        return active_screen_widgets(layout)
    return layout.setdefault("widgets", [])


def flatten_all_widgets(layout: dict[str, Any]) -> list[dict[str, Any]]:
    """供 PanelState / Lua 扁平遍历。"""
    out: list[dict[str, Any]] = []
    for sc in screens(layout):
        out.extend(sc.get("widgets") or [])
    out.extend(chrome_widgets(layout))
    return out


def ensure_all_rects(layout: dict[str, Any]) -> dict[str, Any]:
    ensure_migrated(layout)
    for sc in layout.get("screens") or []:
        for j, w in enumerate(sc.get("widgets") or []):
            ensure_widget_rect(w, j + 1)
    for j, w in enumerate(layout.get("widgets") or []):
        ensure_widget_rect(w, j + 1)
    return layout


def resolve_widget(layout: dict[str, Any], path: tuple[int, ...]) -> dict[str, Any] | None:
    ensure_migrated(layout)
    if len(path) != 2:
        return None
    screen_idx, widget_idx = path
    if screen_idx == CHROME_PATH_TAG:
        cw = layout.get("widgets") or []
        return cw[widget_idx] if 0 <= widget_idx < len(cw) else None
    sc = layout.get("screens") or []
    if 0 <= screen_idx < len(sc):
        ws = sc[screen_idx].get("widgets") or []
        if 0 <= widget_idx < len(ws):
            return ws[widget_idx]
    return None


def set_widget_rect(
    layout: dict[str, Any],
    path: tuple[int, ...],
    x: int,
    y: int,
    w: int,
    h: int,
) -> dict[str, Any]:
    ensure_migrated(layout)
    target = resolve_widget(layout, path)
    if target is None:
        return layout
    dw, _ = panel_design_size(layout.get("panel", {}))
    wtype = str(target.get("type", ""))
    max_y = 64 if len(path) == 2 and path[0] == CHROME_PATH_TAG else None
    cx, cy, cw, ch = clamp_widget_rect(dw, wtype, x, y, w, h, max_y=max_y)
    target["layout_x"] = cx
    target["layout_y"] = cy
    target["layout_w"] = cw
    target["layout_h"] = ch
    return layout


def content_height(layout: dict[str, Any], screen_idx: int, *, min_canvas: int = 800) -> int:
    """界面可滚动内容高度（设计像素）。"""
    sc = screens(layout)
    if screen_idx < 0 or screen_idx >= len(sc):
        return max(min_canvas, 400)
    ws = sc[screen_idx].get("widgets") or []
    if not ws:
        return max(min_canvas, 400)
    bottom = max(int(w.get("layout_y", 0) + w.get("layout_h", 56)) for w in ws)
    return max(min_canvas, bottom + 80)


def repair_screen_widgets(widgets: list[dict[str, Any]]) -> None:
    """修正无效/重叠的自由布局坐标，保证画布可见。"""
    if not widgets:
        return
    y = 24
    prev_y = -999
    for i, w in enumerate(widgets):
        ensure_widget_rect(w, i + 1)
        wtype = str(w.get("type", ""))
        if wtype == "divider":
            w["text"] = ""
            w["layout_h"] = max(8, min(16, int(w.get("layout_h", 12))))
        if wtype in ("text", "label"):
            style = str(w.get("text_style") or "normal") if wtype == "text" else "normal"
            est_w = estimate_text_layout_width(str(w.get("text") or w.get("label") or ""), style)
            raw_w = int(w.get("layout_w", est_w))
            if raw_w > est_w + 32:
                w["layout_w"] = est_w
        raw_w = int(w.get("layout_w", 0))
        raw_h = int(w.get("layout_h", 0))
        raw_y = int(w.get("layout_y", y))
        raw_x = int(w.get("layout_x", 24))
        min_w, min_h = min_rect_for_type(wtype)
        broken = (
            raw_w < min_w
            or raw_h < min_h
            or raw_y < 16
            or raw_x + raw_w > DESIGN_W
            or raw_x > DESIGN_W - min_w
        )
        dup = i > 0 and abs(raw_y - prev_y) < 8
        if broken or dup:
            raw_y = y
        w["layout_y"] = raw_y
        w["layout_w"] = max(min_w, min(672, raw_w if raw_w >= min_w else 672))
        if wtype == "divider":
            w["layout_h"] = max(8, min(16, raw_h if raw_h >= min_h else 12))
        elif wtype in ("text", "label"):
            w["layout_h"] = max(min_h, raw_h if raw_h >= min_h else 36)
        else:
            w["layout_h"] = max(40, raw_h if raw_h >= 32 else 56)
        w["layout_x"] = max(24, min(DESIGN_W - int(w["layout_w"]), int(w.get("layout_x", 24))))
        prev_y = raw_y
        y = raw_y + int(w["layout_h"]) + 16


def repair_all_screens(layout: dict[str, Any]) -> None:
    ensure_migrated(layout)
    for sc in screens(layout):
        repair_screen_widgets(sc.get("widgets") or [])
    repair_screen_widgets(chrome_widgets(layout))


def path_for_chrome(widget_idx: int) -> tuple[int, int]:
    return (CHROME_PATH_TAG, widget_idx)


def path_for_screen(screen_idx: int, widget_idx: int) -> tuple[int, int]:
    return (screen_idx, widget_idx)


def export_screen_dict(layout: dict[str, Any], screen_idx: int) -> dict[str, Any]:
    """导出单个界面（不含 chrome）。"""
    ensure_migrated(layout)
    sc = screens(layout)
    if screen_idx < 0 or screen_idx >= len(sc):
        raise ValueError(f"界面索引越界: {screen_idx}")
    item = sc[screen_idx]
    return {
        "version": 1,
        "title": item.get("title", f"界面{screen_idx + 1}"),
        "widgets": copy.deepcopy(item.get("widgets") or []),
    }


def import_screen_dict(
    layout: dict[str, Any],
    data: dict[str, Any],
    *,
    replace: bool = False,
) -> int:
    """导入界面；replace=True 时替换当前 active 界面。"""
    ensure_migrated(layout)
    sc = screens(layout)
    payload = {
        "title": str(data.get("title", "导入界面")).strip() or "导入界面",
        "widgets": copy.deepcopy(data.get("widgets") or []),
    }
    idx = active_screen_index(layout)
    if replace and sc:
        sc[idx] = payload
        return idx
    sc.append(payload)
    layout.setdefault("panel", {})["active_screen"] = len(sc) - 1
    return len(sc) - 1
