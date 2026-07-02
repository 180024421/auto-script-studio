"""Studio 页面统一布局：提示条 + 左操作 / 中主区 / 右辅助。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QSplitter, QVBoxLayout, QWidget


def page_root(widget: QWidget) -> QVBoxLayout:
    lay = QVBoxLayout(widget)
    lay.setSpacing(12)
    lay.setContentsMargins(0, 0, 0, 0)
    return lay


def hint_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("HintLabel")
    lbl.setWordWrap(True)
    return lbl


def section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SectionTitle")
    return lbl


def card_frame(title: str | None = None, *, compact: bool = False) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    if compact:
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
    else:
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
    if title:
        lay.addWidget(section_title(title))
    return frame, lay


def main_column(*, compact: bool = False) -> tuple[QFrame, QVBoxLayout]:
    frame, lay = card_frame(compact=compact)
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return frame, lay


def side_column(min_width: int = 220, max_width: int | None = 300) -> tuple[QFrame, QVBoxLayout]:
    frame, lay = card_frame()
    frame.setMinimumWidth(min_width)
    if max_width is not None:
        frame.setMaximumWidth(max_width)
    return frame, lay


def three_columns(
    left: QWidget,
    center: QWidget,
    right: QWidget | None = None,
    *,
    center_stretch: int = 1,
) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    row.addWidget(left, 0)
    row.addWidget(center, center_stretch)
    if right is not None:
        row.addWidget(right, 0)
    return row


def three_column_splitter(
    left: QWidget,
    center: QWidget,
    right: QWidget,
    *,
    sizes: tuple[int, int, int] = (260, 720, 360),
) -> QSplitter:
    """可拖拽调整宽度的三栏布局（左/右固定倾向，中间自适应）。"""
    split = QSplitter(Qt.Orientation.Horizontal)
    split.setObjectName("PageSplitter")
    split.setChildrenCollapsible(False)
    for w, min_w in ((left, 260), (center, 420), (right, 360)):
        w.setMinimumWidth(min_w)
        split.addWidget(w)
    split.setStretchFactor(0, 0)
    split.setStretchFactor(1, 1)
    split.setStretchFactor(2, 0)
    split.setSizes(list(sizes))
    return split


def tool_button_row(
    parent_layout: QVBoxLayout,
    buttons: list[tuple[str, object, str]],
    *,
    columns: int = 2,
    min_height: int = 34,
) -> None:
    """buttons: [(text, slot, role), ...]"""
    from studio.ui.app_theme import set_button_role
    from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

    wrap = QWidget()
    grid = QGridLayout(wrap)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)
    for i, (text, slot, role) in enumerate(buttons):
        b = QPushButton(text)
        set_button_role(b, role)
        b.clicked.connect(slot)
        b.setMinimumHeight(min_height)
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(b, i // columns, i % columns)
    for c in range(columns):
        grid.setColumnStretch(c, 1)
    parent_layout.addWidget(wrap)
