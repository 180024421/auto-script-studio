"""PhoneCanvasWidget 预览缩放逻辑。"""

from __future__ import annotations

from studio.ui.phone_canvas_widget import (
    DEFAULT_PHONE_SCREEN_PX,
    compute_preview_scale,
)


def test_editor_target_screen_width():
    scale = compute_preview_scale(
        design_w=720,
        design_h=1280,
        viewport_w=800,
        viewport_h=900,
        target_screen_px=DEFAULT_PHONE_SCREEN_PX,
        fit_viewport=False,
        min_scale=0.35,
    )
    assert abs(scale - DEFAULT_PHONE_SCREEN_PX / 720) < 0.01


def test_script_fit_viewport_proportional():
    scale = compute_preview_scale(
        design_w=720,
        design_h=1280,
        viewport_w=400,
        viewport_h=420,
        target_screen_px=None,
        fit_viewport=True,
        min_scale=0.15,
        hint_reserve=0,
    )
    scale_w = (400 - 48 - 20) / 720
    scale_h = (420 - 20) / 1280
    assert abs(scale - max(0.15, min(scale_w, scale_h))) < 0.01


def test_target_width_capped_by_viewport():
    scale = compute_preview_scale(
        design_w=720,
        design_h=1280,
        viewport_w=260,
        viewport_h=900,
        target_screen_px=400,
        fit_viewport=False,
        min_scale=0.15,
    )
    scale_w = (260 - 48 - 20) / 720
    assert scale <= scale_w + 0.001
