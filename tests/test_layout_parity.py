"""snap_design / panel_geometry / pack layout 校验测试。"""

from __future__ import annotations

from studio.services.layout_clone import clone_layout
from studio.services.layout_defaults import DEFAULT_LAYOUT
from studio.services.panel_geometry import compute_free_panel_design_height
from studio.services.panel_lua_snippets import lua_all_values_for_layout, list_value_widgets
from studio.services.snap_design import SNAP_GRID, snap_design


def test_snap_design_rounds_to_grid():
    assert snap_design(0) == 0
    assert snap_design(7) == 8
    assert snap_design(8) == 8
    assert snap_design(11) == 8
    assert snap_design(12) == 16
    assert snap_design(16) == 16


def test_free_panel_design_height_includes_chrome():
    layout = clone_layout(DEFAULT_LAYOUT)
    h = compute_free_panel_design_height(layout)
    assert h >= 48 + 44


def test_lua_all_values_for_screen_filters():
    layout = clone_layout(DEFAULT_LAYOUT)
    all_w = list_value_widgets(layout)
    screen_w = list_value_widgets(layout, screen_index=0)
    assert len(screen_w) <= len(all_w)
    code = lua_all_values_for_layout(layout, screen_index=0)
    assert "panel.get" in code
    for w in screen_w[:2]:
        assert w["id"] in code
