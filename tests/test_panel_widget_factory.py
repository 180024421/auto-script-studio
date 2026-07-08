"""panel_widget_factory 缩放与行高逻辑。"""

from __future__ import annotations

from studio.ui.panel_widget_factory import (
    _default_row_h,
    _row_height,
    _scaled_px,
    _switch_style,
)


def test_scaled_px_floor_at_low_scale():
    assert _scaled_px(32, 0.25, floor=24) == 24
    assert _scaled_px(32, 0.9, floor=24) >= 24


def test_switch_style_scales_indicator():
    small = _switch_style(0.5)
    large = _switch_style(1.0)
    assert "width: 28px" in small or "width: 22px" in small
    assert "width: 44px" in large
    assert "#PanelSwitch::indicator" in large


def test_row_height_floor_at_low_scale():
    assert _row_height(0.35, _FakeControl(0), None) >= 24


def test_row_height_respects_container():
    assert _row_height(0.45, _FakeControl(40), 24) == 24


def test_default_row_h_clamped_by_container():
    assert _default_row_h(0.9, 20) == 20
    assert _default_row_h(0.9, None) >= 24


class _FakeHint:
    def __init__(self, height: int) -> None:
        self._height = height

    def height(self) -> int:
        return self._height


class _FakeControl:
    def __init__(self, hint_h: int) -> None:
        self._hint_h = hint_h

    def sizeHint(self) -> _FakeHint:
        return _FakeHint(self._hint_h)
