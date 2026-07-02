"""浮动面板 WYSIWYG 预览（可交互，同步 PanelState；可选布局设计模式）。"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from studio.runtime.panel_state import PanelState
from studio.services.layout_defaults import is_action_type, validate_widget_value
from studio.services.widget_path import (
    container_prefix,
    remap_path_after_reorder,
    reorder_in_container,
    set_widget_width,
)
from studio.ui.preview_design import DesignFrame, PanelWidthHandle


def _panel_width_px(width_dp: int, zoom: float = 1.0) -> int:
    """预览区 1dp≈1px × zoom。"""
    return max(200, int(width_dp * zoom))


def _set_tree_enabled(widget: QWidget, enabled: bool) -> None:
    widget.setEnabled(enabled)
    for child in widget.findChildren(QWidget):
        child.setEnabled(enabled)


class LayoutPreviewWidget(QScrollArea):
    values_changed = Signal()
    widget_selected = Signal(tuple)
    structure_changed = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setObjectName("PreviewPanel")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._viewport = QWidget()
        self._viewport.setObjectName("PreviewViewport")
        self.setWidget(self._viewport)
        self._root = QVBoxLayout(self._viewport)
        self._root.setContentsMargins(6, 4, 6, 6)
        self._root.setSpacing(0)
        self._layout: dict[str, Any] = {}
        self._design_mode = False
        self._zoom_auto = True
        self._preview_zoom = 2.0
        self._selected_path: tuple[int, ...] = ()
        self._frames: list[DesignFrame] = []
        self._panel_card: QFrame | None = None
        self._panel_handle: PanelWidthHandle | None = None
        self._suppress_structure = False
        self._last_fit_width = -1

    def design_mode(self) -> bool:
        return self._design_mode

    def preview_zoom(self) -> float:
        return self._preview_zoom

    def zoom_auto(self) -> bool:
        return self._zoom_auto

    def set_zoom_auto(self, on: bool) -> None:
        if self._zoom_auto == on:
            return
        self._zoom_auto = on
        self._last_fit_width = -1
        self._rebuild()

    def set_preview_zoom(self, factor: float) -> None:
        factor = max(1.0, min(3.5, float(factor)))
        self._zoom_auto = False
        if abs(self._preview_zoom - factor) < 0.01:
            self._rebuild()
            return
        self._preview_zoom = factor
        self._rebuild()

    def _effective_zoom(self, width_dp: int) -> float:
        if not self._zoom_auto:
            return self._preview_zoom
        pad = 24
        if self._design_mode:
            pad += 32
        available = max(220, self.viewport().width() - pad)
        return max(1.25, min(3.5, available / max(1, width_dp)))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not self._zoom_auto or not self._layout:
            return
        w = self.viewport().width()
        if w == self._last_fit_width:
            return
        self._last_fit_width = w
        self._rebuild()

    def set_design_mode(self, on: bool) -> None:
        if self._design_mode == on:
            return
        self._design_mode = on
        self._selected_path = ()
        self._rebuild()

    def set_layout(
        self,
        layout: dict[str, Any],
        *,
        selected_index: int | None = None,
        selected_path: tuple[int, ...] | None = None,
    ) -> None:
        old = PanelState.all()
        self._layout = json.loads(json.dumps(layout or {}))
        PanelState.seed_from_layout(self._layout)
        for k, v in old.items():
            if k in PanelState.all():
                PanelState.set(k, v)
        if selected_path is not None:
            self._selected_path = selected_path
        elif selected_index is not None:
            self._selected_path = (selected_index,) if selected_index >= 0 else ()
        self._rebuild()
        self.values_changed.emit()

    def _clear(self) -> None:
        self._frames = []
        self._panel_card = None
        self._panel_handle = None
        while self._root.count():
            item = self._root.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _emit_values(self) -> None:
        self.values_changed.emit()

    def _emit_structure(self) -> None:
        if self._suppress_structure:
            return
        self.structure_changed.emit(json.loads(json.dumps(self._layout)))
        self.values_changed.emit()

    def _fill_grid(
        self,
        widgets: list,
        grid: QGridLayout,
        cols: int,
        container: tuple[int, ...],
        grid_host: QWidget,
        zoom: float = 1.0,
    ) -> None:
        row, col = 0, 0

        def place(w: QWidget, span: int) -> None:
            nonlocal row, col
            if col + span > cols:
                row += 1
                col = 0
            grid.addWidget(w, row, col, 1, span)
            col += span
            if col >= cols:
                row += 1
                col = 0

        for idx, spec in enumerate(widgets):
            wtype = spec.get("type", "tap")
            if wtype == "tabs" and self._design_mode:
                inner = self._build_tabs_design(spec, cols, idx, grid_host, zoom)
            else:
                inner = self._build_widget(spec, cols, zoom)

            if self._design_mode:
                path = container + (idx,)
                span = max(1, min(cols, int(spec.get("width", 1))))
                frame = DesignFrame(path, container, span, cols, inner, grid_host)
                frame.set_selected(path == self._selected_path)
                frame.selected.connect(self._on_frame_selected)
                frame.reorder_request.connect(self._on_reorder)
                frame.span_changed.connect(self._on_span_changed)
                frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                if wtype != "tabs":
                    _set_tree_enabled(inner, False)
                self._frames.append(frame)
                place(frame, span)
            else:
                inner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                place(inner, max(1, min(cols, int(spec.get("width", 1)))))

        for c in range(cols):
            grid.setColumnStretch(c, 1)

    def _build_tabs_design(
        self,
        spec: dict[str, Any],
        cols: int,
        tabs_idx: int,
        grid_host: QWidget,
        zoom: float = 1.0,
    ) -> QTabWidget:
        tabs = QTabWidget()
        for tab_idx, tab in enumerate(spec.get("tabs") or []):
            page = QWidget()
            tab_grid_host = QWidget()
            tab_grid = QGridLayout(tab_grid_host)
            tab_grid.setContentsMargins(4, 4, 4, 4)
            tab_grid.setHorizontalSpacing(6)
            tab_grid.setVerticalSpacing(6)
            tab_widgets = tab.get("widgets") or []
            self._fill_grid(tab_widgets, tab_grid, cols, (tabs_idx, tab_idx), tab_grid_host, zoom)
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.addWidget(tab_grid_host)
            tabs.addTab(page, tab.get("title", "页签"))
        return tabs

    def _rebuild(self) -> None:
        self._clear()
        if not self._layout.get("enabled", True):
            lbl = QLabel("浮动面板已禁用")
            lbl.setAlignment(Qt.AlignCenter)
            self._root.addWidget(lbl)
            return

        panel = self._layout.get("panel", {})
        cols = max(1, min(3, int(panel.get("columns", 2))))
        width_dp = int(panel.get("width_dp", 220))
        zoom = self._effective_zoom(width_dp)
        self._last_fit_width = self.viewport().width()
        width_px = _panel_width_px(width_dp, zoom)
        font_px = max(12, int(13 * zoom))
        field_px = max(11, int(12 * zoom))
        btn_pad = max(6, int(8 * zoom))
        btn_h = max(32, int(36 * zoom))

        center_row = QWidget()
        center_lay = QHBoxLayout(center_row)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.addStretch(1)

        panel_row = QWidget()
        panel_row_lay = QHBoxLayout(panel_row)
        panel_row_lay.setContentsMargins(0, 0, 0, 0)
        panel_row_lay.setSpacing(6)

        card = QFrame()
        card.setObjectName("OverlayPanelCard")
        self._panel_card = card
        card.setFixedWidth(width_px)
        card.setStyleSheet(
            f"QWidget {{ font-size: {font_px}px; }}"
            f"#PanelTitleBar {{ font-size: {font_px + 1}px; padding: {btn_pad}px {btn_pad + 2}px; }}"
            f"#PanelFieldLabel {{ font-size: {field_px}px; }}"
            f"#PanelLogArea {{ font-size: {field_px}px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 10)
        card_layout.setSpacing(8)

        title_bar = QLabel(panel.get("title", "脚本助手"))
        title_bar.setObjectName("PanelTitleBar")
        title_bar.setWordWrap(True)
        card_layout.addWidget(title_bar)

        grid_host = QWidget()
        grid_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        widgets = self._layout.get("widgets") or self._layout.get("buttons") or []
        self._fill_grid(widgets, grid, cols, (), grid_host, zoom)
        card_layout.addWidget(grid_host)

        if panel.get("show_log", True):
            log = QLabel("日志输出区域…")
            log.setObjectName("PanelLogArea")
            log.setMinimumHeight(56)
            log.setWordWrap(True)
            log.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            card_layout.addWidget(log)

        panel_row_lay.addWidget(card)

        if self._design_mode:
            handle_col = QVBoxLayout()
            handle_col.setContentsMargins(0, 24, 0, 0)
            self._panel_handle = PanelWidthHandle()
            self._panel_handle.set_width_dp(width_dp)
            self._panel_handle.width_dp_changed.connect(self._on_panel_width_dp)
            handle_col.addWidget(self._panel_handle, 0, Qt.AlignTop)
            handle_col.addStretch()
            panel_row_lay.addLayout(handle_col)

        center_lay.addWidget(panel_row, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        center_lay.addStretch(1)
        self._root.addWidget(center_row, 1, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

    def _on_frame_selected(self, path: tuple[int, ...]) -> None:
        self._selected_path = path
        for fr in self._frames:
            fr.set_selected(fr.widget_path() == path)
        self.widget_selected.emit(path)

    def _on_reorder(self, container: tuple[int, ...], from_idx: int, to_idx: int) -> None:
        self._layout = reorder_in_container(self._layout, container, from_idx, to_idx)
        self._selected_path = remap_path_after_reorder(
            self._selected_path, container, from_idx, to_idx
        )
        self._suppress_structure = True
        self._rebuild()
        self._suppress_structure = False
        self._emit_structure()

    def _on_span_changed(self, path: tuple[int, ...], span: int) -> None:
        self._layout = set_widget_width(self._layout, path, span)
        self._suppress_structure = True
        self._rebuild()
        self._suppress_structure = False
        self._emit_structure()

    def _on_panel_width_dp(self, dp: int) -> None:
        self._layout.setdefault("panel", {})["width_dp"] = dp
        if self._panel_card is not None:
            self._panel_card.setFixedWidth(_panel_width_px(dp, self._effective_zoom(dp)))
        self._emit_structure()

    def _build_widget(self, spec: dict[str, Any], cols: int, zoom: float = 1.0) -> QWidget:
        wtype = spec.get("type", "tap")
        wid = str(spec.get("id", ""))
        btn_h = max(32, int(36 * zoom))
        btn_pad = max(6, int(8 * zoom))

        if wtype in ("label", "text"):
            from studio.ui.panel_widget_factory import build_design_preview

            preview = build_design_preview(spec)
            if preview is not None:
                return preview

        if wtype == "input":
            host = QWidget()
            wrap = QVBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            wrap.setSpacing(4)
            if spec.get("label"):
                lbl = QLabel(spec["label"])
                lbl.setWordWrap(True)
                wrap.addWidget(lbl)
            edit = QLineEdit()
            edit.setPlaceholderText(spec.get("placeholder", ""))
            edit.setText(PanelState.get(wid) or spec.get("default", ""))

            def apply_validation_style() -> None:
                err = validate_widget_value(spec, edit.text())
                if err:
                    edit.setStyleSheet("border: 1px solid #DC2626; border-radius: 4px;")
                else:
                    edit.setStyleSheet("")

            if wid:

                def on_text(t, i=wid, s=spec):
                    PanelState.set(i, t)
                    apply_validation_style()
                    self._emit_values()

                edit.textChanged.connect(on_text)
                edit.editingFinished.connect(apply_validation_style)
            apply_validation_style()
            wrap.addWidget(edit)
            return host

        if wtype in ("select",):
            host = QWidget()
            wrap = QVBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            if spec.get("label"):
                lbl = QLabel(spec["label"])
                lbl.setWordWrap(True)
                wrap.addWidget(lbl)
            cb = QComboBox()
            opts = [str(o) for o in (spec.get("options") or ["选项1", "选项2"])]
            cb.addItems(opts)
            cur = PanelState.get(wid) or str(spec.get("default", ""))
            idx = cb.findText(cur)
            if idx >= 0:
                cb.setCurrentIndex(idx)
            if wid:
                cb.currentTextChanged.connect(
                    lambda t, i=wid: (PanelState.set(i, t), self._emit_values())
                )
            wrap.addWidget(cb)
            return host

        if wtype == "radio":
            host = QWidget()
            wrap = QVBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            if spec.get("label"):
                lbl = QLabel(spec["label"])
                lbl.setWordWrap(True)
                wrap.addWidget(lbl)
            group = QButtonGroup(host)
            cur = PanelState.get(wid) or str(spec.get("default", ""))
            for i, opt in enumerate(spec.get("options") or ["A", "B"]):
                rb = QRadioButton(str(opt))
                if str(opt) == cur or (not cur and i == 0):
                    rb.setChecked(True)
                group.addButton(rb)
                wrap.addWidget(rb)

            def on_radio(_btn, i=wid, g=group):
                for b in g.buttons():
                    if b.isChecked():
                        PanelState.set(i, b.text())
                        self._emit_values()
                        break

            group.buttonClicked.connect(on_radio)
            if wid and not PanelState.get(wid):
                for b in group.buttons():
                    if b.isChecked():
                        PanelState.set(wid, b.text())
                        break
            return host

        if wtype == "multiselect":
            host = QWidget()
            wrap = QHBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            wrap.setSpacing(12)
            if spec.get("label"):
                lbl = QLabel(spec["label"])
                lbl.setWordWrap(True)
                wrap.addWidget(lbl)
            selected = {
                x.strip()
                for x in (PanelState.get(wid) or str(spec.get("default", ""))).split(",")
                if x.strip()
            }

            def sync_multi(i=wid, boxes=None):
                if not i or boxes is None:
                    return
                val = ",".join(b.text() for b in boxes if b.isChecked())
                PanelState.set(i, val)
                self._emit_values()

            boxes: list[QCheckBox] = []
            for opt in spec.get("options") or ["A", "B"]:
                c = QCheckBox(str(opt))
                c.setChecked(str(opt) in selected)
                c.stateChanged.connect(lambda _s, i=wid, bs=boxes: sync_multi(i, bs))
                boxes.append(c)
                wrap.addWidget(c)
            wrap.addStretch(1)
            sync_multi(wid, boxes)
            return host

        if wtype == "switch":
            from studio.ui.panel_widget_factory import _make_switch

            host = QWidget()
            wrap = QHBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            if spec.get("label"):
                lbl = QLabel(spec["label"])
                lbl.setWordWrap(True)
                wrap.addWidget(lbl, 1)
            cur = (PanelState.get(wid) or str(spec.get("default", "false"))).lower()
            sw = _make_switch(checked=cur in ("true", "1", "yes", "on"), enabled=True)
            if wid:
                sw.toggled.connect(
                    lambda on, i=wid: (
                        PanelState.set(i, "true" if on else "false"),
                        self._emit_values(),
                    )
                )
            wrap.addWidget(sw)
            return host

        if wtype == "time_range":
            host = QWidget()
            wrap = QVBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            if spec.get("label"):
                lbl = QLabel(spec["label"])
                lbl.setWordWrap(True)
                wrap.addWidget(lbl)
            row = QHBoxLayout()
            start = QLineEdit()
            end = QLineEdit()
            start.setPlaceholderText("09:00")
            end.setPlaceholderText("18:00")
            raw = PanelState.get(wid) or str(spec.get("default", ""))
            if raw and "-" in raw:
                a, b = raw.split("-", 1)
                start.setText(a.strip())
                end.setText(b.strip())
            else:
                start.setText(str(spec.get("default_start", "09:00")))
                end.setText(str(spec.get("default_end", "18:00")))

            def sync_range(i=wid, s=start, e=end):
                val = f"{s.text().strip()}-{e.text().strip()}"
                PanelState.set(i, val)
                self._emit_values()

            if wid:
                start.textChanged.connect(lambda _t: sync_range())
                end.textChanged.connect(lambda _t: sync_range())
            row.addWidget(QLabel("从"))
            row.addWidget(start, 1)
            row.addWidget(QLabel("到"))
            row.addWidget(end, 1)
            wrap.addLayout(row)
            if wid and not PanelState.get(wid):
                sync_range()
            return host

        if wtype == "slider":
            host = QWidget()
            wrap = QVBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            if spec.get("label"):
                wrap.addWidget(QLabel(spec["label"]))
            from PySide6.QtWidgets import QSlider

            slider = QSlider(Qt.Orientation.Horizontal)
            min_v = int(spec.get("min", 0))
            max_v = int(spec.get("max", 100))
            step = int(spec.get("step", 1) or 1)
            slider.setMinimum(min_v)
            slider.setMaximum(max_v)
            slider.setSingleStep(step)
            cur = int(PanelState.get(wid) or spec.get("default", min_v) or min_v)
            slider.setValue(max(min_v, min(max_v, cur)))
            if wid:
                slider.valueChanged.connect(
                    lambda v, i=wid: (PanelState.set(i, str(v)), self._emit_values())
                )
                PanelState.set(wid, str(slider.value()))
            wrap.addWidget(slider)
            return host

        if wtype == "stepper":
            host = QWidget()
            row = QHBoxLayout(host)
            row.setContentsMargins(0, 0, 0, 0)
            if spec.get("label"):
                row.addWidget(QLabel(spec["label"]))
            min_v = int(spec.get("min", 0))
            max_v = int(spec.get("max", 99))
            step = int(spec.get("step", 1) or 1)
            val_lbl = QLabel()
            state = {"v": int(PanelState.get(wid) or spec.get("default", min_v) or min_v)}

            def render():
                state["v"] = max(min_v, min(max_v, state["v"]))
                val_lbl.setText(str(state["v"]))
                if wid:
                    PanelState.set(wid, str(state["v"]))

            minus = QPushButton("−")
            plus = QPushButton("+")
            minus.clicked.connect(lambda: (state.update(v=state["v"] - step), render(), self._emit_values()))
            plus.clicked.connect(lambda: (state.update(v=state["v"] + step), render(), self._emit_values()))
            render()
            row.addWidget(minus)
            row.addWidget(val_lbl, 1)
            row.addWidget(plus)
            return host

        if wtype == "textarea":
            host = QWidget()
            wrap = QVBoxLayout(host)
            wrap.setContentsMargins(0, 0, 0, 0)
            if spec.get("label"):
                wrap.addWidget(QLabel(spec["label"]))
            edit = QTextEdit()
            edit.setPlainText(PanelState.get(wid) or spec.get("default", ""))
            edit.setMaximumHeight(int(spec.get("rows", 3)) * 24)
            if wid:
                edit.textChanged.connect(
                    lambda i=wid, e=edit: (
                        PanelState.set(i, e.toPlainText()),
                        self._emit_values(),
                    )
                )
            wrap.addWidget(edit)
            return host

        if wtype == "divider":
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("color: #E2E8F0;")
            return line

        if wtype == "tabs":
            tabs = QTabWidget()
            tabs.setDocumentMode(True)
            tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            for tab in spec.get("tabs") or []:
                page = QWidget()
                tab_grid_host = QWidget()
                tab_grid = QGridLayout(tab_grid_host)
                tab_grid.setContentsMargins(0, 0, 0, 0)
                tab_grid.setHorizontalSpacing(8)
                tab_grid.setVerticalSpacing(8)
                self._fill_grid(tab.get("widgets") or [], tab_grid, cols, (), tab_grid_host, zoom)
                page_layout = QVBoxLayout(page)
                page_layout.setContentsMargins(0, 0, 0, 0)
                page_layout.addWidget(tab_grid_host)
                tabs.addTab(page, tab.get("title", "页签"))
            return tabs

        if is_action_type(wtype):
            btn = QPushButton(spec.get("label", "按钮"))
            color = spec.get("color", "#2563EB")
            btn.setStyleSheet(
                f"background-color:{color}; color:white; border-radius:8px;"
                f" padding:{btn_pad}px {btn_pad - 2}px; font-size:{max(12, int(13 * zoom))}px;"
            )
            btn.setMinimumHeight(btn_h)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if self._design_mode:
                btn.setEnabled(True)
            else:
                btn.setEnabled(False)
            return btn

        return QLabel(f"未知: {wtype}")
