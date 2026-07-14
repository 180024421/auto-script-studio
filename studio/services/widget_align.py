"""自由布局控件对齐与分布。"""

from __future__ import annotations

from typing import Any, Literal

from studio.services.free_layout import clamp_widget_rect

AlignKind = Literal[
    "left",
    "right",
    "hcenter",
    "top",
    "bottom",
    "vcenter",
]
DistributeKind = Literal["horizontal", "vertical"]

STYLE_KEYS = (
    "color",
    "text_style",
    "button_style",
    "width",
    "layout_w",
    "layout_h",
)


def _rect(w: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        int(w.get("layout_x", 0)),
        int(w.get("layout_y", 0)),
        int(w.get("layout_w", 120)),
        int(w.get("layout_h", 48)),
    )


def align_widgets(
    widgets: list[dict[str, Any]],
    indices: list[int],
    kind: AlignKind,
    *,
    design_w: int = 720,
) -> None:
    ordered = sorted({i for i in indices if 0 <= i < len(widgets)})
    if len(ordered) < 2:
        return
    rects = [_rect(widgets[i]) for i in ordered]
    if kind == "left":
        target = min(r[0] for r in rects)
        for i, (x, y, ww, hh) in zip(ordered, rects):
            _apply(widgets[i], target, y, ww, hh, design_w)
    elif kind == "right":
        target = max(r[0] + r[2] for r in rects)
        for i, (x, y, ww, hh) in zip(ordered, rects):
            _apply(widgets[i], target - ww, y, ww, hh, design_w)
    elif kind == "hcenter":
        left = min(r[0] for r in rects)
        right = max(r[0] + r[2] for r in rects)
        mid = (left + right) // 2
        for i, (x, y, ww, hh) in zip(ordered, rects):
            _apply(widgets[i], mid - ww // 2, y, ww, hh, design_w)
    elif kind == "top":
        target = min(r[1] for r in rects)
        for i, (x, y, ww, hh) in zip(ordered, rects):
            _apply(widgets[i], x, target, ww, hh, design_w)
    elif kind == "bottom":
        target = max(r[1] + r[3] for r in rects)
        for i, (x, y, ww, hh) in zip(ordered, rects):
            _apply(widgets[i], x, target - hh, ww, hh, design_w)
    elif kind == "vcenter":
        top = min(r[1] for r in rects)
        bottom = max(r[1] + r[3] for r in rects)
        mid = (top + bottom) // 2
        for i, (x, y, ww, hh) in zip(ordered, rects):
            _apply(widgets[i], x, mid - hh // 2, ww, hh, design_w)


def distribute_widgets(
    widgets: list[dict[str, Any]],
    indices: list[int],
    kind: DistributeKind,
    *,
    design_w: int = 720,
) -> None:
    ordered = sorted({i for i in indices if 0 <= i < len(widgets)})
    if len(ordered) < 3:
        return
    if kind == "horizontal":
        items = sorted(ordered, key=lambda i: int(widgets[i].get("layout_x", 0)))
        left = int(widgets[items[0]].get("layout_x", 0))
        right = max(
            int(widgets[i].get("layout_x", 0)) + int(widgets[i].get("layout_w", 0)) for i in items
        )
        widths = [int(widgets[i].get("layout_w", 0)) for i in items]
        gap_total = right - left - sum(widths)
        gap = gap_total / (len(items) - 1)
        cursor = float(left)
        for i, ww in zip(items, widths):
            y = int(widgets[i].get("layout_y", 0))
            hh = int(widgets[i].get("layout_h", 48))
            _apply(widgets[i], int(round(cursor)), y, ww, hh, design_w)
            cursor += ww + gap
    else:
        items = sorted(ordered, key=lambda i: int(widgets[i].get("layout_y", 0)))
        top = int(widgets[items[0]].get("layout_y", 0))
        bottom = max(
            int(widgets[i].get("layout_y", 0)) + int(widgets[i].get("layout_h", 0)) for i in items
        )
        heights = [int(widgets[i].get("layout_h", 0)) for i in items]
        gap_total = bottom - top - sum(heights)
        gap = gap_total / (len(items) - 1)
        cursor = float(top)
        for i, hh in zip(items, heights):
            x = int(widgets[i].get("layout_x", 0))
            ww = int(widgets[i].get("layout_w", 120))
            _apply(widgets[i], x, int(round(cursor)), ww, hh, design_w)
            cursor += hh + gap


def equalize_size(
    widgets: list[dict[str, Any]],
    indices: list[int],
    *,
    dimension: Literal["width", "height", "both"] = "both",
    design_w: int = 720,
) -> None:
    """以选中第一个为基准统一宽/高。"""
    ordered = sorted({i for i in indices if 0 <= i < len(widgets)})
    if len(ordered) < 2:
        return
    base = widgets[ordered[0]]
    bw = int(base.get("layout_w", 120))
    bh = int(base.get("layout_h", 48))
    for i in ordered[1:]:
        w = widgets[i]
        ww = bw if dimension in ("width", "both") else int(w.get("layout_w", bw))
        hh = bh if dimension in ("height", "both") else int(w.get("layout_h", bh))
        _apply(w, int(w.get("layout_x", 0)), int(w.get("layout_y", 0)), ww, hh, design_w)


def match_spacing(
    widgets: list[dict[str, Any]],
    indices: list[int],
    *,
    axis: Literal["horizontal", "vertical"] = "horizontal",
    design_w: int = 720,
) -> None:
    """按前两个控件间距，统一后续相邻控件间距（保持顺序）。"""
    ordered = sorted({i for i in indices if 0 <= i < len(widgets)})
    if len(ordered) < 3:
        return
    if axis == "horizontal":
        items = sorted(ordered, key=lambda i: int(widgets[i].get("layout_x", 0)))
        a, b = widgets[items[0]], widgets[items[1]]
        gap = int(b.get("layout_x", 0)) - (int(a.get("layout_x", 0)) + int(a.get("layout_w", 0)))
        cursor = int(b.get("layout_x", 0)) + int(b.get("layout_w", 0)) + gap
        for i in items[2:]:
            w = widgets[i]
            ww = int(w.get("layout_w", 120))
            hh = int(w.get("layout_h", 48))
            y = int(w.get("layout_y", 0))
            _apply(w, cursor, y, ww, hh, design_w)
            cursor = int(w["layout_x"]) + int(w["layout_w"]) + gap
    else:
        items = sorted(ordered, key=lambda i: int(widgets[i].get("layout_y", 0)))
        a, b = widgets[items[0]], widgets[items[1]]
        gap = int(b.get("layout_y", 0)) - (int(a.get("layout_y", 0)) + int(a.get("layout_h", 0)))
        cursor = int(b.get("layout_y", 0)) + int(b.get("layout_h", 0)) + gap
        for i in items[2:]:
            w = widgets[i]
            ww = int(w.get("layout_w", 120))
            hh = int(w.get("layout_h", 48))
            x = int(w.get("layout_x", 0))
            _apply(w, x, cursor, ww, hh, design_w)
            cursor = int(w["layout_y"]) + int(w["layout_h"]) + gap


def widgets_inside_bounds(
    widgets: list[dict[str, Any]],
    sx: int,
    sy: int,
    sw: int,
    sh: int,
    *,
    exclude_idx: int | None = None,
    margin: int = 4,
) -> list[int]:
    """中心点落在给定矩形内的控件索引（可排除 section 自身）。"""
    out: list[int] = []
    for i, w in enumerate(widgets):
        if exclude_idx is not None and i == exclude_idx:
            continue
        if str(w.get("type", "")) == "section":
            continue
        x, y, ww, hh = _rect(w)
        cx, cy = x + ww // 2, y + hh // 2
        if sx - margin <= cx <= sx + sw + margin and sy - margin <= cy <= sy + sh + margin:
            out.append(i)
    return out


def widgets_inside_section(
    widgets: list[dict[str, Any]],
    section_idx: int,
    *,
    margin: int = 4,
) -> list[int]:
    """几何上落在分区框内的其它控件索引（中心点判定）。"""
    if section_idx < 0 or section_idx >= len(widgets):
        return []
    sec = widgets[section_idx]
    if str(sec.get("type", "")) != "section":
        return []
    sx, sy, sw, sh = _rect(sec)
    return widgets_inside_bounds(
        widgets, sx, sy, sw, sh, exclude_idx=section_idx, margin=margin
    )


def move_widgets_by(
    widgets: list[dict[str, Any]],
    indices: list[int],
    dx: int,
    dy: int,
    *,
    design_w: int = 720,
) -> None:
    for i in indices:
        if i < 0 or i >= len(widgets):
            continue
        w = widgets[i]
        _apply(
            w,
            int(w.get("layout_x", 0)) + dx,
            int(w.get("layout_y", 0)) + dy,
            int(w.get("layout_w", 120)),
            int(w.get("layout_h", 48)),
            design_w,
        )


def copy_widget_style(src: dict[str, Any]) -> dict[str, Any]:
    return {k: src[k] for k in STYLE_KEYS if k in src}


def paste_widget_style(dst: dict[str, Any], style: dict[str, Any]) -> None:
    for k, v in style.items():
        if k in STYLE_KEYS:
            dst[k] = v


def _apply(
    w: dict[str, Any],
    x: int,
    y: int,
    ww: int,
    hh: int,
    design_w: int,
) -> None:
    wtype = str(w.get("type", "input"))
    nx, ny, nww, nhh = clamp_widget_rect(design_w, wtype, x, y, ww, hh)
    w["layout_x"] = nx
    w["layout_y"] = ny
    w["layout_w"] = nww
    w["layout_h"] = nhh
