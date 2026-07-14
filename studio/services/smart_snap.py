"""自由布局拖动时相对其它控件的智能吸附。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SnapResult:
    x: int
    y: int
    guides: list[tuple[str, int]]  # ("v"|"h", design_coord)


def smart_snap_rect(
    x: int,
    y: int,
    w: int,
    h: int,
    others: list[tuple[int, int, int, int]],
    *,
    threshold: int = 8,
    design_w: int = 720,
) -> SnapResult:
    """将 (x,y,w,h) 相对 others 的边/中心吸附；others 为 (ox,oy,ow,oh)。"""
    anchors_x = {0, design_w // 2, design_w}
    anchors_y = {0}
    for ox, oy, ow, oh in others:
        anchors_x.update({ox, ox + ow // 2, ox + ow})
        anchors_y.update({oy, oy + oh // 2, oy + oh})

    cx = x + w // 2
    rx = x + w
    cy = y + h // 2
    by = y + h

    best_dx = 0
    best_abs = threshold + 1
    v_guide: int | None = None
    for ax in anchors_x:
        for cand, delta in ((x, ax - x), (cx, ax - cx), (rx, ax - rx)):
            ad = abs(delta)
            if ad < best_abs:
                best_abs = ad
                best_dx = delta
                v_guide = ax

    best_dy = 0
    best_abs_y = threshold + 1
    h_guide: int | None = None
    for ay in anchors_y:
        for cand, delta in ((y, ay - y), (cy, ay - cy), (by, ay - by)):
            ad = abs(delta)
            if ad < best_abs_y:
                best_abs_y = ad
                best_dy = delta
                h_guide = ay

    nx, ny = x, y
    guides: list[tuple[str, int]] = []
    if best_abs <= threshold:
        nx = x + best_dx
        if v_guide is not None:
            guides.append(("v", v_guide))
    if best_abs_y <= threshold:
        ny = y + best_dy
        if h_guide is not None:
            guides.append(("h", h_guide))
    return SnapResult(x=nx, y=ny, guides=guides)


def other_rects_excluding(
    widgets: list[dict[str, Any]],
    exclude_index: int,
) -> list[tuple[int, int, int, int]]:
    out: list[tuple[int, int, int, int]] = []
    for i, w in enumerate(widgets):
        if i == exclude_index:
            continue
        out.append(
            (
                int(w.get("layout_x", 0)),
                int(w.get("layout_y", 0)),
                int(w.get("layout_w", 120)),
                int(w.get("layout_h", 48)),
            )
        )
    return out
