"""布局编辑器 — 预览区与手机画布协调。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from studio.runtime.panel_state import PanelState
from studio.ui.app_theme import set_button_role
from studio.ui.layout_preview_widget import LayoutPreviewWidget
from studio.ui.minimal_bar_preview import MinimalBarPreviewWidget
from studio.ui.phone_canvas_widget import (
    AUTO_FIT_DEVICE,
    DEFAULT_PHONE_SCREEN_PX,
    PhoneCanvasWidget,
)
from studio.services.layout_clone import clone_layout, clone_widget
from studio.services.free_layout import is_free_mode
from studio.services.screen_layout import (
    CHROME_PATH_TAG,
    active_screen_index,
    chrome_widgets,
    ensure_migrated,
    migrate_layout,
    resolve_widget,
    screens,
)


class LayoutEditorPreviewMixin:
    """预览列构建与画布/网格预览同步。"""

    canvas_stack: QStackedWidget
    phone_canvas: PhoneCanvasWidget
    preview: LayoutPreviewWidget
    design_mode_cb: QCheckBox
    interactive_preview_cb: QCheckBox
    zoom_combo: QComboBox
    values_label: QLabel
    _layout: dict[str, Any]
    _selected_path: tuple[int, ...]
    widget_list: Any

    def _build_preview_column(self, add_menu) -> QWidget:
        center_wrap = QWidget()
        center_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout = QVBoxLayout(center_wrap)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        preview_header = QHBoxLayout()
        preview_header.setSpacing(8)
        self.design_mode_cb = QCheckBox("网格设计")
        self.design_mode_cb.setToolTip("仅网格布局：拖动排序、拉宽")
        self.design_mode_cb.toggled.connect(self._on_design_mode_toggled)
        preview_header.addWidget(self.design_mode_cb)
        self.design_mode_cb.hide()

        self.interactive_preview_cb = QCheckBox("交互预览")
        self.interactive_preview_cb.setToolTip("在手机画布内直接操作表单控件（顶部色条仍可拖动）")
        self.interactive_preview_cb.toggled.connect(self._on_interactive_preview_toggled)
        preview_header.addWidget(self.interactive_preview_cb)

        self.apk_shell_preview_cb = QCheckBox("APK 外壳预览")
        self.apk_shell_preview_cb.setToolTip("叠加设置 / 启停 / 日志，模拟打包后主界面")
        # 默认开启：简易模式「所见即打包」（先设值再连信号，避免 phone_canvas 尚未创建）
        self.apk_shell_preview_cb.setChecked(True)
        self.apk_shell_preview_cb.toggled.connect(self._on_apk_shell_preview_toggled)
        preview_header.addWidget(self.apk_shell_preview_cb)

        preview_add_btn = QPushButton("添加控件")
        set_button_role(preview_add_btn, "accent")
        preview_add_btn.setMinimumHeight(30)
        preview_add_btn.setMenu(add_menu)
        preview_add_btn.setToolTip("向当前界面添加控件（与左侧「＋ 添加控件」相同）")
        preview_header.addWidget(preview_add_btn)

        preview_toolbar = QHBoxLayout()
        preview_toolbar.setSpacing(8)
        preview_toolbar.addWidget(QLabel("预览宽度"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.setMinimumWidth(108)
        self._grid_zoom_items = [
            ("适应宽度", None),
            ("150%", 1.5),
            ("175%", 1.75),
            ("200%", 2.0),
            ("250%", 2.5),
        ]
        self._phone_zoom_items = [
            ("适应窗口", AUTO_FIT_DEVICE),
            ("紧凑 · 320", 320),
            ("中 · 360", DEFAULT_PHONE_SCREEN_PX),
            ("小米/Pixel · 392", 392),
            ("大 · 400", 400),
            ("iPhone 标准 · 390", 390),
            ("特大 · 440", 440),
            ("平板窄边 · 480", 480),
        ]
        self._populate_zoom_combo(free_mode=True)
        self.zoom_combo.setToolTip("主面板预览缩放（720×1280 等比，与 APK MainActivity 内表单一致）")
        self.zoom_combo.currentIndexChanged.connect(self._on_preview_zoom_changed)
        preview_toolbar.addWidget(self.zoom_combo)
        self.compare_grab_cb = QCheckBox("截图对照")
        self.compare_grab_cb.setToolTip("叠加抓抓页最新截图半透明对照（请先在抓抓页截屏）")
        self.compare_grab_cb.toggled.connect(self._on_compare_grab_toggled)
        preview_toolbar.addWidget(self.compare_grab_cb)
        preview_toolbar.addStretch(1)
        self.main_panel_hint = QLabel("APK 主面板 · 空白框选 / Ctrl+多选 · 拖动有智能对齐线")
        self.main_panel_hint.setObjectName("HintLabel")
        preview_toolbar.addWidget(self.main_panel_hint)
        center_layout.addLayout(preview_toolbar)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(6)
        theme_row.addWidget(QLabel("主题"))
        from studio.services.layout_defaults import PANEL_THEMES

        self._theme_chip_buttons: list[QPushButton] = []
        for tid, label in PANEL_THEMES:
            b = QPushButton(label)
            set_button_role(b, "ghost")
            b.setMinimumHeight(28)
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, t=tid: self._apply_theme_chip(t))
            theme_row.addWidget(b)
            self._theme_chip_buttons.append(b)
        theme_row.addStretch(1)
        center_layout.addLayout(theme_row)

        self.values_label = QLabel()
        self.values_label.setObjectName("InfoBar")
        self.values_label.setWordWrap(True)
        preview_header.addWidget(self.values_label, 1)

        snippet_btn = QPushButton("插入面板读取")
        set_button_role(snippet_btn, "primary")
        snippet_btn.setToolTip("根据当前 layout.json 生成 panel.get 代码并插入脚本")
        snippet_btn.clicked.connect(self._insert_panel_lua_example)
        preview_header.addWidget(snippet_btn)
        center_layout.addLayout(preview_header)

        self.canvas_stack = QStackedWidget()
        self.phone_canvas = PhoneCanvasWidget()
        self.phone_canvas.set_main_panel_preview(True)
        self.phone_canvas.set_phone_style(False)
        self.phone_canvas.set_device_emulation(False)
        self.phone_canvas.set_auto_fit_device(False)
        self.phone_canvas.set_target_screen_width(None)
        self.phone_canvas.set_min_scale(0.25)
        self.phone_canvas.set_compact_preview(True)
        self.phone_canvas.setMinimumHeight(480)
        self.phone_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview = LayoutPreviewWidget()
        self.preview.setMinimumHeight(420)
        self.canvas_stack.addWidget(self.phone_canvas)
        self.canvas_stack.addWidget(self.preview)
        center_layout.addWidget(self.canvas_stack, 1)
        self.minimal_preview = MinimalBarPreviewWidget()
        self.minimal_preview.hide()
        center_layout.addWidget(self.minimal_preview)
        self.preview.set_zoom_auto(True)
        return center_wrap

    def _sync_display_preview(self) -> None:
        panel = self._layout.get("panel", {})
        mode = str(panel.get("display_mode", "host"))
        is_minimal = mode == "minimal"
        if hasattr(self, "minimal_preview"):
            self.minimal_preview.setVisible(is_minimal)
            if is_minimal:
                self.minimal_preview.apply_panel(panel)
        if hasattr(self, "canvas_stack"):
            self.canvas_stack.setVisible(not is_minimal)

    def _wire_preview_signals(self) -> None:
        self.phone_canvas.layout_changed.connect(self._on_phone_structure_changed)
        self.phone_canvas.widget_selected.connect(self._on_preview_widget_selected)
        self.phone_canvas.selection_changed.connect(self._on_canvas_selection_changed)
        self.phone_canvas.screen_changed.connect(self._on_canvas_screen_changed)
        self.phone_canvas.nudge_selected.connect(self._on_nudge_selected)
        self.phone_canvas.delete_selected.connect(self._on_delete_selected)
        self.phone_canvas.duplicate_selected.connect(self._duplicate_widget)
        self.phone_canvas.undo_requested.connect(self._undo_layout)
        self.phone_canvas.redo_requested.connect(self._redo_layout)
        self.phone_canvas.values_changed.connect(self._refresh_value_summary)
        self.phone_canvas.context_menu_requested.connect(self._show_canvas_context_menu)
        self.preview.values_changed.connect(self._refresh_value_summary)
        self.preview.widget_selected.connect(self._on_preview_widget_selected)
        self.preview.structure_changed.connect(self._on_preview_structure_changed)
        PanelState.add_listener(self._refresh_value_summary)

    def _on_interactive_preview_toggled(self, checked: bool) -> None:
        if not hasattr(self, "phone_canvas"):
            return
        self.phone_canvas.set_interactive_preview(checked)

    def _on_apk_shell_preview_toggled(self, checked: bool) -> None:
        if not hasattr(self, "phone_canvas"):
            return
        self.phone_canvas.set_apk_shell_preview(checked)

    def _on_compare_grab_toggled(self, checked: bool) -> None:
        if not checked:
            self.phone_canvas.set_compare_opacity(0)
            self.main_panel_hint.setText("APK 主面板 · 空白框选 / Ctrl+多选 · 拖动有智能对齐线")
            return
        provider = getattr(self, "_grab_pixmap_provider_fn", None)
        pixmap = provider() if callable(provider) else None
        if pixmap is None or pixmap.isNull():
            from PySide6.QtWidgets import QMessageBox

            self.compare_grab_cb.blockSignals(True)
            self.compare_grab_cb.setChecked(False)
            self.compare_grab_cb.blockSignals(False)
            QMessageBox.information(self, "提示", "请先在「抓抓」页截屏，再开启截图对照。")
            return
        self.phone_canvas.set_backdrop_pixmap(pixmap)
        self.phone_canvas.set_compare_opacity(0.35)
        tip = self._compare_offset_tip(pixmap)
        self.main_panel_hint.setText(tip)
        self.compare_grab_cb.setToolTip(tip)

    def _compare_offset_tip(self, pixmap) -> str:
        from studio.services.free_layout import panel_design_size

        panel = (getattr(self, "_layout", None) or {}).get("panel") or {}
        dw, dh = panel_design_size(panel)
        pw = max(1, int(pixmap.width()))
        ph = max(1, int(pixmap.height()))
        sx = pw / max(1, dw)
        sy = ph / max(1, dh)
        scale_delta = abs(sx - sy)
        # 若按宽铺满设计画布，高度方向的像素余量（正=截图更高）
        fitted_h = ph * (dw / pw)
        dy_design = fitted_h - dh
        return (
            f"对照 {pw}×{ph} · 设计 {dw}×{dh} · "
            f"约 {sx:.2f}×/{sy:.2f}× · Δ比例 {scale_delta:.3f} · "
            f"按宽对齐时高度差约 {dy_design:+.0f}dp"
        )

    def _apply_theme_chip(self, theme_id: str) -> None:
        idx = self.theme_combo.findData(theme_id)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self._sync_theme_chips(theme_id)
        self._on_header_changed()

    def _sync_theme_chips(self, theme_id: str | None = None) -> None:
        tid = theme_id or (self.theme_combo.currentData() if hasattr(self, "theme_combo") else "light")
        from studio.services.layout_defaults import PANEL_THEMES

        for b, (id_, _label) in zip(getattr(self, "_theme_chip_buttons", []), PANEL_THEMES):
            b.blockSignals(True)
            b.setChecked(id_ == tid)
            b.blockSignals(False)

    def set_grab_pixmap_provider(self, provider) -> None:
        self._grab_pixmap_provider_fn = provider

    def _show_canvas_context_menu(self, global_pos) -> None:
        if not is_free_mode(self._layout):
            return
        menu = self._build_add_menu()
        menu.addSeparator()
        dup = menu.addAction("复制选中")
        dup.setEnabled(bool(self._selected_path))
        dup.triggered.connect(self._duplicate_widget)
        del_act = menu.addAction("删除选中")
        del_act.setEnabled(bool(self._selected_path))
        del_act.triggered.connect(self._on_delete_selected)
        reset_act = menu.addAction("重置为默认尺寸")
        reset_act.setEnabled(bool(self._selected_path))
        reset_act.triggered.connect(self._reset_selected_widget_layout)
        menu.exec(global_pos)

    def _reset_selected_widget_layout(self) -> None:
        if not self._selected_path or len(self._selected_path) != 2:
            return
        from studio.services.free_layout import default_rect_for_type
        from studio.services.screen_layout import set_widget_rect

        w = resolve_widget(self._layout, self._selected_path)
        if w is None:
            return
        idx = self._selected_path[1]
        rect = default_rect_for_type(str(w.get("type", "input")), idx + 1)
        set_widget_rect(
            self._layout,
            self._selected_path,
            rect["layout_x"],
            rect["layout_y"],
            rect["layout_w"],
            rect["layout_h"],
        )
        self._load_widget_into_form(w)
        self._update_preview(force=True)
        self._mark_dirty()
        self._emit_layout_changed()

    def _populate_zoom_combo(self, *, free_mode: bool) -> None:
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.clear()
        items = self._phone_zoom_items if free_mode else self._grid_zoom_items
        default_idx = 0
        for i, (label, val) in enumerate(items):
            self.zoom_combo.addItem(label, val)
            if free_mode and val == AUTO_FIT_DEVICE:
                default_idx = i
        self.zoom_combo.setCurrentIndex(default_idx if free_mode else 0)
        self.zoom_combo.blockSignals(False)

    def _sync_canvas_mode(self) -> None:
        free = is_free_mode(self._layout)
        self.canvas_stack.setCurrentIndex(0 if free else 1)
        self.design_mode_cb.setVisible(not free)
        self.zoom_combo.setVisible(True)
        if hasattr(self, "main_panel_hint"):
            self.main_panel_hint.setVisible(free)
        self._populate_zoom_combo(free_mode=free)
        if free:
            data = self.zoom_combo.currentData()
            if data == AUTO_FIT_DEVICE:
                self.phone_canvas.set_target_screen_width(None)
            else:
                width = int(data) if data is not None else DEFAULT_PHONE_SCREEN_PX
                self.phone_canvas.set_target_screen_width(width)
            self.phone_canvas.refresh_viewport()
        else:
            self.preview.set_zoom_auto(True)
        simple = self._is_simple_mode()
        self.interactive_preview_cb.setVisible(free and not simple)
        if not free or simple:
            self.interactive_preview_cb.setChecked(False)
        self.screen_tabs_editor.setVisible(free)
        for w in getattr(self, "_grid_header_widgets", []):
            w.setVisible(not free)
        if free:
            self.screen_tabs_editor.set_screens(
                screens(self._layout),
                active_screen_index(self._layout),
            )
        self._update_preview()

    def _sync_screen_tabs_from_layout(self) -> None:
        if not is_free_mode(self._layout):
            return
        self.screen_tabs_editor.set_screens(
            screens(self._layout),
            active_screen_index(self._layout),
        )

    def _on_phone_structure_changed(self, layout: dict) -> None:
        if not is_free_mode(self._layout):
            self._layout = migrate_layout(layout)
            self._refresh_widget_list(keep_row=True)
            self._mark_dirty()
            self._emit_layout_changed()
            return
        incoming = migrate_layout(layout)
        self._apply_canvas_layout_patch(incoming)
        self._refresh_widget_list(keep_row=True)
        if self._selected_path:
            w = resolve_widget(self._layout, self._selected_path)
            if w is not None:
                self._sync_layout_rect_to_form(w)
        self._mark_dirty()
        self._emit_layout_changed()

    def _sync_layout_rect_to_form(self, w: dict) -> None:
        self._loading_form = True
        try:
            for sp, key in (
                (self.layout_x_spin, "layout_x"),
                (self.layout_y_spin, "layout_y"),
                (self.layout_w_spin, "layout_w"),
                (self.layout_h_spin, "layout_h"),
            ):
                sp.blockSignals(True)
                sp.setValue(int(w.get(key, sp.value())))
                sp.blockSignals(False)
        finally:
            self._loading_form = False

    def _apply_canvas_layout_patch(self, incoming: dict) -> None:
        ensure_migrated(self._layout)
        in_panel = incoming.get("panel", {})
        panel = self._layout.setdefault("panel", {})
        if "active_screen" in in_panel:
            panel["active_screen"] = in_panel["active_screen"]

        def patch_list(dst_widgets: list, src_widgets: list) -> None:
            for i, src in enumerate(src_widgets):
                if i >= len(dst_widgets):
                    break
                dst = dst_widgets[i]
                if dst.get("id") != src.get("id") or dst.get("type") != src.get("type"):
                    continue
                for key in ("layout_x", "layout_y", "layout_w", "layout_h"):
                    if key in src:
                        dst[key] = src[key]

        in_screens = incoming.get("screens") or []
        dst_screens = screens(self._layout)
        for si, in_sc in enumerate(in_screens):
            if si >= len(dst_screens):
                break
            patch_list(
                dst_screens[si].setdefault("widgets", []),
                in_sc.get("widgets") or [],
            )
        patch_list(chrome_widgets(self._layout), incoming.get("widgets") or [])

    def _on_canvas_screen_changed(self, idx: int) -> None:
        self._flush_property_sync()
        self._layout.setdefault("panel", {})["active_screen"] = idx
        self.screen_tabs_editor.set_active_index(idx)
        self._selected_path = ()
        self._refresh_widget_list()
        self._clear_form()
        self._mark_dirty()
        self._emit_layout_changed()

    def _on_design_mode_toggled(self, checked: bool) -> None:
        self.preview.set_design_mode(checked)

    def _on_preview_zoom_changed(self, _index: int = 0) -> None:
        data = self.zoom_combo.currentData()
        if is_free_mode(self._layout):
            if data == AUTO_FIT_DEVICE:
                self.phone_canvas.set_target_screen_width(None)
            else:
                self.phone_canvas.set_auto_fit_device(False)
                width = int(data) if data is not None else DEFAULT_PHONE_SCREEN_PX
                self.phone_canvas.set_target_screen_width(width)
            self.phone_canvas.refresh_viewport()
            return
        if data is None:
            self.preview.set_zoom_auto(True)
        else:
            self.preview.set_preview_zoom(float(data))

    def _select_widget_path(self, path: tuple[int, ...], *, sync_canvas: bool = True) -> None:
        if not path:
            return
        self._flush_property_sync()
        if len(path) == 2:
            screen_idx, widget_idx = path
            if screen_idx == CHROME_PATH_TAG:
                w = resolve_widget(self._layout, path)
                if w:
                    self._selected_path = path
                    self.widget_list.blockSignals(True)
                    self.widget_list.clearSelection()
                    self.widget_list.blockSignals(False)
                    self._load_widget_into_form(w)
                    if sync_canvas:
                        self.phone_canvas.set_selected_path(path)
                return
            act = active_screen_index(self._layout)
            if screen_idx != act:
                self._layout.setdefault("panel", {})["active_screen"] = screen_idx
                self.screen_tabs_editor.set_active_index(screen_idx)
                self._refresh_widget_list()
                self.phone_canvas.set_layout(clone_layout(self._layout))
            self.widget_list.blockSignals(True)
            if 0 <= widget_idx < self.widget_list.count():
                self.widget_list.setCurrentRow(widget_idx)
            self.widget_list.blockSignals(False)
            w = resolve_widget(self._layout, path)
            if w:
                self._selected_path = path
                self._load_widget_into_form(w)
                if sync_canvas:
                    self.phone_canvas.set_selected_path(path)
            return
        if len(path) == 1:
            self.widget_list.blockSignals(True)
            self.widget_list.setCurrentRow(path[0])
            self.widget_list.blockSignals(False)
            self._on_select_widget(path[0])

    def _on_canvas_selection_changed(self, paths: object) -> None:
        plist = [p for p in (paths or []) if isinstance(p, tuple)]
        if not plist:
            return
        rows = sorted({p[1] for p in plist if len(p) == 2 and p[0] != CHROME_PATH_TAG})
        if not rows:
            return
        self.widget_list.blockSignals(True)
        self.widget_list.clearSelection()
        for r in rows:
            if 0 <= r < self.widget_list.count():
                self.widget_list.item(r).setSelected(True)
        self.widget_list.setCurrentRow(rows[0])
        self.widget_list.blockSignals(False)
        if len(plist) == 1:
            self._select_widget_path(plist[0], sync_canvas=False)
        else:
            w = resolve_widget(self._layout, plist[0])
            if w is not None:
                self._selected_path = plist[0]
                self._load_widget_into_form(w)

    def _on_preview_widget_selected(self, path: tuple) -> None:
        if isinstance(path, tuple):
            paths = self.phone_canvas.selected_paths() if hasattr(self, "phone_canvas") else []
            if len(paths) > 1 and path in paths:
                self._on_canvas_selection_changed(paths)
                return
            self._select_widget_path(path)
        elif isinstance(path, int) and 0 <= path < self.widget_list.count():
            self.widget_list.setCurrentRow(path)

    def _on_preview_structure_changed(self, layout: dict) -> None:
        self._layout = migrate_layout(layout)
        row = self.widget_list.currentRow()
        self._refresh_widget_list()
        if 0 <= row < self.widget_list.count():
            self.widget_list.setCurrentRow(row)
            self._on_select_widget(row)
        panel = self._layout.get("panel", {})
        self.width_dp_spin.blockSignals(True)
        self.width_dp_spin.setValue(int(panel.get("width_dp", 220)))
        self.width_dp_spin.blockSignals(False)
        self._mark_dirty()
        self._emit_layout_changed()

    def _mirror_widget_to_canvas(self, path: tuple[int, ...], spec: dict[str, Any]) -> None:
        canvas_layout = getattr(self.phone_canvas, "_layout", None)
        if not canvas_layout:
            return
        cw = resolve_widget(canvas_layout, path)
        if cw is None:
            return
        patch = clone_widget(spec)
        for key in list(cw.keys()):
            if key not in patch:
                del cw[key]
        cw.update(patch)

    def _refresh_canvas_after_spec_change(self, path: tuple[int, ...], spec: dict[str, Any]) -> None:
        self._mirror_widget_to_canvas(path, spec)
        if is_free_mode(self._layout):
            if not self.phone_canvas.refresh_widget_at(path):
                self._update_preview(force=True)
        else:
            self._update_preview()

    def _refresh_value_summary(self) -> None:
        self.values_label.setText(PanelState.format_summary())
        if self._project_dir_getter():
            PanelState.save_sidecar(Path(self._project_dir_getter() or "."))

    def _update_preview(self, *, force: bool = False) -> None:
        self._apply_header()
        self._sync_display_preview()
        payload = clone_layout(self._layout)
        if is_free_mode(self._layout):
            self.phone_canvas.set_layout(
                payload,
                selected_path=self._selected_path or None,
                full=force,
            )
            if self._selected_path:
                self.phone_canvas.set_selected_path(self._selected_path)
            QTimer.singleShot(0, self.phone_canvas.refresh_viewport)
        else:
            selected_path: tuple[int, ...] | None = None
            row = self.widget_list.currentRow()
            if row >= 0:
                selected_path = (row,)
            self.preview.set_layout(payload, selected_path=selected_path)
        self._refresh_value_summary()
