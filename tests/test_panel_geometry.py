"""面板几何（设备仿真 + 抓抓 overlay）。"""

from __future__ import annotations

from pathlib import Path

from studio.services.layout_defaults import load_layout
from studio.services.panel_geometry import (
    compute_device_screen_px,
    compute_host_panel_overlay_rect,
    dp_to_preview_px,
)


def test_dp_to_preview_px():
    assert dp_to_preview_px(360, 720) == 720
    assert dp_to_preview_px(12, 720) == 24


def test_device_screen_px_landscape():
    w, h = compute_device_screen_px(720, 1280, 0.5, landscape=False)
    assert w == 360 and h == 640
    w2, h2 = compute_device_screen_px(720, 1280, 0.5, landscape=True)
    assert w2 == 640 and h2 == 360


def test_host_panel_overlay_left_center():
    root = Path(__file__).resolve().parents[1]
    layout = load_layout(root / "examples" / "demo-game")
    rect = compute_host_panel_overlay_rect(layout, 720, 1280)
    assert rect.w > 0 and rect.h > 0
    assert rect.x >= 12
    assert 0 <= rect.y < 1280
    assert rect.inner_scale > 0
