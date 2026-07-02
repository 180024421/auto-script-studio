"""全局标签页（界面）管理 — 水平标签概念，左侧编辑。"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from studio.ui.app_theme import set_button_role
from studio.ui.page_shell import section_title


class _ScreenTabButton(QPushButton):
    def __init__(self, editor: "ScreenTabsEditor", index: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._editor = editor
        self._index = index

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._editor._rename_screen(self._index)
        event.accept()


class ScreenTabsEditor(QWidget):
    """管理 layout.screens[]：添加 / 重命名 / 删除界面。"""

    def __init__(self, on_changed: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self._on_changed = on_changed
        self._screens: list[dict[str, Any]] = []
        self._active = 0
        self._tab_buttons: list[QPushButton] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        root.addWidget(section_title("全局标签页"))
        hint = QLabel("单击切换界面，双击标签可重命名")
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self._tabs_row = QHBoxLayout()
        self._tabs_row.setSpacing(4)
        root.addLayout(self._tabs_row)
        ops = QHBoxLayout()
        for text, slot, role in [
            ("添加界面", self._add_screen, "accent"),
            ("重命名", self._rename_active_screen, "ghost"),
            ("删除", self._remove_screen, "danger"),
        ]:
            b = QPushButton(text)
            set_button_role(b, role)
            b.setMinimumHeight(30)
            b.clicked.connect(slot)
            ops.addWidget(b)
        root.addLayout(ops)

    def set_screens(self, screens: list[dict[str, Any]], active: int = 0) -> None:
        # 直接引用 layout.screens[]，避免浅拷贝导致 widgets 列表与布局脱节
        self._screens = screens if screens is not None else []
        if not self._screens:
            self._screens.append({"title": "界面1", "widgets": []})
        self._active = max(0, min(len(self._screens) - 1, active))
        self._rebuild_tabs()

    def get_screens(self) -> list[dict[str, Any]]:
        return self._screens

    def active_index(self) -> int:
        return self._active

    def set_active_index(self, idx: int) -> None:
        if 0 <= idx < len(self._screens):
            self._active = idx
            self._rebuild_tabs()

    def _clear_tabs_row(self) -> None:
        while self._tabs_row.count():
            item = self._tabs_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._tab_buttons = []

    def _rebuild_tabs(self) -> None:
        self._clear_tabs_row()
        for i, sc in enumerate(self._screens):
            b = _ScreenTabButton(self, i, sc.get("title", f"界面{i + 1}"))
            b.setCheckable(True)
            b.blockSignals(True)
            b.setChecked(i == self._active)
            b.blockSignals(False)
            b.setMinimumHeight(32)
            if i == self._active:
                set_button_role(b, "primary")
            else:
                set_button_role(b, "ghost")
            b.clicked.connect(lambda _c=False, idx=i: self._select_tab(idx))
            self._tabs_row.addWidget(b)
            self._tab_buttons.append(b)
        self._tabs_row.addStretch()

    def _select_tab(self, idx: int) -> None:
        if idx == self._active:
            return
        self._active = idx
        self._rebuild_tabs()
        self._on_changed()

    def _add_screen(self) -> None:
        n = len(self._screens) + 1
        self._screens.append({"title": f"界面{n}", "widgets": []})
        self._active = len(self._screens) - 1
        self._rebuild_tabs()
        self._on_changed()

    def _remove_screen(self) -> None:
        if len(self._screens) <= 1:
            return
        self._screens.pop(self._active)
        self._active = min(self._active, len(self._screens) - 1)
        self._rebuild_tabs()
        self._on_changed()

    def _rename_active_screen(self) -> None:
        self._rename_screen(self._active)

    def _rename_screen(self, idx: int | None = None) -> None:
        if idx is None:
            idx = self._active
        if idx < 0 or idx >= len(self._screens):
            return
        self._active = idx
        title, ok = QInputDialog.getText(
            self.window(),
            "重命名界面",
            "界面标题:",
            text=self._screens[idx].get("title", ""),
        )
        if ok and title.strip():
            self._screens[idx]["title"] = title.strip()
            self._rebuild_tabs()
            self._on_changed()
