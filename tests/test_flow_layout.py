"""流式布局与主题 / 向导扩展测试。"""

from __future__ import annotations

from studio.services.flow_layout import (
    align_left,
    pair_two_columns,
    place_widget_in_flow,
    reflow_vertical,
    unify_width,
)
from studio.services.layout_validate import validate_layout
from studio.services.layout_wizard_templates import build_wizard_layout
from studio.services.panel_theme import panel_theme_colors


def test_place_and_reflow():
    widgets: list[dict] = []
    a = {"id": "a", "type": "input", "label": "A", "layout_w": 100, "layout_h": 52}
    place_widget_in_flow(widgets, a)
    widgets.append(a)
    b = {"id": "b", "type": "switch", "label": "B", "layout_w": 100, "layout_h": 48}
    place_widget_in_flow(widgets, b)
    widgets.append(b)
    assert a["layout_y"] < b["layout_y"]
    assert a["layout_x"] == 24
    reflow_vertical(widgets)
    assert a["layout_w"] == 672
    assert b["layout_w"] == 672


def test_pair_two_columns():
    widgets = [
        {"id": "a", "type": "select", "layout_x": 24, "layout_y": 40, "layout_w": 672, "layout_h": 64},
        {"id": "b", "type": "select", "layout_x": 24, "layout_y": 120, "layout_w": 672, "layout_h": 64},
    ]
    pair_two_columns(widgets, [0, 1])
    assert widgets[0]["layout_x"] == 24
    assert widgets[1]["layout_x"] > widgets[0]["layout_x"]
    assert widgets[0]["layout_y"] == widgets[1]["layout_y"]


def test_align_and_unify():
    widgets = [
        {"id": "a", "type": "input", "layout_x": 80, "layout_y": 40, "layout_w": 200, "layout_h": 52},
    ]
    align_left(widgets)
    assert widgets[0]["layout_x"] == 24
    unify_width(widgets)
    assert widgets[0]["layout_w"] == 672


def test_wizard_remind_and_dual():
    remind = build_wizard_layout("remind")
    assert remind["panel"]["theme"] == "green"
    ids = [w["id"] for sc in remind["screens"] for w in sc["widgets"]]
    assert "remind_on" in ids and "work_hours" in ids and "sec_remind" in ids
    assert validate_layout(remind) == []

    dual = build_wizard_layout("dual")
    assert dual["panel"]["theme"] == "gray"
    assert validate_layout(dual) == []


def test_wizard_full_has_section():
    layout = build_wizard_layout("full")
    types = [w["type"] for sc in layout["screens"] for w in sc["widgets"]]
    assert "section" in types
    assert validate_layout(layout) == []


def test_theme_presets():
    for key in ("light", "green", "gray", "dark"):
        c = panel_theme_colors(key)
        assert c.accent.startswith("#")
        assert c.section_bg.startswith("#")
