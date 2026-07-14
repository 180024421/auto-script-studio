"""screen_layout 与 layout_validate 单元测试。"""

from __future__ import annotations

import copy
import json

from studio.services.layout_defaults import DEFAULT_LAYOUT, default_widget, migrate_layout
from studio.services.layout_validate import validate_layout
from studio.services.screen_layout import (
    CHROME_PATH_TAG,
    active_screen_index,
    active_screen_widgets,
    ensure_migrated,
    export_screen_dict,
    import_screen_dict,
    migrate_layout as migrate_screens,
    repair_screen_widgets,
    screens,
)


def test_migrate_to_screens():
    raw = {
        "version": 2,
        "panel": {"layout_mode": "free", "display_mode": "minimal"},
        "widgets": [
            {
                "type": "tabs",
                "tabs": [
                    {"title": "页A", "widgets": [{"id": "a", "type": "label", "text": "A"}]},
                    {"title": "页B", "widgets": [{"id": "b", "type": "input", "label": "B"}]},
                ],
            },
            {"id": "start", "type": "start_script", "label": "开始"},
        ],
    }
    layout = migrate_screens(raw)
    assert layout["version"] >= 3
    assert len(screens(layout)) == 2
    assert screens(layout)[0]["title"] == "页A"
    assert layout["widgets"][0]["type"] == "start_script"


def test_export_import_screen():
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    ensure_migrated(layout)
    idx = active_screen_index(layout)
    exported = export_screen_dict(layout, idx)
    assert exported["title"]
    assert isinstance(exported["widgets"], list)

    new_idx = import_screen_dict(layout, exported, replace=False)
    assert new_idx == len(screens(layout)) - 1
    assert screens(layout)[new_idx]["title"] == exported["title"]

    cur = active_screen_index(layout)
    import_screen_dict(layout, {"title": "替换页", "widgets": []}, replace=True)
    assert screens(layout)[cur]["title"] == "替换页"


def test_validate_layout_ok():
    layout = migrate_layout(DEFAULT_LAYOUT)
    assert validate_layout(layout) == []


def test_validate_duplicate_id():
    layout = migrate_layout(DEFAULT_LAYOUT)
    ws = screens(layout)[0]["widgets"]
    if len(ws) < 2:
        ws.append(copy.deepcopy(ws[0]))
    ws[1]["id"] = ws[0]["id"]
    errors = validate_layout(layout)
    assert any("重复" in e for e in errors)


def test_chrome_path_tag():
    assert CHROME_PATH_TAG == -1


def test_normalize_chrome_empty_for_host_form():
    from studio.services.screen_layout import chrome_widgets, normalize_chrome_widgets

    widgets = [
        {"id": "start", "type": "start_script", "label": "开始"},
        {"id": "stop", "type": "stop_script", "label": "停止"},
    ]
    out = normalize_chrome_widgets(widgets, {"display_mode": "form"})
    assert out == []
    layout = migrate_screens(
        {
            "version": 3,
            "panel": {"layout_mode": "free", "display_mode": "host"},
            "screens": [{"title": "A", "widgets": []}],
            "widgets": widgets,
        }
    )
    assert chrome_widgets(layout) == []


def test_normalize_chrome_keeps_stop_in_minimal():
    from studio.services.screen_layout import normalize_chrome_widgets

    widgets = [{"id": "start", "type": "start_script", "label": "开始"}]
    out = normalize_chrome_widgets(widgets, {"display_mode": "minimal"})
    types = [w["type"] for w in out]
    assert "start_script" in types
    assert "stop_script" in types


def test_clamp_widget_rect_horizontal_bounds():
    from studio.services.free_layout import clamp_widget_rect

    x, y, w, h = clamp_widget_rect(720, "input", 800, 50, 200, 48)
    assert x + w <= 720
    assert x >= 0
    assert y == 50

    x2, y2, w2, h2 = clamp_widget_rect(720, "input", 24, -10, 900, 48)
    assert x2 >= 0
    assert y2 == 0
    assert x2 + w2 <= 720


def test_clamp_widget_rect_allows_tall_scroll_layout():
    from studio.services.free_layout import clamp_widget_rect

    _, y, _, h = clamp_widget_rect(720, "input", 24, 2400, 672, 52)
    assert y == 2400
    assert h == 52


def test_repair_off_canvas_widget():
    widgets = [
        {
            "id": "account",
            "type": "input",
            "layout_x": 696,
            "layout_y": 308,
            "layout_w": 48,
            "layout_h": 32,
        }
    ]
    repair_screen_widgets(widgets)
    w = widgets[0]
    assert w["layout_x"] + w["layout_w"] <= 720
    assert w["layout_w"] >= 160
    assert w["layout_h"] >= 48


def test_repair_overlapping_widgets():
    widgets = [
        {"id": "a", "type": "select", "layout_x": 24, "layout_y": 24, "layout_w": 672, "layout_h": 64},
        {"id": "b", "type": "input", "layout_x": 0, "layout_y": 0, "layout_w": 24, "layout_h": 24},
        {"id": "c", "type": "switch", "layout_x": 24, "layout_y": 24, "layout_w": 24, "layout_h": 24},
    ]
    repair_screen_widgets(widgets)
    ys = [w["layout_y"] for w in widgets]
    assert len(set(ys)) == 3
    assert all(w["layout_w"] >= 80 for w in widgets)


def test_repair_vertical_overlap_stack():
    widgets = [
        {"id": "account", "type": "input", "layout_x": 24, "layout_y": 60, "layout_w": 296, "layout_h": 56},
        {"id": "div", "type": "divider", "layout_x": 24, "layout_y": 72, "layout_w": 296, "layout_h": 16},
        {"id": "hint", "type": "text", "text": "提示", "layout_x": 24, "layout_y": 104, "layout_w": 48, "layout_h": 36},
    ]
    repair_screen_widgets(widgets, design_w=320)
    bottoms = [w["layout_y"] + w["layout_h"] for w in widgets]
    for i in range(1, len(widgets)):
        assert widgets[i]["layout_y"] >= bottoms[i - 1] - 2 or widgets[i]["layout_y"] >= widgets[i - 1]["layout_y"] + 8


def test_validate_size_error_detail():
    layout = migrate_layout(copy.deepcopy(DEFAULT_LAYOUT))
    ws = screens(layout)[0]["widgets"]
    ws[0]["layout_w"] = 24
    ws[0]["layout_h"] = 20
    errors = validate_layout(layout)
    assert any("尺寸过小" in e and "至少" in e for e in errors)


def test_is_auto_repairable():
    from studio.services.layout_validate import is_auto_repairable

    assert is_auto_repairable(["控件「a」尺寸过小（当前 24×20，input 至少 160×48）"])
    assert is_auto_repairable(["控件 id 重复：「a」（text 与 select）"])
    assert not is_auto_repairable(["存在未设置 id 的控件（type=input）"])
    assert not is_auto_repairable(
        [
            "控件「a」尺寸过小（当前 24×20，input 至少 160×48）",
            "存在未设置 id 的控件（type=input）",
        ]
    )


def test_dedupe_widget_ids_on_sanitize():
    from studio.services.layout_cleanup import sanitize_free_layout

    layout = migrate_layout(copy.deepcopy(DEFAULT_LAYOUT))
    ws = screens(layout)[0]["widgets"]
    if len(ws) < 2:
        ws.append(copy.deepcopy(ws[0]))
    ws[0]["type"] = "text"
    ws[0]["id"] = "w_0"
    ws[1]["type"] = "select"
    ws[1]["id"] = "w_0"
    assert any("重复" in e for e in validate_layout(layout))
    sanitize_free_layout(layout)
    assert validate_layout(layout) == []
    ids = [w["id"] for w in ws]
    assert len(ids) == len(set(ids))
    assert ids[0] == "w_0"
    assert ids[1] != "w_0"


def test_demo_game_layout_validates():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "examples" / "demo-game" / "ui" / "layout.json"
    layout = migrate_layout(json.loads(path.read_text(encoding="utf-8")))
    assert validate_layout(layout) == []


def test_screen_tabs_shared_widgets_list():
    """模拟 ScreenTabsEditor 共享引用：追加控件不应丢失。"""
    layout = migrate_layout(copy.deepcopy(DEFAULT_LAYOUT))
    ensure_migrated(layout)
    shared = screens(layout)
    editor_screens = shared  # 直接引用，不再浅拷贝

    widgets = active_screen_widgets(layout)
    widgets.append(default_widget("label", len(widgets) + 1))
    assert len(editor_screens[0]["widgets"]) == len(active_screen_widgets(layout))

    # 模拟旧版错误：json 全量覆盖后引用脱节
    layout["screens"] = json.loads(json.dumps(editor_screens))
    widgets.append(default_widget("input", len(active_screen_widgets(layout)) + 1))
    assert len(active_screen_widgets(layout)) >= 3
