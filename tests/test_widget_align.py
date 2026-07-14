"""控件对齐 / 分布 / 智能吸附。"""

from __future__ import annotations

from studio.services.smart_snap import smart_snap_rect
from studio.services.widget_align import (
    align_widgets,
    copy_widget_style,
    distribute_widgets,
    equalize_size,
    match_spacing,
    move_widgets_by,
    paste_widget_style,
    widgets_inside_bounds,
)


def _w(x, y, ww=100, hh=40, **extra):
    return {"type": "input", "layout_x": x, "layout_y": y, "layout_w": ww, "layout_h": hh, **extra}


def test_align_left_and_right():
    ws = [_w(40, 10), _w(120, 80), _w(200, 160)]
    align_widgets(ws, [0, 1, 2], "left", design_w=720)
    assert ws[0]["layout_x"] == ws[1]["layout_x"] == ws[2]["layout_x"] == 40
    align_widgets(ws, [0, 1, 2], "right", design_w=720)
    rights = [w["layout_x"] + w["layout_w"] for w in ws]
    assert len(set(rights)) == 1


def test_distribute_horizontal():
    ws = [_w(24, 10, 80), _w(200, 10, 80), _w(500, 10, 80)]
    distribute_widgets(ws, [0, 1, 2], "horizontal", design_w=720)
    gaps = []
    ordered = sorted(ws, key=lambda w: w["layout_x"])
    for a, b in zip(ordered, ordered[1:]):
        gaps.append(b["layout_x"] - (a["layout_x"] + a["layout_w"]))
    assert abs(gaps[0] - gaps[1]) <= 1


def test_smart_snap_near_edge():
    r = smart_snap_rect(22, 100, 100, 40, [(24, 200, 200, 40)], threshold=8, design_w=720)
    assert r.x == 24
    assert any(g[0] == "v" for g in r.guides)


def test_copy_paste_style():
    src = _w(0, 0, color="#123456", text_style="title", layout_w=200)
    style = copy_widget_style(src)
    dst = _w(10, 10)
    paste_widget_style(dst, style)
    assert dst["color"] == "#123456"
    assert dst["text_style"] == "title"
    assert dst["layout_w"] == 200


def test_equalize_height_and_match_spacing():
    ws = [_w(0, 0, 100, 56), _w(0, 80, 160, 72), _w(0, 200, 80, 64)]
    equalize_size(ws, [0, 1, 2], dimension="height", design_w=720)
    assert ws[0]["layout_h"] == ws[1]["layout_h"] == ws[2]["layout_h"] == 56
    ws2 = [_w(0, 0, 80, 56), _w(100, 0, 80, 56), _w(300, 0, 80, 56)]
    match_spacing(ws2, [0, 1, 2], axis="horizontal", design_w=720)
    # gap0-1 = 20; widget2 should start at 100+80+20=200
    assert ws2[2]["layout_x"] == 200


def test_section_bounds_and_move():
    ws = [
        {"type": "section", "layout_x": 0, "layout_y": 0, "layout_w": 200, "layout_h": 200},
        _w(20, 30),
        _w(400, 30),
    ]
    inside = widgets_inside_bounds(ws, 0, 0, 200, 200, exclude_idx=0)
    assert inside == [1]
    move_widgets_by(ws, inside, 10, 5, design_w=720)
    assert ws[1]["layout_x"] == 30
    assert ws[1]["layout_y"] == 35
