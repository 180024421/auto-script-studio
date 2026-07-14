"""自由布局半自动流式排版（固定边距/行距，少抠像素）。"""

from __future__ import annotations

from typing import Any

from studio.services.free_layout import (
    DESIGN_W,
    clamp_widget_rect,
    default_rect_for_type,
    ensure_widget_rect,
    is_free_mode,
    min_rect_for_type,
    panel_design_size,
)

MARGIN_X = 24
GAP_Y = 16
GAP_X = 16
CONTENT_W = DESIGN_W - MARGIN_X * 2  # 672


def place_widget_in_flow(
    widgets: list[dict[str, Any]],
    w: dict[str, Any],
    *,
    design_w: int = DESIGN_W,
) -> None:
    """将控件放到列表底部下一行（全宽内容区）。"""
    ensure_widget_rect(w, len(widgets) + 1)
    content_w = max(120, design_w - MARGIN_X * 2)
    wtype = str(w.get("type", "input"))
    min_w, min_h = min_rect_for_type(wtype)
    h = max(min_h, int(w.get("layout_h", min_h)))
    # section / divider / text 保持合理默认高宽
    if wtype == "section":
        h = max(h, 120)
    bottom = 0
    if widgets:
        bottom = max(int(x.get("layout_y", 0) + x.get("layout_h", 56)) for x in widgets)
    y = MARGIN_X if not widgets else bottom + GAP_Y
    x, y, ww, hh = clamp_widget_rect(design_w, wtype, MARGIN_X, y, content_w, h)
    w["layout_x"] = x
    w["layout_y"] = y
    w["layout_w"] = ww
    w["layout_h"] = hh


def reflow_vertical(widgets: list[dict[str, Any]], *, design_w: int = DESIGN_W) -> None:
    """按当前顺序重新流式排布：左对齐、统一内容宽、固定行距。"""
    content_w = max(120, design_w - MARGIN_X * 2)
    y = MARGIN_X
    for i, w in enumerate(widgets):
        ensure_widget_rect(w, i + 1)
        wtype = str(w.get("type", "input"))
        min_w, min_h = min_rect_for_type(wtype)
        h = max(min_h, int(w.get("layout_h", min_h)))
        if wtype == "section":
            h = max(h, int(w.get("layout_h", 160)))
        # 窄文字框保留原宽，其它拉满内容宽
        if wtype in ("text", "label") and int(w.get("layout_w", content_w)) < content_w * 0.6:
            ww = max(min_w, int(w.get("layout_w", content_w)))
        else:
            ww = content_w
        x, y2, ww, hh = clamp_widget_rect(design_w, wtype, MARGIN_X, y, ww, h)
        w["layout_x"] = x
        w["layout_y"] = y2
        w["layout_w"] = ww
        w["layout_h"] = hh
        y = y2 + hh + GAP_Y


def align_left(widgets: list[dict[str, Any]], *, design_w: int = DESIGN_W) -> None:
    for w in widgets:
        wtype = str(w.get("type", "input"))
        x, y, ww, hh = clamp_widget_rect(
            design_w,
            wtype,
            MARGIN_X,
            int(w.get("layout_y", 0)),
            int(w.get("layout_w", CONTENT_W)),
            int(w.get("layout_h", 52)),
        )
        w["layout_x"] = x
        w["layout_y"] = y
        w["layout_w"] = ww
        w["layout_h"] = hh


def unify_width(widgets: list[dict[str, Any]], *, design_w: int = DESIGN_W) -> None:
    content_w = max(120, design_w - MARGIN_X * 2)
    for w in widgets:
        wtype = str(w.get("type", "input"))
        x, y, ww, hh = clamp_widget_rect(
            design_w,
            wtype,
            int(w.get("layout_x", MARGIN_X)),
            int(w.get("layout_y", 0)),
            content_w,
            int(w.get("layout_h", 52)),
        )
        w["layout_x"] = x
        w["layout_y"] = y
        w["layout_w"] = ww
        w["layout_h"] = hh


def pair_two_columns(
    widgets: list[dict[str, Any]],
    indices: list[int],
    *,
    design_w: int = DESIGN_W,
) -> None:
    """将选中的控件按两列并排（保留相对顺序）。"""
    if len(indices) < 2:
        return
    content_w = max(120, design_w - MARGIN_X * 2)
    col_w = (content_w - GAP_X) // 2
    ordered = sorted({i for i in indices if 0 <= i < len(widgets)})
    # 以第一个控件的 y 为基准分行
    y = int(widgets[ordered[0]].get("layout_y", MARGIN_X))
    col = 0
    row_h = 0
    for idx in ordered:
        w = widgets[idx]
        wtype = str(w.get("type", "input"))
        min_w, min_h = min_rect_for_type(wtype)
        h = max(min_h, int(w.get("layout_h", min_h)))
        x = MARGIN_X if col == 0 else MARGIN_X + col_w + GAP_X
        x, y2, ww, hh = clamp_widget_rect(design_w, wtype, x, y, col_w, h)
        w["layout_x"] = x
        w["layout_y"] = y2
        w["layout_w"] = ww
        w["layout_h"] = hh
        row_h = max(row_h, hh)
        col += 1
        if col >= 2:
            col = 0
            y = y2 + row_h + GAP_Y
            row_h = 0


def reflow_active_screen(layout: dict[str, Any]) -> bool:
    """对流式整理当前活动界面；成功返回 True。"""
    if not is_free_mode(layout):
        return False
    from studio.services.screen_layout import active_screen_widgets

    widgets = active_screen_widgets(layout)
    dw, _ = panel_design_size(layout.get("panel") or {})
    reflow_vertical(widgets, design_w=dw)
    return True
