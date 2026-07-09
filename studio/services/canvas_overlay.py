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
        cx = int(getattr(h, "center_x", h.get("center_x", 0)))
        cy = int(getattr(h, "center_y", h.get("center_y", 0)))
        w = int(getattr(h, "width", h.get("width", 40)))
        hgt = int(getattr(h, "height", h.get("height", 20)))
        x = getattr(h, "x", h.get("x", cx - w // 2))
        y = getattr(h, "y", h.get("y", cy - hgt // 2))
        painter.drawRect(
            QRectF(int(x * scale), int(y * scale), int(w * scale), int(hgt * scale))
        )
        text = str(getattr(h, "text", h.get("text", "")))
        if text:
            painter.setPen(QColor(15, 118, 110))
            painter.drawText(int(x * scale), max(0, int(y * scale) - 2), text[:16])
            painter.setPen(pen)


def paint_mask_centers(
    painter: QPainter,
    markers: Sequence[Any],
    scale: float = 1.0,
) -> None:
    """seg 掩码质心（绿色十字）。"""
    paint_point_markers(painter, markers, scale=scale, color="#22C55E")


def paint_match_boxes(
    painter: QPainter,
    boxes: Sequence[Any],
    scale: float = 1.0,
) -> None:
    pen = QPen(QColor(249, 115, 22, 230), max(2, int(2 * scale)))
    painter.setPen(pen)
    painter.setBrush(QColor(249, 115, 22, 40))
    font = QFont()
    font.setPointSizeF(max(6.0, 8 * scale))
    painter.setFont(font)
    for box in boxes:
        if isinstance(box, dict):
            x, y, w, h = box["x"], box["y"], box["w"], box["h"]
            label = str(box.get("label", ""))
        else:
            x, y, w, h, *rest = box
            label = str(rest[0]) if rest else ""
        painter.drawRect(QRectF(x * scale, y * scale, w * scale, h * scale))
        if label:
            painter.setPen(QColor(194, 65, 12))
            painter.drawText(int(x * scale), max(0, int(y * scale) - 2), label[:20])
            painter.setPen(pen)


def paint_point_markers(
    painter: QPainter,
    markers: Sequence[Any],
    scale: float = 1.0,
    color: str = "#16A34A",
) -> None:
    pen = QPen(QColor(color), max(2, int(2 * scale)))
    painter.setPen(pen)
    painter.setBrush(QColor(color))
    font = QFont()
    font.setPointSizeF(max(6.0, 8 * scale))
    painter.setFont(font)
    for m in markers:
        if isinstance(m, dict):
            x, y = m["x"], m["y"]
            label = str(m.get("label", ""))
        else:
            x, y, *rest = m
            label = str(rest[0]) if rest else ""
        sx, sy = int(x * scale), int(y * scale)
        r = max(6, int(8 * scale))
        painter.drawLine(sx - r, sy, sx + r, sy)
        painter.drawLine(sx, sy - r, sx, sy + r)
        painter.drawEllipse(QRectF(sx - 3 * scale, sy - 3 * scale, 6 * scale, 6 * scale))
        if label:
            painter.drawText(sx + r + 2, sy + 4, label[:24])


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
