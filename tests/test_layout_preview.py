"""layout_preview 单元测试。"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from studio.services.layout_defaults import DEFAULT_LAYOUT
from studio.services.layout_preview import dp_to_px, paint_layout_overlay


def test_dp_to_px():
    assert dp_to_px(180, 1080) == 540


def test_paint_overlay_no_crash():
    from PySide6.QtGui import QImage, QPainter

    img = QImage(720, 1280, QImage.Format_RGB32)
    img.fill(0)
    painter = QPainter(img)
    paint_layout_overlay(painter, DEFAULT_LAYOUT, 720, 1280, scale=1.0)
    painter.end()
