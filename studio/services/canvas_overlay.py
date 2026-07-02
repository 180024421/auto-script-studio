"""在截图上绘制 OCR 命中框等辅助标记。"""

from __future__ import annotations

from typing import Any, Sequence

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen


def paint_ocr_hits(
    painter: QPainter,
    hits: Sequence[Any],
    scale: float = 1.0,
    limit: int = 30,
) -> None:
    pen = QPen(QColor(13, 148, 136, 220), max(1, int(2 * scale)))
    painter.setPen(pen)
    painter.setBrush(QColor(13, 148, 136, 35))
    font = QFont()
    font.setPointSizeF(max(6.0, 8 * scale))
    painter.setFont(font)
    for h in list(hits)[:limit]:
        cx = int(getattr(h, "center_x", h.get("center_x", 0)) * scale)
        cy = int(getattr(h, "center_y", h.get("center_y", 0)) * scale)
        w = int(getattr(h, "width", h.get("width", 40)) * scale)
        hgt = int(getattr(h, "height", h.get("height", 20)) * scale)
        x = cx - w // 2
        y = cy - hgt // 2
        painter.drawRect(QRectF(x, y, w, hgt))
        text = str(getattr(h, "text", h.get("text", "")))
        if text:
            painter.setPen(QColor(15, 118, 110))
            painter.drawText(x, max(0, y - 2), text[:12])
            painter.setPen(pen)


def paint_crosshair(painter: QPainter, x: int, y: int, scale: float = 1.0, color: str = "#2563EB") -> None:
    if x <= 0 and y <= 0:
        return
    sx = int(x * scale)
    sy = int(y * scale)
    r = max(8, int(12 * scale))
    pen = QPen(QColor(color), max(1, int(2 * scale)))
    painter.setPen(pen)
    painter.drawLine(sx - r, sy, sx + r, sy)
    painter.drawLine(sx, sy - r, sx, sy + r)
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QRectF(sx - 4 * scale, sy - 4 * scale, 8 * scale, 8 * scale))
