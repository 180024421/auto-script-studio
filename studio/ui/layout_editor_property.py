"""布局编辑器 — 控件属性面板。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QWidget,
)

from studio.ui.app_theme import set_button_role
from studio.services.layout_clone import clone_widget
from studio.services.free_layout import estimate_text_layout_width, is_free_mode, panel_design_size
from studio.services.screen_layout import (
    CHROME_PATH_TAG,
    active_screen_index,
    resolve_widget,
)
from studio.services.layout_defaults import (
    action_types_for_layout,
    FORM_WIDGET_TYPES,
    is_action_type,
    widget_display_name,
)


class LayoutEditorPropertyMixin:
    """右侧属性表单：构建、加载、同步。"""

    _layout: dict[str, Any]
    _selected_path: tuple[int, ...]
    _loading_form: bool
    widget_list: Any
    request_pick_mode: Any

    def _build_property_panel(self) -> QScrollArea:
        form_box = QGroupBox("控件属性")
        form = QFormLayout(form_box)
        self.id_edit = QLineEdit()
        self.type_combo = QComboBox()
        for t, desc in FORM_WIDGET_TYPES + action_types_for_layout(self._layout):
            self.type_combo.addItem(f"{desc} ({t})", t)
        self.label_edit = QLineEdit()
        self.text_edit = QLineEdit()
        self.text_style_combo = QComboBox()
        for val, desc in [("title", "标题"), ("hint", "提示"), ("normal", "普通")]:
            self.text_style_combo.addItem(desc, val)
        self.color_edit = QLineEdit("#2563EB")
        pick_color_btn = QPushButton("选色")
        set_button_role(pick_color_btn, "ghost")
        pick_color_btn.clicked.connect(self._pick_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_edit, 1)
        color_row.addWidget(pick_color_btn)
        color_wrap = QWidget()
        color_wrap.setLayout(color_row)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 3)
        self.placeholder_edit = QLineEdit()
        self.default_edit = QLineEdit()
        self.options_edit = QTextEdit()
        self.options_edit.setMaximumHeight(72)
        self.options_edit.setPlaceholderText("每行一个选项")
        self.layout_x_spin = QSpinBox()
        self.layout_y_spin = QSpinBox()
        self.layout_w_spin = QSpinBox()
        self.layout_h_spin = QSpinBox()
        for sp in (self.layout_x_spin, self.layout_y_spin):
            sp.setRange(0, 4096)
        for sp in (self.layout_w_spin, self.layout_h_spin):
            sp.setRange(24, 4096)
        self.required_cb = QCheckBox("必填")
        self.min_edit = QLineEdit()
        self.min_edit.setPlaceholderText("最小值（留空不限）")
        self.max_edit = QLineEdit()
        self.max_edit.setPlaceholderText("最大值（留空不限）")
        self.switch_default_cb = QCheckBox("默认开启")
        self.time_start_edit = QTimeEdit()
        self.time_start_edit.setDisplayFormat("HH:mm")
        self.time_end_edit = QTimeEdit()
        self.time_end_edit.setDisplayFormat("HH:mm")
        time_row = QWidget()
        time_row_l = QHBoxLayout(time_row)
        time_row_l.setContentsMargins(0, 0, 0, 0)
        time_row_l.addWidget(QLabel("从"))
        time_row_l.addWidget(self.time_start_edit)
        time_row_l.addWidget(QLabel("到"))
        time_row_l.addWidget(self.time_end_edit)
        self.x_spin = QSpinBox()
        self.y_spin = QSpinBox()
        self.x1_spin = QSpinBox()
        self.y1_spin = QSpinBox()
        self.x2_spin = QSpinBox()
        self.y2_spin = QSpinBox()
        for sp in (self.x_spin, self.y_spin, self.x1_spin, self.y1_spin, self.x2_spin, self.y2_spin):
            sp.setRange(0, 4096)
        self.lua_edit = QTextEdit()
        self.lua_edit.setMaximumHeight(80)
        self.lua_edit.setPlaceholderText('bot.tap(100, 200) 或 panel.get("mode")')

        self._row_id = form.rowCount()
        form.addRow("ID", self.id_edit)
        self._row_type = form.rowCount()
        form.addRow("类型", self.type_combo)
        self._row_label = form.rowCount()
        form.addRow("显示文字", self.label_edit)
        self._row_text = form.rowCount()
        form.addRow("标签文本", self.text_edit)
        self._row_text_style = form.rowCount()
        form.addRow("文字样式", self.text_style_combo)
        self._row_color = form.rowCount()
        form.addRow("颜色", color_wrap)
        self._row_width = form.rowCount()
        form.addRow("占列宽", self.width_spin)
        self._row_placeholder = form.rowCount()
        form.addRow("占位提示", self.placeholder_edit)
        self._row_default = form.rowCount()
        form.addRow("默认值", self.default_edit)
        self._row_options = form.rowCount()
        form.addRow("选项(每行)", self.options_edit)
        self._row_layout_rect = form.rowCount()
        form.addRow("位置 X/Y", self._xy_row(self.layout_x_spin, self.layout_y_spin))
        self._row_layout_size = form.rowCount()
        form.addRow("大小 W/H", self._xy_row(self.layout_w_spin, self.layout_h_spin))
        self._row_required = form.rowCount()
        form.addRow("校验", self.required_cb)
        self._row_min = form.rowCount()
        form.addRow("最小值", self.min_edit)
        self._row_max = form.rowCount()
        form.addRow("最大值", self.max_edit)
        self._row_switch_default = form.rowCount()
        form.addRow("开关默认", self.switch_default_cb)
        self._row_time_range = form.rowCount()
        form.addRow("时间范围", time_row)
        self._row_xy = form.rowCount()
        form.addRow("点击 X/Y", self._xy_row(self.x_spin, self.y_spin))
        self._row_swipe1 = form.rowCount()
        form.addRow("滑动起止", self._xy_row(self.x1_spin, self.y1_spin))
        self._row_swipe2 = form.rowCount()
        form.addRow("", self._xy_row(self.x2_spin, self.y2_spin))
        pick_wrap = QWidget()
        pick_grid_l = QGridLayout(pick_wrap)
        pick_grid_l.setContentsMargins(0, 0, 0, 0)
        pick_grid_l.setHorizontalSpacing(8)
        pick_grid_l.setVerticalSpacing(8)
        for i, (text, mode, role) in enumerate([
            ("面板位置", "panel", "accent"),
            ("点击坐标", "tap", "ghost"),
            ("滑起点", "swipe1", "ghost"),
            ("滑终点", "swipe2", "ghost"),
        ]):
            b = QPushButton(text)
            set_button_role(b, role)
            b.setMinimumHeight(34)
            b.clicked.connect(lambda _c=False, m=mode: self.request_pick_mode.emit(m))
            pick_grid_l.addWidget(b, i // 2, i % 2)
        for c in range(2):
            pick_grid_l.setColumnStretch(c, 1)
        self._row_pick = form.rowCount()
        form.addRow("从截图取点", pick_wrap)
        self._row_lua = form.rowCount()
        form.addRow("Lua 代码", self.lua_edit)

        form_box.setMinimumWidth(320)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setObjectName("PropertyScroll")
        form_scroll.setMinimumWidth(320)
        form_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        form_scroll.setWidget(form_box)
        return form_scroll

    def _wire_property_signals(self) -> None:
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        for w in (
            self.title_edit,
            self.color_edit,
            self.id_edit,
            self.label_edit,
            self.text_edit,
            self.placeholder_edit,
            self.default_edit,
        ):
            w.textChanged.connect(self._sync_form_to_layout)
        self.text_style_combo.currentIndexChanged.connect(self._sync_form_to_layout)
        self.width_spin.valueChanged.connect(self._sync_form_to_layout)
        for sp in (self.x_spin, self.y_spin, self.x1_spin, self.y1_spin, self.x2_spin, self.y2_spin):
            sp.valueChanged.connect(self._sync_form_to_layout)
        self.lua_edit.textChanged.connect(self._sync_form_to_layout)
        self.options_edit.textChanged.connect(self._sync_form_to_layout)
        self.min_edit.textChanged.connect(self._sync_form_to_layout)
        self.max_edit.textChanged.connect(self._sync_form_to_layout)
        self.required_cb.toggled.connect(self._sync_form_to_layout)
        self.switch_default_cb.toggled.connect(self._sync_form_to_layout)
        self.time_start_edit.timeChanged.connect(self._sync_form_to_layout)
        self.time_end_edit.timeChanged.connect(self._sync_form_to_layout)
        for sp in (self.layout_x_spin, self.layout_y_spin, self.layout_w_spin, self.layout_h_spin):
            sp.valueChanged.connect(self._sync_form_to_layout)

    def _xy_row(self, a: QSpinBox, b: QSpinBox) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(a)
        row.addWidget(b)
        return w

    def _pick_color(self) -> None:
        initial = QColor(self.color_edit.text().strip() or "#2563EB")
        color = QColorDialog.getColor(initial, self, "选择按钮颜色")
        if color.isValid():
            self.color_edit.setText(color.name())
            self._sync_form_to_layout()

    def _load_widget_into_form(self, w: dict) -> None:
        self._loading_form = True
        blocked: list[tuple[Any, bool]] = []
        for wdg in (
            self.id_edit,
            self.label_edit,
            self.text_edit,
            self.text_style_combo,
            self.type_combo,
            self.color_edit,
            self.width_spin,
            self.placeholder_edit,
            self.default_edit,
            self.layout_x_spin,
            self.layout_y_spin,
            self.layout_w_spin,
            self.layout_h_spin,
            self.required_cb,
            self.switch_default_cb,
            self.time_start_edit,
            self.time_end_edit,
            self.x_spin,
            self.y_spin,
            self.x1_spin,
            self.y1_spin,
            self.x2_spin,
            self.y2_spin,
        ):
            blocked.append((wdg, wdg.blockSignals(True)))
        self.options_edit.blockSignals(True)
        self.lua_edit.blockSignals(True)
        try:
            self.id_edit.setText(w.get("id", ""))
            self.label_edit.setText(w.get("label", ""))
            self.text_edit.setText(w.get("text", ""))
            ts_idx = self.text_style_combo.findData(str(w.get("text_style") or "normal"))
            self.text_style_combo.setCurrentIndex(max(0, ts_idx))
            idx = self.type_combo.findData(w.get("type", "tap"))
            self.type_combo.setCurrentIndex(max(0, idx))
            self.color_edit.setText(w.get("color", "#2563EB"))
            self.width_spin.setValue(int(w.get("width", 1)))
            self.placeholder_edit.setText(w.get("placeholder", ""))
            self.options_edit.setPlainText("\n".join(w.get("options") or []))
            self.layout_x_spin.setValue(int(w.get("layout_x", 24)))
            self.layout_y_spin.setValue(int(w.get("layout_y", 120)))
            self.layout_w_spin.setValue(int(w.get("layout_w", 320)))
            self.layout_h_spin.setValue(int(w.get("layout_h", 56)))
            self.required_cb.setChecked(bool(w.get("required")))
            wtype = w.get("type", "")
            if wtype == "time_range":
                self.time_start_edit.setTime(
                    self._qtime_from_str(str(w.get("default_start", "09:00")), "09:00")
                )
                self.time_end_edit.setTime(
                    self._qtime_from_str(str(w.get("default_end", "18:00")), "18:00")
                )
                self.default_edit.setText(str(w.get("default", "")))
            elif wtype == "switch":
                raw = w.get("default", False)
                self.switch_default_cb.setChecked(
                    str(raw).lower() in ("true", "1", "yes", "on")
                )
            else:
                self.min_edit.setText("" if w.get("min") is None else str(w.get("min")))
                self.max_edit.setText("" if w.get("max") is None else str(w.get("max")))
                self.default_edit.setText(w.get("default", ""))
            self.x_spin.setValue(int(w.get("x", 0)))
            self.y_spin.setValue(int(w.get("y", 0)))
            self.x1_spin.setValue(int(w.get("x1", 0)))
            self.y1_spin.setValue(int(w.get("y1", 0)))
            self.x2_spin.setValue(int(w.get("x2", 0)))
            self.y2_spin.setValue(int(w.get("y2", 0)))
            self.lua_edit.setPlainText(w.get("lua", ""))
            self._update_form_visibility(wtype)
        finally:
            self.options_edit.blockSignals(False)
            self.lua_edit.blockSignals(False)
            for wdg, was in blocked:
                wdg.blockSignals(was)
            self._loading_form = False

    def _on_select_widget(self, row: int) -> None:
        widgets = self._widgets()
        if row < 0 or row >= len(widgets):
            self._clear_form()
            self._selected_path = ()
            return
        w = widgets[row]
        self._selected_path = (
            (active_screen_index(self._layout), row) if is_free_mode(self._layout) else (row,)
        )
        self._load_widget_into_form(w)
        if is_free_mode(self._layout):
            self.phone_canvas.set_selected_path(self._selected_path)
        else:
            self._update_preview()

    def _clear_form(self) -> None:
        self._selected_path = ()
        self.id_edit.clear()
        self.label_edit.clear()
        self.text_edit.clear()
        self.lua_edit.clear()

    def _on_type_changed(self) -> None:
        wtype = self.type_combo.currentData() or ""
        self._update_form_visibility(wtype)
        self._sync_form_to_layout()

    def _update_form_visibility(self, wtype: str) -> None:
        parent_form: QFormLayout = self.findChildren(QFormLayout)[0]

        def show_row(row: int, visible: bool) -> None:
            if row < 0:
                return
            label = parent_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field = parent_form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label and label.widget():
                label.widget().setVisible(visible)
            if field and field.widget():
                field.widget().setVisible(visible)

        action = is_action_type(wtype)
        free = is_free_mode(self._layout)
        show_row(self._row_label, wtype not in ("label", "divider", "text"))
        show_row(self._row_text, wtype in ("label", "text"))
        show_row(self._row_text_style, wtype == "text")
        if wtype == "text":
            self._set_form_row_label(self._row_text, "提示文字")
        elif wtype == "label":
            self._set_form_row_label(self._row_text, "标签文本")
        show_row(self._row_color, action)
        show_row(self._row_placeholder, wtype in ("input", "textarea"))
        show_row(
            self._row_default,
            wtype in ("input", "select", "radio", "multiselect", "slider", "stepper", "textarea"),
        )
        show_row(self._row_switch_default, wtype == "switch")
        show_row(self._row_time_range, wtype == "time_range")
        show_row(self._row_options, wtype in ("select", "radio", "multiselect"))
        show_row(self._row_layout_rect, free)
        show_row(self._row_layout_size, free)
        show_row(self._row_width, not free)
        show_row(self._row_required, wtype == "input")
        show_row(self._row_min, wtype in ("input", "slider", "stepper"))
        show_row(self._row_max, wtype in ("input", "slider", "stepper"))
        self._set_form_row_label(self._row_min, "最小值")
        self._set_form_row_label(self._row_max, "最大值")
        if wtype == "time_range":
            self.default_edit.setPlaceholderText("可选：09:00-18:00")
        else:
            self.default_edit.setPlaceholderText("")
        show_row(self._row_xy, action and wtype in ("tap", "long_press"))
        show_row(self._row_swipe1, action and wtype == "swipe")
        show_row(self._row_swipe2, action and wtype == "swipe")
        show_row(self._row_pick, action)
        show_row(self._row_lua, action and wtype in ("lua", "snippet"))

    def _set_form_row_label(self, row: int, text: str) -> None:
        parent_form: QFormLayout = self.findChildren(QFormLayout)[0]
        label = parent_form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        if label and label.widget():
            label.widget().setText(text)

    def _sync_form_to_layout(self, *_args) -> None:
        if self._loading_form:
            return
        target = self._edit_target()
        if target is None:
            self._apply_header()
            if not is_free_mode(self._layout):
                self._update_preview()
            self._emit_layout_changed()
            return
        w, path, row = target
        wtype = self.type_combo.currentData() or "tap"
        w["id"] = self.id_edit.text().strip() or f"w_{row}"
        w["type"] = wtype
        w["label"] = self.label_edit.text().strip()
        w["text"] = self.text_edit.text().strip()
        if wtype == "text":
            w["text_style"] = self.text_style_combo.currentData() or "normal"
        elif "text_style" in w:
            del w["text_style"]
        w["color"] = self.color_edit.text().strip() or "#2563EB"
        w["width"] = self.width_spin.value()
        w["placeholder"] = self.placeholder_edit.text().strip()
        if wtype == "time_range":
            start = self.time_start_edit.time().toString("HH:mm")
            end = self.time_end_edit.time().toString("HH:mm")
            w["default_start"] = start
            w["default_end"] = end
            w["default"] = self.default_edit.text().strip() or f"{start}-{end}"
        elif wtype == "switch":
            w["default"] = "true" if self.switch_default_cb.isChecked() else "false"
        else:
            w["default"] = self.default_edit.text().strip()
        opts = [ln.strip() for ln in self.options_edit.toPlainText().splitlines() if ln.strip()]
        if opts:
            w["options"] = opts
        elif "options" in w:
            del w["options"]
        if wtype == "input":
            w["required"] = self.required_cb.isChecked()
            min_t = self.min_edit.text().strip()
            max_t = self.max_edit.text().strip()
            if min_t:
                w["min"] = float(min_t) if "." in min_t else int(min_t)
            elif "min" in w:
                del w["min"]
            if max_t:
                w["max"] = float(max_t) if "." in max_t else int(max_t)
            elif "max" in w:
                del w["max"]
        elif "required" in w:
            del w["required"]
            w.pop("min", None)
            w.pop("max", None)
        w["x"] = self.x_spin.value()
        w["y"] = self.y_spin.value()
        w["x1"] = self.x1_spin.value()
        w["y1"] = self.y1_spin.value()
        w["x2"] = self.x2_spin.value()
        w["y2"] = self.y2_spin.value()
        w["lua"] = self.lua_edit.toPlainText().strip()
        if is_free_mode(self._layout):
            w["layout_x"] = self.layout_x_spin.value()
            w["layout_y"] = self.layout_y_spin.value()
            sender = self.sender()
            geom_spin = sender in (
                self.layout_x_spin,
                self.layout_y_spin,
                self.layout_w_spin,
                self.layout_h_spin,
            )
            text_geom = sender in (self.text_edit, self.text_style_combo)
            if wtype in ("text", "label") and text_geom and not geom_spin:
                style = str(w.get("text_style") or "normal") if wtype == "text" else "normal"
                content = w.get("text") or w.get("label") or ""
                est_w = estimate_text_layout_width(str(content), style)
                w["layout_w"] = est_w
                self.layout_w_spin.blockSignals(True)
                self.layout_w_spin.setValue(est_w)
                self.layout_w_spin.blockSignals(False)
            else:
                w["layout_w"] = self.layout_w_spin.value()
            w["layout_h"] = self.layout_h_spin.value()
            from studio.services.screen_layout import set_widget_rect

            set_widget_rect(
                self._layout,
                path,
                int(w["layout_x"]),
                int(w["layout_y"]),
                int(w["layout_w"]),
                int(w["layout_h"]),
            )
            dw, _ = panel_design_size(self._layout.get("panel", {}))
            for sp, key in (
                (self.layout_x_spin, "layout_x"),
                (self.layout_y_spin, "layout_y"),
                (self.layout_w_spin, "layout_w"),
                (self.layout_h_spin, "layout_h"),
            ):
                sp.blockSignals(True)
                sp.setValue(int(w[key]))
                sp.blockSignals(False)
            self.layout_x_spin.setMaximum(max(0, dw - int(w["layout_w"])))
            self.layout_w_spin.setMaximum(dw)
        self._apply_header()
        if path[0] != CHROME_PATH_TAG and 0 <= row < self.widget_list.count():
            item = self.widget_list.item(row)
            if item:
                item.setText(widget_display_name(w))
        self._refresh_canvas_after_spec_change(path, w)
        self._mark_dirty()
        self._emit_layout_changed()

    def _edit_target(self) -> tuple[dict, tuple[int, ...], int] | None:
        if self._selected_path and len(self._selected_path) == 2:
            w = resolve_widget(self._layout, self._selected_path)
            if w is not None:
                row = self._selected_path[1] if self._selected_path[0] != CHROME_PATH_TAG else -1
                return w, self._selected_path, row
        row = self.widget_list.currentRow()
        widgets = self._widgets()
        if 0 <= row < len(widgets):
            path: tuple[int, ...] = (
                (active_screen_index(self._layout), row)
                if is_free_mode(self._layout)
                else (row,)
            )
            return widgets[row], path, row
        return None

    def _qtime_from_str(self, text: str, fallback: str) -> QTime:
        for candidate in (text, fallback):
            parsed = QTime.fromString(candidate, "HH:mm")
            if parsed.isValid():
                return parsed
        return QTime(9, 0)
