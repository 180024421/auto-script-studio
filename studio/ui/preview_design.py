"""预览区布局设计：拖动排序、拖拽调整占列宽。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class SelectFrame(QFrame):
    """只读预览：点击选中控件，无拖动排序。"""

    selected = Signal(tuple)

    def __init__(
        self,
        path: tuple[int, ...],
        inner: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._selected = False
        self.setObjectName("DesignFrame")
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(0)
        root.addWidget(inner)
        self._update_style()

    def widget_path(self) -> tuple[int, ...]:
        return self._path

    def set_selected(self, on: bool) -> None:
        self._selected = on
        self._update_style()

    def _update_style(self) -> None:
        border = "#2563EB" if self._selected else "transparent"
        width = 2 if self._selected else 0
        self.setStyleSheet(
            f"QFrame#DesignFrame {{ border: {width}px solid {border}; border-radius: 6px; }}"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._path)
            event.accept()
            return
        super().mousePressEvent(event)


class DesignFrame(QFrame):
    """包裹预览控件，设计模式下可拖动排序与调整列宽。"""

    selected = Signal(tuple)
    reorder_request = Signal(tuple, int, int)  # container_prefix, from_idx, to_idx
    span_changed = Signal(tuple, int)  # widget_path, span

    HANDLE_H = 20
    RESIZE_W = 10

    def __init__(
        self,
        path: tuple[int, ...],
        container: tuple[int, ...],
        span: int,
        cols: int,
        inner: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._container = container
        self._index = path[-1]
        self._span = max(1, min(cols, span))
        self._cols = cols
        self._selected = False
        self._mode = ""
        self._press_pos = QPoint()
        self._start_span = self._span

        self.setObjectName("DesignFrame")
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        label = "/".join(str(p) for p in path) if path else "?"
        self._handle = QLabel(f"⋮⋮  {label}  ·  拖动排序 / 右缘拉宽")
        self._handle.setObjectName("DesignHandle")
        self._handle.setFixedHeight(self.HANDLE_H)
        self._handle.setCursor(QCursor(Qt.SizeAllCursor))
        self._handle.setAlignment(Qt.AlignCenter)
        root.addWidget(self._handle)

        inner_host = QWidget()
        inner_lay = QVBoxLayout(inner_host)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.addWidget(inner)
        root.addWidget(inner_host, 1)

        self._resize = QLabel("⇔")
        self._resize.setObjectName("DesignResizeGrip")
        self._resize.setFixedWidth(self.RESIZE_W)
        self._resize.setAlignment(Qt.AlignCenter)
        self._resize.setCursor(QCursor(Qt.SizeHorCursor))
        self._resize.setParent(self)
        self._resize.raise_()
        self._update_style()

    def widget_path(self) -> tuple[int, ...]:
        return self._path

    def container_prefix(self) -> tuple[int, ...]:
        return self._container

    def set_selected(self, on: bool) -> None:
        self._selected = on
        self._update_style()

    def set_path(self, path: tuple[int, ...]) -> None:
        self._path = path
        self._index = path[-1]
        label = "/".join(str(p) for p in path)
        self._handle.setText(f"⋮⋮  {label}  ·  拖动排序 / 右缘拉宽")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._resize.setFixedHeight(max(40, self.height() - self._handle.height() - 12))
        self._resize.move(self.width() - self.RESIZE_W - 4, self._handle.height() + 6)

    def _update_style(self) -> None:
        border = "#2563EB" if self._selected else "transparent"
        width = 2 if self._selected else 0
        bg = "transparent"
        self.setStyleSheet(
            f"QFrame#DesignFrame {{ border: {width}px dashed {border}; border-radius: 8px; background: {bg}; }}"
            "QLabel#DesignHandle { background: #E2E8F0; color: #475569; border-radius: 4px; font-size: 11px; }"
            "QLabel#DesignResizeGrip { background: #BFDBFE; color: #1D4ED8; border-radius: 4px; font-size: 10px; }"
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        self.selected.emit(self._path)
        local = event.position().toPoint()
        if local.x() >= self.width() - self.RESIZE_W - 6:
            self._mode = "resize"
            self._press_pos = local
            self._start_span = self._span
        elif local.y() <= self.HANDLE_H + 8:
            self._mode = "drag"
        else:
            self._mode = ""
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._mode == "resize" and event.buttons() & Qt.LeftButton:
            cell = max(48, self.width() // max(1, self._span))
            delta = event.position().toPoint().x() - self._press_pos.x()
            new_span = self._start_span + round(delta / cell)
            new_span = max(1, min(self._cols, new_span))
            if new_span != self._span:
                self._span = new_span
                self.span_changed.emit(self._path, new_span)
            return
        if self._mode == "drag" and event.buttons() & Qt.LeftButton:
            self._handle.setText("⋮⋮  松开以插入…")
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._mode == "drag" and event.button() == Qt.LeftButton:
            label = "/".join(str(p) for p in self._path)
            self._handle.setText(f"⋮⋮  {label}  ·  拖动排序 / 右缘拉宽")
            self.setCursor(QCursor(Qt.ArrowCursor))
            target = self._find_drop_index(event.globalPosition().toPoint())
            if target is not None and target != self._index:
                self.reorder_request.emit(self._container, self._index, target)
        self._mode = ""
        super().mouseReleaseEvent(event)

    def _find_drop_index(self, global_pos: QPoint) -> int | None:
        host = self.parentWidget()
        if host is None:
            return None
        siblings = [
            f
            for f in host.children()
            if isinstance(f, DesignFrame) and f.container_prefix() == self._container
        ]
        ordered = sorted(siblings, key=lambda f: f.geometry().center().y())
        for fr in ordered:
            bottom = fr.mapToGlobal(QPoint(0, fr.height())).y()
            if global_pos.y() < bottom:
                return fr._index
        return ordered[-1]._index if ordered else self._index


class PanelWidthHandle(QFrame):
    """面板右缘拖拽，调整 width_dp。"""

    width_dp_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._width_dp = 220
        self._press_x = 0
        self._start_dp = 220
        self.setFixedWidth(8)
        self.setCursor(QCursor(Qt.SizeHorCursor))
        self.setStyleSheet("background: #93C5FD; border-radius: 4px;")

    def set_width_dp(self, dp: int) -> None:
        self._width_dp = dp

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._press_x = int(event.globalPosition().x())
            self._start_dp = self._width_dp
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.buttons() & Qt.LeftButton:
            delta = int(event.globalPosition().x()) - self._press_x
            new_dp = max(160, min(360, self._start_dp + delta))
            if new_dp != self._width_dp:
                self._width_dp = new_dp
                self.width_dp_changed.emit(new_dp)
        super().mouseMoveEvent(event)
