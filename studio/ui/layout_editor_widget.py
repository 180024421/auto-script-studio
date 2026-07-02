"""浮动面板布局编辑器 — 支持多控件类型与 WYSIWYG 预览。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, Signal, QTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from studio.runtime.panel_state import PanelState
from studio.ui.app_theme import set_button_role
from studio.ui.layout_preview_widget import LayoutPreviewWidget
from studio.ui.phone_canvas_widget import PhoneCanvasWidget
from studio.ui.page_shell import (
    card_frame,
    section_title,
    side_column,
    three_column_splitter,
    tool_button_row,
)
from studio.ui.screen_tabs_editor import ScreenTabsEditor
from studio.services.layout_history import LayoutHistory
from studio.services.layout_validate import validate_layout
from studio.services.layout_templates import get_template, template_choices
from studio.services.free_layout import estimate_text_layout_width, is_free_mode
from studio.services.screen_layout import (
    CHROME_PATH_TAG,
    active_screen_index,
    active_screen_widgets,
    chrome_widgets,
    ensure_migrated,
    export_screen_dict,
    import_screen_dict,
    migrate_layout,
    repair_screen_widgets,
    repair_all_screens,
    resolve_widget,
    screens,
)
from studio.services.layout_defaults import (
    ACTION_TYPES,
    action_types_for_layout,
    DEFAULT_LAYOUT,
    FORM_WIDGET_TYPES,
    PANEL_THEMES,
    default_widget,
    is_action_type,
    is_form_type,
    load_layout,
    save_layout,
    widget_display_name,
)


class LayoutEditorWidget(QWidget):
    layout_changed = Signal(dict)
    request_pick_mode = Signal(str)
    insert_lua = Signal(str)

    def __init__(self, project_dir_getter: Callable[[], Optional[str]]) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self._layout = migrate_layout(json.loads(json.dumps(DEFAULT_LAYOUT)))
        self._dirty = False
        self._selected_path: tuple[int, ...] = ()
        self._history = LayoutHistory()
        self._clipboard_widget: dict | None = None
        self._loading_form = False

        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(0, 0, 0, 0)

        header, header_lay = card_frame(compact=True)
        top = QHBoxLayout()
        top.setSpacing(8)
        header_lay.addLayout(top)
        self.enabled_cb = QComboBox()
        self.enabled_cb.addItems(["启用浮动面板", "禁用浮动面板"])
        top.addWidget(self.enabled_cb)
        self.theme_combo = QComboBox()
        for tid, label in PANEL_THEMES:
            self.theme_combo.addItem(label, tid)
        top.addWidget(QLabel("布局"))
        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem("手机自由", "free")
        self.layout_mode_combo.addItem("网格", "grid")
        self.layout_mode_combo.currentIndexChanged.connect(self._on_layout_mode_changed)
        top.addWidget(self.layout_mode_combo)
        top.addWidget(QLabel("主题"))
        top.addWidget(self.theme_combo)
        top.addWidget(QLabel("标题"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("面板标题")
        top.addWidget(self.title_edit, 1)
        self._lbl_cols = QLabel("列")
        top.addWidget(self._lbl_cols)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 3)
        self.cols_spin.setValue(2)
        top.addWidget(self.cols_spin)
        self.width_dp_spin = QSpinBox()
        self.width_dp_spin.setRange(160, 360)
        self.width_dp_spin.setValue(220)
        self._lbl_width = QLabel("宽dp")
        top.addWidget(self._lbl_width)
        top.addWidget(self.width_dp_spin)
        self._grid_header_widgets = [self._lbl_cols, self.cols_spin, self._lbl_width, self.width_dp_spin]
        self.start_x_spin = QSpinBox()
        self.start_y_spin = QSpinBox()
        for sp in (self.start_x_spin, self.start_y_spin):
            sp.setRange(0, 4096)
        top.addWidget(QLabel("X"))
        top.addWidget(self.start_x_spin)
        top.addWidget(QLabel("Y"))
        top.addWidget(self.start_y_spin)
        self.allow_design_cb = QCheckBox("实机可设计")
        self.allow_design_cb.setChecked(True)
        self.allow_design_cb.setToolTip("APK 浮动面板长按标题栏 1.2 秒进入布局设计模式")
        top.addWidget(self.allow_design_cb)
        self.start_confirm_cb = QCheckBox("开始需二次确认")
        self.start_confirm_cb.setChecked(True)
        self.start_confirm_cb.setToolTip("点「开始」先收起为悬浮球，再点绿色悬浮球才真正运行脚本")
        top.addWidget(self.start_confirm_cb)
        root.addWidget(header)

        # —— 左：添加控件 + 标签页 + 列表（可滚动） ——
        left_card, left_card_lay = side_column(300, None)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_inner = QWidget()
        left_layout = QVBoxLayout(left_inner)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        left_layout.addWidget(section_title("添加控件"))
        add_menu = self._build_add_menu()
        add_main_btn = QPushButton("＋ 添加控件")
        set_button_role(add_main_btn, "accent")
        add_main_btn.setMinimumHeight(36)
        add_main_btn.setMenu(add_menu)
        add_main_btn.setToolTip("向当前界面标签页内添加表单或动作控件")
        left_layout.addWidget(add_main_btn)

        quick_hint = QLabel("快捷：")
        quick_hint.setObjectName("HintLabel")
        left_layout.addWidget(quick_hint)
        quick_row = QHBoxLayout()
        quick_row.setSpacing(6)
        for t, desc in [("text", "文字框"), ("input", "输入框"), ("select", "下拉"), ("switch", "开关")]:
            b = QPushButton(desc)
            set_button_role(b, "ghost")
            b.setMinimumHeight(30)
            b.clicked.connect(lambda _c=False, wt=t: self.add_widget(wt))
            quick_row.addWidget(b)
        left_layout.addLayout(quick_row)

        self.screen_tabs_editor = ScreenTabsEditor(self._on_screens_changed)
        left_layout.addWidget(self.screen_tabs_editor)

        left_layout.addWidget(section_title("当前界面控件"))
        self.widget_list = QListWidget()
        self.widget_list.currentRowChanged.connect(self._on_select_widget)
        left_layout.addWidget(self.widget_list, 1)

        tool_button_row(
            left_layout,
            [
                ("撤销", self._undo_layout, "ghost"),
                ("重做", self._redo_layout, "ghost"),
                ("复制", self._copy_widget, "ghost"),
                ("粘贴", self._paste_widget, "ghost"),
            ],
            columns=2,
        )

        tool_button_row(
            left_layout,
            [
                ("删除", self.remove_widget, "danger"),
                ("上移", lambda: self._move_widget(-1), "ghost"),
                ("下移", lambda: self._move_widget(1), "ghost"),
            ],
            columns=2,
        )

        tool_button_row(
            left_layout,
            [
                ("加载", self.load_from_project, "ghost"),
                ("保存", self.save_to_project, "primary"),
                ("导出界面", self.export_active_screen, "ghost"),
                ("导入界面", self.import_screen, "ghost"),
            ],
            columns=2,
        )
        tool_button_row(
            left_layout,
            [
                ("模板", self.apply_template, "accent"),
                ("恢复默认", self.reset_default, "ghost"),
            ],
            columns=2,
        )

        left_scroll.setWidget(left_inner)
        left_card_lay.addWidget(left_scroll)

        # —— 中：预览主区（无额外卡片边距，尽量留给画布） ——
        center_wrap = QWidget()
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

        preview_add_btn = QPushButton("添加控件")
        set_button_role(preview_add_btn, "accent")
        preview_add_btn.setMinimumHeight(30)
        preview_add_btn.setMenu(self._build_add_menu())
        preview_add_btn.setToolTip("向当前界面添加控件（与左侧「＋ 添加控件」相同）")
        preview_header.addWidget(preview_add_btn)

        preview_header.addWidget(QLabel("缩放"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItem("适应宽度", None)
        for label, val in [("150%", 1.5), ("175%", 1.75), ("200%", 2.0), ("250%", 2.5)]:
            self.zoom_combo.addItem(label, val)
        self.zoom_combo.setCurrentIndex(0)
        self.zoom_combo.setToolTip("适应宽度：按中间区域自动放大；固定比例仅影响 PC 预览")
        self.zoom_combo.currentIndexChanged.connect(self._on_preview_zoom_changed)
        preview_header.addWidget(self.zoom_combo)

        self.values_label = QLabel()
        self.values_label.setObjectName("InfoBar")
        self.values_label.setWordWrap(False)
        self.values_label.setMaximumHeight(26)
        preview_header.addWidget(self.values_label, 1)

        snippet_btn = QPushButton("Lua 示例")
        set_button_role(snippet_btn, "ghost")
        snippet_btn.setToolTip("插入 panel Lua 示例到脚本")
        snippet_btn.clicked.connect(self._insert_panel_lua_example)
        preview_header.addWidget(snippet_btn)
        center_layout.addLayout(preview_header)

        self.canvas_stack = QStackedWidget()
        self.phone_canvas = PhoneCanvasWidget()
        self.phone_canvas.setMinimumHeight(480)
        self.preview = LayoutPreviewWidget()
        self.preview.setMinimumHeight(420)
        self.canvas_stack.addWidget(self.phone_canvas)
        self.canvas_stack.addWidget(self.preview)
        center_layout.addWidget(self.canvas_stack, 1)

        # —— 右：属性表单（可滚动） ——
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

        form_box.setMinimumWidth(400)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setObjectName("PropertyScroll")
        form_scroll.setMinimumWidth(420)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        form_scroll.setWidget(form_box)

        self.preview.set_zoom_auto(True)
        root.addWidget(three_column_splitter(left_card, center_wrap, form_scroll, sizes=(300, 680, 420)), 1)

        self.phone_canvas.layout_changed.connect(self._on_phone_structure_changed)
        self.phone_canvas.widget_selected.connect(self._on_preview_widget_selected)
        self.phone_canvas.screen_changed.connect(self._on_canvas_screen_changed)
        self.phone_canvas.nudge_selected.connect(self._on_nudge_selected)
        self.phone_canvas.delete_selected.connect(self._on_delete_selected)
        self.phone_canvas.duplicate_selected.connect(self._duplicate_widget)
        self.phone_canvas.values_changed.connect(self._refresh_value_summary)
        self.phone_canvas.context_menu_requested.connect(self._show_canvas_context_menu)
        self.preview.values_changed.connect(self._refresh_value_summary)
        self.preview.widget_selected.connect(self._on_preview_widget_selected)
        self.preview.structure_changed.connect(self._on_preview_structure_changed)
        PanelState.add_listener(self._refresh_value_summary)

        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        for w in (self.title_edit, self.color_edit, self.id_edit, self.label_edit, self.text_edit,
                  self.placeholder_edit, self.default_edit):
            w.textChanged.connect(self._sync_form_to_layout)
        self.text_style_combo.currentIndexChanged.connect(self._sync_form_to_layout)
        self.width_spin.valueChanged.connect(self._sync_form_to_layout)
        for sp in (self.x_spin, self.y_spin, self.x1_spin, self.y1_spin, self.x2_spin, self.y2_spin):
            sp.valueChanged.connect(self._sync_form_to_layout)
        self.start_x_spin.valueChanged.connect(self._sync_panel_position)
        self.start_y_spin.valueChanged.connect(self._sync_panel_position)
        self.lua_edit.textChanged.connect(self._sync_form_to_layout)
        self.options_edit.textChanged.connect(self._sync_form_to_layout)
        self.min_edit.textChanged.connect(self._sync_form_to_layout)
        self.max_edit.textChanged.connect(self._sync_form_to_layout)
        self.required_cb.toggled.connect(self._sync_form_to_layout)
        self.switch_default_cb.toggled.connect(self._sync_form_to_layout)
        self.time_start_edit.timeChanged.connect(self._sync_form_to_layout)
        self.time_end_edit.timeChanged.connect(self._sync_form_to_layout)
        self.enabled_cb.currentIndexChanged.connect(self._on_header_changed)
        self.theme_combo.currentIndexChanged.connect(self._on_header_changed)
        self.cols_spin.valueChanged.connect(self._on_header_changed)
        self.width_dp_spin.valueChanged.connect(self._on_header_changed)
        self.allow_design_cb.toggled.connect(self._on_header_changed)
        for sp in (self.layout_x_spin, self.layout_y_spin, self.layout_w_spin, self.layout_h_spin):
            sp.valueChanged.connect(self._sync_form_to_layout)
        # layout_mode 由 _on_layout_mode_changed 单独处理，避免重复 rebuild

        self.start_confirm_cb.toggled.connect(self._on_header_changed)

        self.layout_mode_combo.blockSignals(True)
        mode_idx = self.layout_mode_combo.findData(self._layout.get("panel", {}).get("layout_mode", "free"))
        self.layout_mode_combo.setCurrentIndex(max(0, mode_idx))
        self.layout_mode_combo.blockSignals(False)
        self._sync_canvas_mode()
        self._refresh_ui()
        self._commit_history()

    def _on_interactive_preview_toggled(self, checked: bool) -> None:
        self.phone_canvas.set_interactive_preview(checked)

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
        menu.exec(global_pos)

    def _on_layout_mode_changed(self, _index: int = 0) -> None:
        self._apply_header()
        self._dirty = True
        self._sync_canvas_mode()
        self._emit_layout_changed()

    def _sync_canvas_mode(self) -> None:
        free = is_free_mode(self._layout)
        self.canvas_stack.setCurrentIndex(0 if free else 1)
        self.design_mode_cb.setVisible(not free)
        self.zoom_combo.setVisible(not free)
        self.interactive_preview_cb.setVisible(free)
        if not free:
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
        """画布拖动/缩放后，仅合并坐标，不覆盖 screens 控件列表。"""
        if not is_free_mode(self._layout):
            self._layout = migrate_layout(layout)
            self._refresh_widget_list(keep_row=True)
            self._dirty = True
            self._emit_layout_changed()
            return
        incoming = migrate_layout(layout)
        self._apply_canvas_layout_patch(incoming)
        self._refresh_widget_list(keep_row=True)
        if self._selected_path:
            w = resolve_widget(self._layout, self._selected_path)
            if w is not None:
                self._load_widget_into_form(w)
        self._dirty = True
        self._emit_layout_changed()

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
        self._layout.setdefault("panel", {})["active_screen"] = idx
        self.screen_tabs_editor.set_active_index(idx)
        self._selected_path = ()
        self._refresh_widget_list()
        self._clear_form()
        self._dirty = True
        self._emit_layout_changed()

    def _on_screens_changed(self) -> None:
        # screens[] 已与 layout 共享引用，仅同步当前界面索引
        self._layout.setdefault("panel", {})["active_screen"] = self.screen_tabs_editor.active_index()
        self._selected_path = ()
        self._refresh_widget_list()
        self._clear_form()
        self._update_preview(force=True)
        self._dirty = True
        self._emit_layout_changed()

    def _refresh_widget_list(self, *, keep_row: bool = False, select_row: int | None = None) -> None:
        row = self.widget_list.currentRow() if keep_row else -1
        if select_row is not None:
            row = select_row
        self.widget_list.blockSignals(True)
        self.widget_list.clear()
        for w in self._widgets():
            self.widget_list.addItem(QListWidgetItem(widget_display_name(w)))
        self.widget_list.blockSignals(False)
        if 0 <= row < self.widget_list.count():
            self.widget_list.setCurrentRow(row)
        elif self.widget_list.count() and not keep_row and select_row is None:
            self.widget_list.setCurrentRow(0)

    def _on_design_mode_toggled(self, checked: bool) -> None:
        self.preview.set_design_mode(checked)

    def _on_preview_zoom_changed(self, _index: int = 0) -> None:
        data = self.zoom_combo.currentData()
        if data is None:
            self.preview.set_zoom_auto(True)
        else:
            self.preview.set_preview_zoom(float(data))

    def _select_widget_path(self, path: tuple[int, ...]) -> None:
        if not path:
            return
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
                    self.phone_canvas.set_selected_path(path)
                return
            act = active_screen_index(self._layout)
            if screen_idx != act:
                self._layout.setdefault("panel", {})["active_screen"] = screen_idx
                self.screen_tabs_editor.set_active_index(screen_idx)
                self._refresh_widget_list()
                payload = json.loads(json.dumps(self._layout))
                self.phone_canvas.set_layout(payload)
            self.widget_list.blockSignals(True)
            if 0 <= widget_idx < self.widget_list.count():
                self.widget_list.setCurrentRow(widget_idx)
            self.widget_list.blockSignals(False)
            w = resolve_widget(self._layout, path)
            if w:
                self._selected_path = path
                self._load_widget_into_form(w)
                self.phone_canvas.set_selected_path(path)
            return
        if len(path) == 1:
            self.widget_list.blockSignals(True)
            self.widget_list.setCurrentRow(path[0])
            self.widget_list.blockSignals(False)
            self._on_select_widget(path[0])

    def _on_preview_widget_selected(self, path: tuple) -> None:
        if isinstance(path, tuple):
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
        self._dirty = True
        self._emit_layout_changed()

    def apply_template(self) -> None:
        choices = template_choices()
        if not choices:
            return
        labels = [c[1] for c in choices]
        keys = [c[0] for c in choices]
        label, ok = QInputDialog.getItem(self, "套用布局模板", "选择模板:", labels, 0, False)
        if not ok:
            return
        key = keys[labels.index(label)]
        tpl = get_template(key)
        if not tpl:
            return
        mode, ok2 = QInputDialog.getItem(
            self, "套用方式", "如何套用模板？", ["替换全部控件", "追加到末尾"], 0, False
        )
        if not ok2:
            return
        if mode == "替换全部控件":
            self._layout = migrate_layout(json.loads(json.dumps(tpl)))
        else:
            panel = self._layout.setdefault("panel", {})
            panel.update(tpl.get("panel", {}))
            self._layout["enabled"] = tpl.get("enabled", True)
            if is_free_mode(self._layout):
                active_screen_widgets(self._layout).extend(
                    json.loads(json.dumps(tpl.get("widgets", [])))
                )
            else:
                self._layout.setdefault("widgets", []).extend(
                    json.loads(json.dumps(tpl.get("widgets", [])))
                )
        self._refresh_ui()
        self._dirty = True
        self._emit_layout_changed()

    def _build_add_menu(self) -> QMenu:
        menu = QMenu(self)
        sub_form = menu.addMenu("表单控件")
        for t, desc in FORM_WIDGET_TYPES:
            if t == "tabs":
                continue
            sub_form.addAction(desc, lambda _c=False, wt=t: self.add_widget(wt))
        sub_act = menu.addMenu("动作按钮")
        for t, desc in action_types_for_layout(self._layout):
            sub_act.addAction(desc, lambda _c=False, wt=t: self.add_widget(wt))
        return menu

    def _widgets(self) -> list:
        ensure_migrated(self._layout)
        if is_free_mode(self._layout):
            return active_screen_widgets(self._layout)
        return self._layout.setdefault("widgets", [])

    def _chrome_widgets(self) -> list:
        ensure_migrated(self._layout)
        return chrome_widgets(self._layout)

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

    def load_from_project(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return
        self._layout = load_layout(project)
        self._history.clear()
        self._refresh_ui()
        self._commit_history()
        self._dirty = False

    def save_to_project(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return
        self._apply_header()
        self._sync_form_to_layout()
        errors = validate_layout(self._layout)
        if errors:
            QMessageBox.warning(self, "布局校验", "\n".join(errors[:10]))
            return
        save_layout(project, self._layout)
        self._dirty = False
        self.layout_changed.emit(json.loads(json.dumps(self._layout)))
        QMessageBox.information(self, "完成", "已保存 ui/layout.json")

    def _commit_history(self) -> None:
        self._history.push(self._layout)

    def _apply_layout_snapshot(self, snap: dict) -> None:
        self._layout = json.loads(json.dumps(snap))
        self._selected_path = ()
        self._refresh_ui()
        self._dirty = True
        self._emit_layout_changed()

    def _undo_layout(self) -> None:
        snap = self._history.undo(self._layout)
        if snap:
            self._apply_layout_snapshot(snap)

    def _redo_layout(self) -> None:
        snap = self._history.redo()
        if snap:
            self._apply_layout_snapshot(snap)

    def _copy_widget(self) -> None:
        target = self._edit_target()
        if not target:
            return
        w, _, _ = target
        self._clipboard_widget = json.loads(json.dumps(w))

    def _paste_widget(self) -> None:
        if not self._clipboard_widget:
            return
        src = json.loads(json.dumps(self._clipboard_widget))
        widgets = self._widgets()
        w = default_widget(str(src.get("type", "label")), len(widgets) + 1)
        w.update({k: v for k, v in src.items() if k != "id"})
        w["id"] = f"{src.get('id', 'w')}_{len(widgets) + 1}"
        w["layout_y"] = int(w.get("layout_y", 40)) + 72
        widgets.append(w)
        row = len(widgets) - 1
        self._selected_path = (active_screen_index(self._layout), row)
        self._commit_history()
        self._refresh_widget_list()
        self.widget_list.setCurrentRow(row)
        self._load_widget_into_form(widgets[row])
        self._dirty = True
        self._update_preview(force=True)

    def _duplicate_widget(self) -> None:
        self._copy_widget()
        self._paste_widget()

    def _on_nudge_selected(self, dx: int, dy: int) -> None:
        if not self._selected_path or len(self._selected_path) != 2:
            return
        from studio.services.screen_layout import set_widget_rect

        w = resolve_widget(self._layout, self._selected_path)
        if w is None:
            return
        set_widget_rect(
            self._layout,
            self._selected_path,
            int(w.get("layout_x", 0)) + dx,
            int(w.get("layout_y", 0)) + dy,
            int(w.get("layout_w", 200)),
            int(w.get("layout_h", 48)),
        )
        self._load_widget_into_form(w)
        self._update_preview(force=True)
        self._dirty = True
        self._emit_layout_changed()

    def _on_delete_selected(self) -> None:
        if self._selected_path and len(self._selected_path) == 2:
            screen_idx, widget_idx = self._selected_path
            if screen_idx == CHROME_PATH_TAG:
                cw = self._chrome_widgets()
                if 0 <= widget_idx < len(cw):
                    cw.pop(widget_idx)
            else:
                ws = active_screen_widgets(self._layout)
                if 0 <= widget_idx < len(ws):
                    ws.pop(widget_idx)
        else:
            self.remove_widget()
            return
        self._selected_path = ()
        self._sync_screen_tabs_from_layout()
        self._commit_history()
        self._refresh_widget_list()
        if self.widget_list.count():
            self.widget_list.setCurrentRow(0)
            self._on_select_widget(0)
        else:
            self._clear_form()
        self._update_preview(force=True)
        self._dirty = True
        self._emit_layout_changed()

    def save_if_dirty(self) -> bool:
        if not self._dirty:
            return False
        project = self._project_dir_getter()
        if not project:
            return False
        if self.widget_list.currentRow() >= 0:
            self._sync_form_to_layout()
        else:
            self._apply_header()
        save_layout(project, self._layout)
        self._dirty = False
        self.layout_changed.emit(json.loads(json.dumps(self._layout)))
        return True

    def add_widget(self, wtype: str) -> None:
        ensure_migrated(self._layout)
        if wtype == "stop_script" and is_free_mode(self._layout):
            QMessageBox.information(
                self,
                "提示",
                "手机自由布局不再使用「停止」按钮；脚本运行后请点右侧悬浮球 ■ 图标停止。",
            )
            return
        if is_action_type(wtype) and wtype in ("start_script", "stop_script"):
            widgets = self._chrome_widgets()
            widgets.append(default_widget(wtype, len(widgets) + 1))
            self._selected_path = (CHROME_PATH_TAG, len(widgets) - 1)
            w = widgets[-1]
            self._load_widget_into_form(w)
        else:
            widgets = self._widgets()
            w = default_widget(wtype, len(widgets) + 1)
            if widgets:
                bottom = max(
                    int(x.get("layout_y", 0) + x.get("layout_h", 56)) for x in widgets
                )
                w["layout_y"] = bottom + 16
            widgets.append(w)
            row = len(widgets) - 1
            self._selected_path = (active_screen_index(self._layout), row)
            repair_screen_widgets(widgets)
            self._sync_screen_tabs_from_layout()
            self._refresh_widget_list(select_row=row)
            self._load_widget_into_form(widgets[row])
        self._dirty = True
        self._update_preview(force=True)
        self._commit_history()
        self._emit_layout_changed()

    def _resolve_remove_row(self) -> int:
        row = self.widget_list.currentRow()
        if row >= 0:
            return row
        if self._selected_path and len(self._selected_path) == 2:
            screen_idx, widget_idx = self._selected_path
            if screen_idx != CHROME_PATH_TAG and screen_idx == active_screen_index(self._layout):
                return widget_idx
        return -1

    def remove_widget(self) -> None:
        row = self._resolve_remove_row()
        if row < 0:
            return
        widgets = self._widgets()
        if row >= len(widgets):
            return
        widgets.pop(row)
        self._selected_path = ()
        self._sync_screen_tabs_from_layout()
        self._refresh_widget_list()
        if self.widget_list.count():
            self.widget_list.setCurrentRow(min(row, self.widget_list.count() - 1))
            self._on_select_widget(self.widget_list.currentRow())
        else:
            self._clear_form()
        self._update_preview(force=True)
        self._dirty = True
        self._commit_history()
        self._emit_layout_changed()

    def reset_default(self) -> None:
        self._layout = json.loads(json.dumps(DEFAULT_LAYOUT))
        self._history.clear()
        self._refresh_ui()
        self._commit_history()
        self._dirty = True

    def _move_widget(self, delta: int) -> None:
        row = self.widget_list.currentRow()
        widgets = self._widgets()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= len(widgets):
            return
        widgets[row], widgets[new_row] = widgets[new_row], widgets[row]
        self._refresh_ui()
        self.widget_list.setCurrentRow(new_row)
        self._dirty = True

    def _apply_header(self) -> None:
        panel = self._layout.setdefault("panel", {})
        panel["title"] = self.title_edit.text().strip() or "脚本助手"
        panel["columns"] = self.cols_spin.value()
        panel["width_dp"] = self.width_dp_spin.value()
        panel["start_x"] = self.start_x_spin.value()
        panel["start_y"] = self.start_y_spin.value()
        panel["theme"] = self.theme_combo.currentData() or "light"
        panel["allow_design"] = self.allow_design_cb.isChecked()
        panel["start_confirm_collapse"] = self.start_confirm_cb.isChecked()
        panel["layout_mode"] = self.layout_mode_combo.currentData() or "free"
        panel["design_width"] = int(panel.get("design_width", 720))
        panel["design_height"] = int(panel.get("design_height", 1280))
        if is_free_mode(self._layout):
            panel["active_screen"] = self.screen_tabs_editor.active_index()
            self._layout["screens"] = json.loads(json.dumps(self.screen_tabs_editor.get_screens()))
        self._layout["enabled"] = self.enabled_cb.currentIndex() == 0

    def _on_header_changed(self, *_args) -> None:
        self._apply_header()
        self._update_preview()
        self._dirty = True
        self._emit_layout_changed()

    def _sync_panel_position(self, *_args) -> None:
        panel = self._layout.setdefault("panel", {})
        panel["start_x"] = self.start_x_spin.value()
        panel["start_y"] = self.start_y_spin.value()
        self._apply_header()
        self._emit_layout_changed()

    def _emit_layout_changed(self) -> None:
        self.layout_changed.emit(json.loads(json.dumps(self._layout)))

    def _refresh_ui(self) -> None:
        self._layout = migrate_layout(self._layout)
        if is_free_mode(self._layout):
            repair_all_screens(self._layout)
        panel = self._layout.get("panel", {})
        self.enabled_cb.setCurrentIndex(0 if self._layout.get("enabled", True) else 1)
        theme_idx = self.theme_combo.findData(panel.get("theme", "light"))
        self.theme_combo.setCurrentIndex(max(0, theme_idx))
        self.title_edit.setText(panel.get("title", "脚本助手"))
        self.cols_spin.setValue(int(panel.get("columns", 2)))
        self.width_dp_spin.setValue(int(panel.get("width_dp", 220)))
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.start_x_spin.setValue(int(panel.get("start_x", 20)))
        self.start_y_spin.setValue(int(panel.get("start_y", 200)))
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        self.allow_design_cb.blockSignals(True)
        self.allow_design_cb.setChecked(panel.get("allow_design", True))
        self.allow_design_cb.blockSignals(False)
        self.start_confirm_cb.blockSignals(True)
        self.start_confirm_cb.setChecked(panel.get("start_confirm_collapse", True))
        self.start_confirm_cb.blockSignals(False)
        mode_idx = self.layout_mode_combo.findData(panel.get("layout_mode", "free"))
        self.layout_mode_combo.blockSignals(True)
        self.layout_mode_combo.setCurrentIndex(max(0, mode_idx))
        self.layout_mode_combo.blockSignals(False)
        if is_free_mode(self._layout):
            self._sync_screen_tabs_from_layout()
        self._refresh_widget_list()
        if self.widget_list.count():
            self.widget_list.setCurrentRow(0)
            self._on_select_widget(0)
        else:
            self._clear_form()
        self._sync_canvas_mode()

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
        form = self.findChild(QGroupBox, "")
        # toggle rows via widgets parent form — use stored row indices on form layout
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
        show_row(self._row_default, wtype in ("input", "select", "radio", "multiselect", "slider", "stepper", "textarea"))
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
        self._apply_header()
        if path[0] != CHROME_PATH_TAG and 0 <= row < self.widget_list.count():
            item = self.widget_list.item(row)
            if item:
                item.setText(widget_display_name(w))
        if is_free_mode(self._layout):
            sender = self.sender()
            geom_spin = sender in (
                self.layout_x_spin,
                self.layout_y_spin,
                self.layout_w_spin,
                self.layout_h_spin,
            )
            if geom_spin or sender in (self.text_edit, self.text_style_combo):
                self._update_preview()
        else:
            self._update_preview()
        self._dirty = True
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

    def _refresh_value_summary(self) -> None:
        self.values_label.setText(PanelState.format_summary())
        PanelState.save_sidecar(Path(self._project_dir_getter() or ".")) if self._project_dir_getter() else None

    def _qtime_from_str(self, text: str, fallback: str) -> QTime:
        for candidate in (text, fallback):
            parsed = QTime.fromString(candidate, "HH:mm")
            if parsed.isValid():
                return parsed
        return QTime(9, 0)

    def export_active_screen(self) -> None:
        if not is_free_mode(self._layout):
            QMessageBox.information(self, "提示", "仅「手机自由」布局支持导出界面")
            return
        from PySide6.QtWidgets import QFileDialog

        idx = active_screen_index(self._layout)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出当前界面",
            f"screen-{idx + 1}.json",
            "界面 JSON (*.json)",
        )
        if not path:
            return
        data = export_screen_dict(self._layout, idx)
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        QMessageBox.information(self, "完成", f"已导出界面「{data.get('title', '')}」")

    def import_screen(self) -> None:
        if not is_free_mode(self._layout):
            QMessageBox.information(self, "提示", "仅「手机自由」布局支持导入界面")
            return
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self, "导入界面", "", "界面 JSON (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        mode, ok = QInputDialog.getItem(
            self,
            "导入方式",
            "将界面",
            ["追加为新标签页", "替换当前界面"],
            0,
            False,
        )
        if not ok:
            return
        replace = mode == "替换当前界面"
        import_screen_dict(self._layout, data, replace=replace)
        self._commit_history()
        self._refresh_ui()
        self._dirty = True
        self._emit_layout_changed()

    def _insert_panel_lua_example(self) -> None:
        snippet = (
            "-- 浮动面板表单（控件 id 须与 layout.json 一致）\n"
            'local mode = panel.get("mode")\n'
            'bot.log("模式: " .. mode)\n\n'
            'if panel.is("mode", "极速") then\n'
            '  bot.log("走极速分支")\n'
            "end\n\n"
            'if panel.isOn("notify") then\n'
            '  bot.log("通知已开启")\n'
            "end\n\n"
            'local startT, endT = panel.getTimeRange("work_hours")\n'
            'bot.log("工作时段: " .. startT .. " - " .. endT)\n\n'
            'if panel.has("tasks", "日常") then\n'
            '  bot.log("已勾选日常")\n'
            "end\n\n"
            'panel.watch("mode", function(v)\n'
            '  bot.log("模式变为: " .. v)\n'
            "end)\n\n"
            'local snap = panel.snapshot()\n'
            'for k, v in pairs(snap) do bot.log(k .. "=" .. v) end\n\n'
            'local delay = tonumber(panel.get("delay_ms")) or 500\n'
            "bot.delay(delay / 1000)\n"
        )
        self.insert_lua.emit(snippet)

    def _update_preview(self, *, force: bool = False) -> None:
        self._apply_header()
        payload = json.loads(json.dumps(self._layout))
        if is_free_mode(self._layout):
            if not force and getattr(self.phone_canvas, "_layout", None):
                cur = json.dumps(migrate_layout(self.phone_canvas._layout), sort_keys=True)
                new = json.dumps(migrate_layout(payload), sort_keys=True)
                if cur == new and self.phone_canvas._items:
                    if self._selected_path:
                        self.phone_canvas.set_selected_path(self._selected_path)
                    self._refresh_value_summary()
                    return
            self.phone_canvas.set_layout(payload, selected_path=self._selected_path or None)
            if self._selected_path:
                self.phone_canvas.set_selected_path(self._selected_path)
        else:
            selected_path: tuple[int, ...] | None = None
            row = self.widget_list.currentRow()
            if row >= 0:
                selected_path = (row,)
            self.preview.set_layout(payload, selected_path=selected_path)
        self._refresh_value_summary()

    def on_project_opened(self) -> None:
        self.load_from_project()

    def set_panel_position(self, x: int, y: int) -> None:
        self.start_x_spin.blockSignals(True)
        self.start_y_spin.blockSignals(True)
        self.start_x_spin.setValue(x)
        self.start_y_spin.setValue(y)
        self.start_x_spin.blockSignals(False)
        self.start_y_spin.blockSignals(False)
        panel = self._layout.setdefault("panel", {})
        panel["start_x"] = x
        panel["start_y"] = y
        self._dirty = True
        self._emit_layout_changed()

    def fill_button_coords(self, x: int, y: int, mode: str) -> None:
        if mode == "tap":
            self.x_spin.setValue(x)
            self.y_spin.setValue(y)
            self.type_combo.setCurrentIndex(self.type_combo.findData("tap"))
        elif mode == "swipe1":
            self.x1_spin.setValue(x)
            self.y1_spin.setValue(y)
            self.type_combo.setCurrentIndex(self.type_combo.findData("swipe"))
        elif mode == "swipe2":
            self.x2_spin.setValue(x)
            self.y2_spin.setValue(y)
            self.type_combo.setCurrentIndex(self.type_combo.findData("swipe"))
        else:
            return
        self._sync_form_to_layout()
        self._dirty = True

    # 兼容旧信号名
    @property
    def btn_list(self) -> QListWidget:
        return self.widget_list
