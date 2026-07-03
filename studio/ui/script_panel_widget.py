"""脚本页右栏：浮动面板预览 + 选中控件插入 Lua。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from studio.runtime.panel_state import PanelState
from studio.services.free_layout import is_free_mode
from studio.services.layout_defaults import load_layout
from studio.services.panel_lua_snippets import (
    lua_all_values,
    lua_panel_example,
    lua_read_snippet,
    resolve_layout_widget,
    widget_lua_spec,
)
from studio.ui.app_theme import set_button_role
from studio.ui.layout_preview_widget import LayoutPreviewWidget
from studio.ui.page_shell import hint_label, section_title
from studio.ui.phone_canvas_widget import PhoneCanvasWidget

log = logging.getLogger(__name__)


class ScriptPanelWidget(QWidget):
    insert_lua = Signal(str)
    copy_lua = Signal(str)

    def __init__(self, project_dir_getter: Callable[[], Path | None]) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self._layout: Optional[dict[str, Any]] = None
        self._selected_spec: Optional[dict[str, Any]] = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        bar = QHBoxLayout()
        bar.addWidget(section_title("浮动面板预览"))
        self.values_label = QLabel()
        self.values_label.setObjectName("InfoBar")
        self.values_label.setWordWrap(True)
        bar.addWidget(self.values_label, 1)
        example_btn = QPushButton("Lua 示例")
        set_button_role(example_btn, "ghost")
        example_btn.clicked.connect(lambda: self.insert_lua.emit(lua_panel_example()))
        all_btn = QPushButton("全部值")
        set_button_role(all_btn, "ghost")
        all_btn.clicked.connect(lambda: self.insert_lua.emit(lua_all_values()))
        bar.addWidget(example_btn)
        bar.addWidget(all_btn)
        root.addLayout(bar)

        self.preview_stack = QStackedWidget()
        self.preview_free = PhoneCanvasWidget()
        self.preview_free.set_editable(False)
        self.preview_free.set_selectable(True)
        self.preview_free.set_interactive_preview(True)
        self.preview_free.set_compact_preview(False)
        self.preview_free.set_fit_viewport(True)
        self.preview_grid = LayoutPreviewWidget()
        self.preview_grid.set_zoom_auto(True)
        self.preview_grid.set_design_mode(False)
        self.preview_grid.set_selection_mode(True)
        self.preview_stack.addWidget(self.preview_free)
        self.preview_stack.addWidget(self.preview_grid)
        self.preview_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self.preview_stack, 1)

        self.insert_card = QFrame()
        self.insert_card.setObjectName("Card")
        insert_lay = QVBoxLayout(self.insert_card)
        insert_lay.setContentsMargins(10, 8, 10, 8)
        insert_lay.setSpacing(6)

        self.insert_hint = hint_label("在预览中点击表单控件，可在此插入 panel.get 等 Lua")
        insert_lay.addWidget(self.insert_hint)

        self.insert_row = QWidget()
        row_lay = QHBoxLayout(self.insert_row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(8)
        self.selected_meta = QLabel()
        self.selected_meta.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.selected_value = QLabel()
        self.selected_value.setObjectName("InfoBar")
        self.insert_btn = QPushButton("插入")
        set_button_role(self.insert_btn, "accent")
        self.insert_btn.clicked.connect(self._insert_selected)
        self.copy_btn = QPushButton("复制")
        set_button_role(self.copy_btn, "ghost")
        self.copy_btn.clicked.connect(self._copy_selected)
        row_lay.addWidget(self.selected_meta, 1)
        row_lay.addWidget(self.selected_value)
        row_lay.addWidget(self.copy_btn)
        row_lay.addWidget(self.insert_btn)
        self.insert_row.hide()
        insert_lay.addWidget(self.insert_row)
        root.addWidget(self.insert_card)

        self.preview_free.values_changed.connect(self._refresh_value_summary)
        self.preview_grid.values_changed.connect(self._refresh_value_summary)
        self.preview_free.widget_selected.connect(self._on_widget_selected)
        self.preview_grid.widget_selected.connect(self._on_widget_selected)
        PanelState.add_listener(self._refresh_value_summary)

        self._show_insert_hint()

    def refresh_viewport(self) -> None:
        if self._layout and is_free_mode(self._layout):
            self.preview_free.refresh_viewport()
        elif self._layout:
            self.preview_grid.set_layout(self._layout)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh_viewport()

    def apply_layout(self, layout: dict[str, Any]) -> None:
        old = PanelState.all()
        self._layout = layout
        self._selected_spec = None
        self._show_insert_hint()
        if not layout.get("enabled", True):
            self.preview_stack.setVisible(False)
            self._refresh_value_summary()
            return
        self.preview_stack.setVisible(True)
        if is_free_mode(layout):
            self.preview_stack.setCurrentWidget(self.preview_free)
            self.preview_free.set_layout(layout)
        else:
            self.preview_stack.setCurrentWidget(self.preview_grid)
            self.preview_grid.set_layout(layout)
        if old:
            merged = dict(PanelState.all())
            merged.update({k: v for k, v in old.items() if k in merged})
            PanelState.reset(merged)
        self._refresh_value_summary()

    def on_project_opened(self) -> None:
        project = self._project_dir_getter()
        if not project:
            self._layout = None
            self._selected_spec = None
            self._show_insert_hint()
            self._refresh_value_summary()
            return
        try:
            layout = load_layout(project)
        except Exception as exc:
            log.warning("加载 layout.json 失败: %s", exc)
            layout = None
        if layout is None:
            self._selected_spec = None
            self._show_insert_hint()
            self.values_label.setText("（未找到或无法解析 ui/layout.json）")
            QMessageBox.warning(self, "布局加载失败", "无法读取 ui/layout.json，请检查文件格式。")
            return
        if not PanelState.load_sidecar(project):
            PanelState.seed_from_layout(layout)
        self.apply_layout(layout)

    def _show_insert_hint(self) -> None:
        self.insert_hint.show()
        self.insert_row.hide()
        self._selected_spec = None

    def _show_insert_for(self, spec: dict[str, Any]) -> None:
        self._selected_spec = spec
        wid = spec["id"]
        label = spec.get("label") or wid
        wtype = spec.get("type", "")
        self.selected_meta.setText(f"{label}")
        self.selected_meta.setToolTip(f"{wid} · {wtype}")
        self.selected_value.setText(PanelState.get(wid) or "—")
        self.insert_hint.hide()
        self.insert_row.show()

    def _on_widget_selected(self, path: tuple[int, ...]) -> None:
        if not self._layout:
            self._show_insert_hint()
            return
        raw = resolve_layout_widget(self._layout, path)
        if raw is None:
            self._show_insert_hint()
            return
        lua_spec = widget_lua_spec(raw)
        if lua_spec is None:
            self._show_insert_hint()
            return
        self._show_insert_for(lua_spec)

    def _insert_selected(self) -> None:
        if self._selected_spec:
            self.insert_lua.emit(lua_read_snippet(self._selected_spec))

    def _copy_selected(self) -> None:
        if self._selected_spec:
            self.copy_lua.emit(lua_read_snippet(self._selected_spec))

    def _refresh_value_summary(self) -> None:
        text = PanelState.format_summary()
        self.values_label.setText(text if text.startswith("（") else f"当前值：{text}")
        project = self._project_dir_getter()
        if project:
            PanelState.save_sidecar(project)
        if self._selected_spec:
            wid = self._selected_spec["id"]
            self.selected_value.setText(PanelState.get(wid) or "—")
