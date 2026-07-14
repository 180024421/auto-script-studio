"""控件内容区相对设计框的缩放系数。"""

from __future__ import annotations


def effective_content_scale(
    canvas_scale: float,
    layout_h_design: int,
    pixel_h: int,
    *,
    min_factor: float = 0.35,
    max_factor: float = 2.5,
) -> float:
    """画布 scale × 当前像素高度 / 设计高度对应像素，使控件内容随框体缩放。"""
    if layout_h_design < 44:
        min_factor = max(min_factor, 0.52)
    if pixel_h < 28:
        min_factor = max(min_factor, 0.58)
    ref_px = max(1.0, float(layout_h_design) * max(0.01, canvas_scale))
    factor = max(min_factor, min(max_factor, pixel_h / ref_px))
    return max(0.01, canvas_scale * factor)


def scale_layout_widgets_for_design(
    widgets: list[dict],
    *,
    sx: float,
    sy: float,
) -> None:
    from studio.services.snap_design import snap_design

    for w in widgets:
        if "layout_x" in w or "layout_y" in w:
            w["layout_x"] = snap_design(int(w.get("layout_x", 0) * sx))
            w["layout_y"] = snap_design(int(w.get("layout_y", 0) * sy))
            w["layout_w"] = snap_design(max(24, int(w.get("layout_w", 48) * sx)))
            w["layout_h"] = snap_design(max(16, int(w.get("layout_h", 28) * sy)))
