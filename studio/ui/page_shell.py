"""Studio 页面统一布局：提示条 + 可拖拽分栏（自适应窗口大小）。"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)


class _LeftElideComboDelegate(QStyledItemDelegate):
    """下拉项左对齐，过长文本右侧省略。"""

    def initStyleOption(self, option, index) -> None:  # noqa: N802
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def configure_elide_combo(combo: QComboBox) -> None:
    combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(10)
    view = combo.view()
    view.setTextElideMode(Qt.TextElideMode.ElideRight)
    combo.setItemDelegate(_LeftElideComboDelegate(combo))


class RecentProjectDelegate(QStyledItemDelegate):
    """最近工程列表项：首行工程名（加粗），次行弱化的所在目录。"""

    def paint(self, painter, option, index) -> None:
        from pathlib import Path

        from PySide6.QtGui import QColor, QFont, QPainter

        from studio.ui.app_theme import COLORS

        name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        raw = index.data(Qt.ItemDataRole.UserRole)
        sub = str(Path(str(raw)).parent) if raw else ""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(COLORS["primary_bg"]))
            painter.drawRoundedRect(option.rect.adjusted(4, 2, -4, -2), 6, 6)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QColor(COLORS["surface3"]))
            painter.drawRoundedRect(option.rect.adjusted(4, 2, -4, -2), 6, 6)
        rect = option.rect.adjusted(14, 7, -14, -7)
        name_font = QFont(option.font)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor(COLORS["text"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, name)
        sub_font = QFont(option.font)
        sub_font.setPointSize(max(8, option.font.pointSize() - 1))
        sub_y = rect.top() + painter.fontMetrics().height() + 2
        painter.setFont(sub_font)
        painter.setPen(QColor(COLORS["text_muted"]))
        elided = painter.fontMetrics().elidedText(
            sub, Qt.TextElideMode.ElideMiddle, rect.width()
        )
        painter.drawText(
            QRect(rect.left(), sub_y, rect.width(), rect.bottom() - sub_y + 1),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            elided,
        )
        painter.restore()

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(200, 56)


def page_root(widget: QWidget) -> QVBoxLayout:
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    lay = QVBoxLayout(widget)
    lay.setSpacing(8)
    lay.setContentsMargins(0, 4, 0, 0)
    return lay


def hint_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("HintLabel")
    lbl.setWordWrap(True)
    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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


def side_column(
    min_width: int = 220,
    max_width: int | None = None,
    *,
    flexible: bool = True,
) -> tuple[QFrame, QVBoxLayout]:
    """侧栏卡片：仅设最小宽，默认不设最大宽以便随分栏拉伸。"""
    frame, lay = card_frame()
    frame.setMinimumWidth(min_width)
    if max_width is not None:
        frame.setMaximumWidth(max_width)
    if flexible:
        frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    return frame, lay


def scroll_side_panel(
    inner: QWidget,
    *,
    min_width: int = 240,
) -> QScrollArea:
    """侧栏内容包一层纵向滚动，小窗口时避免底部裁切。"""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(inner)
    scroll.setMinimumWidth(min_width)
    scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    return scroll


def _configure_splitter(
    split: QSplitter,
    widgets: list[QWidget],
    *,
    mins: list[int] | None = None,
    stretches: list[int] | None = None,
    sizes: list[int] | None = None,
) -> QSplitter:
    split.setObjectName("PageSplitter")
    split.setChildrenCollapsible(False)
    split.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    for i, w in enumerate(widgets):
        if mins and i < len(mins):
            w.setMinimumWidth(mins[i])
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        split.addWidget(w)
    n = len(widgets)
    if stretches:
        for i, s in enumerate(stretches[:n]):
            split.setStretchFactor(i, s)
    if sizes:
        split.setSizes(sizes)
    return split


def two_column_splitter(
    left: QWidget,
    center: QWidget,
    *,
    sizes: tuple[int, int] = (300, 700),
    left_min: int = 240,
    center_min: int = 360,
    stretches: tuple[int, int] = (1, 3),
) -> QSplitter:
    """左操作 / 右主区，随窗口等比伸缩。"""
    return _configure_splitter(
        QSplitter(Qt.Orientation.Horizontal),
        [left, center],
        mins=[left_min, center_min],
        stretches=list(stretches),
        sizes=list(sizes),
    )


def three_column_splitter(
    left: QWidget,
    center: QWidget,
    right: QWidget,
    *,
    sizes: tuple[int, int, int] = (280, 680, 380),
    mins: tuple[int, int, int] = (240, 400, 320),
    stretches: tuple[int, int, int] = (1, 3, 1),
) -> QSplitter:
    """左 / 中 / 右三栏，中间主区优先获得更多空间。"""
    return _configure_splitter(
        QSplitter(Qt.Orientation.Horizontal),
        [left, center, right],
        mins=list(mins),
        stretches=list(stretches),
        sizes=list(sizes),
    )


def three_columns(
    left: QWidget,
    center: QWidget,
    right: QWidget | None = None,
    *,
    center_stretch: int = 1,
) -> QHBoxLayout:
    """兼容旧代码；新页面请用 *column_splitter。"""
    row = QHBoxLayout()
    row.setSpacing(12)
    left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    row.addWidget(left, 0)
    row.addWidget(center, center_stretch)
    if right is not None:
        right.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        row.addWidget(right, 0)
    return row


def tool_button_row(
    parent_layout: QVBoxLayout,
    buttons: list[tuple[str, object, str]],
    *,
    columns: int = 2,
    min_height: int = 34,
) -> None:
    """buttons: [(text, slot, role), ...]"""
    from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

    from studio.ui.app_theme import set_button_role

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
