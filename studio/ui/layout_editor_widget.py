"""浮动面板布局编辑器 — 支持多控件类型与 WYSIWYG 预览。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, Signal, QTimer
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
    QDialog,
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
from studio.ui.layout_editor_preview import LayoutEditorPreviewMixin
from studio.ui.layout_editor_property import LayoutEditorPropertyMixin
from studio.ui.page_shell import (
    card_frame,
    section_title,
    side_column,
    three_column_splitter,
    tool_button_row,
)
from studio.ui.screen_tabs_editor import ScreenTabsEditor
from studio.services.layout_history import LayoutHistory
from studio.services.layout_validate import is_auto_repairable, validate_layout
from studio.services.layout_templates import get_template, template_choices
from studio.services.layout_wizard_templates import build_wizard_layout, wizard_screen_for_append
from studio.ui.layout_wizard_dialog import LayoutWizardDialog
from studio.services.panel_lua_snippets import (
    lua_reads_block_for_layout,
    lua_reads_for_widget_spec,
    widget_lua_spec,
)
from studio.services.layout_clone import clone_layout, clone_list, clone_widget
from studio.services.free_layout import is_free_mode
from studio.services.screen_layout import (
    CHROME_PATH_TAG,
    active_screen_index,
    active_screen_widgets,
    chrome_widgets,
    editor_widget_list,
    ensure_migrated,
    export_screen_dict,
    import_screen_dict,
    migrate_layout,
    repair_screen_widgets,
    repair_all_screens,
    resolve_widget,
    screens,
)
from studio.services.layout_cleanup import next_widget_id, sanitize_free_layout
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


class LayoutEditorWidget(QWidget, LayoutEditorPreviewMixin, LayoutEditorPropertyMixin):
    layout_changed = Signal(dict)
    dirty_changed = Signal(bool)
    request_pick_mode = Signal(str)
    insert_lua = Signal(str)

    def __init__(self, project_dir_getter: Callable[[], Optional[str]]) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self._layout = migrate_layout(clone_layout(DEFAULT_LAYOUT))
        self._dirty = False
        self._selected_path: tuple[int, ...] = ()
        self._history = LayoutHistory()
        self._clipboard_widget: dict | None = None
        self._loading_form = False
        self._layout_emit_timer = QTimer(self)
        self._layout_emit_timer.setSingleShot(True)
        self._layout_emit_timer.setInterval(100)
        self._layout_emit_timer.timeout.connect(self._flush_layout_changed)
        panel0 = self._layout.get("panel", {})
        self._last_design_wh = (
            int(panel0.get("design_width", 720)),
            int(panel0.get("design_height", 1280)),
        )

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
        self.simple_mode_cb = QCheckBox("简易模式")
        self.simple_mode_cb.setChecked(True)
        self.simple_mode_cb.setToolTip("隐藏坐标、导出等专业项，只保留常用操作")
        self.simple_mode_cb.toggled.connect(self._on_simple_mode_toggled)
        top.addWidget(self.simple_mode_cb)
        top.addWidget(QLabel("标题"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("面板标题")
        top.addWidget(self.title_edit, 1)
        self.header_save_btn = QPushButton("保存")
        set_button_role(self.header_save_btn, "primary")
        self.header_save_btn.setMinimumHeight(34)
        self.header_save_btn.clicked.connect(self.save_to_project)
        top.addWidget(self.header_save_btn)
        self.header_load_btn = QPushButton("加载")
        set_button_role(self.header_load_btn, "ghost")
        self.header_load_btn.setMinimumHeight(34)
        self.header_load_btn.clicked.connect(self.load_from_project)
        top.addWidget(self.header_load_btn)

        self._header_adv_wrap = QWidget()
        header_adv = QHBoxLayout(self._header_adv_wrap)
        header_adv.setContentsMargins(0, 0, 0, 0)
        header_adv.setSpacing(8)
        self._lbl_layout_mode = QLabel("布局")
        header_adv.addWidget(self._lbl_layout_mode)
        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItem("手机自由", "free")
        self.layout_mode_combo.addItem("网格", "grid")
        self.layout_mode_combo.currentIndexChanged.connect(self._on_layout_mode_changed)
        header_adv.addWidget(self.layout_mode_combo)
        header_adv.addWidget(QLabel("主题"))
        self.theme_combo = QComboBox()
        for tid, label in PANEL_THEMES:
            self.theme_combo.addItem(label, tid)
        header_adv.addWidget(self.theme_combo)
        self._lbl_cols = QLabel("列")
        header_adv.addWidget(self._lbl_cols)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 3)
        self.cols_spin.setValue(2)
        header_adv.addWidget(self.cols_spin)
        self.width_dp_spin = QSpinBox()
        self.width_dp_spin.setRange(160, 360)
        self.width_dp_spin.setValue(220)
        self._lbl_width = QLabel("宽dp")
        header_adv.addWidget(self._lbl_width)
        header_adv.addWidget(self.width_dp_spin)
        self._grid_header_widgets = [self._lbl_cols, self.cols_spin, self._lbl_width, self.width_dp_spin]
        self.start_x_spin = QSpinBox()
        self.start_y_spin = QSpinBox()
        for sp in (self.start_x_spin, self.start_y_spin):
            sp.setRange(0, 4096)
        header_adv.addWidget(QLabel("X"))
        header_adv.addWidget(self.start_x_spin)
        header_adv.addWidget(QLabel("Y"))
        header_adv.addWidget(self.start_y_spin)
        self.allow_design_cb = QCheckBox("实机可设计")
        self.allow_design_cb.setChecked(True)
        self.allow_design_cb.setToolTip("APK 主页/悬浮窗长按标题栏 1.2 秒进入布局设计模式")
        header_adv.addWidget(self.allow_design_cb)
        self.start_confirm_cb = QCheckBox("开始需二次确认")
        self.start_confirm_cb.setChecked(True)
        self.start_confirm_cb.setToolTip("点「开始」先收起为悬浮球，再点绿色悬浮球才真正运行脚本")
        header_adv.addWidget(self.start_confirm_cb)
        top.addWidget(self._header_adv_wrap)
        root.addWidget(header)

        self.adv_header, adv_lay = card_frame(compact=True)
        adv_row = QHBoxLayout()
        adv_row.setSpacing(8)
        adv_lay.addLayout(adv_row)
        from studio.services.layout_defaults import PANEL_DISPLAY_MODES

        adv_row.addWidget(QLabel("展示"))
        self.display_mode_combo = QComboBox()
        for mode_id, mode_label in PANEL_DISPLAY_MODES:
            self.display_mode_combo.addItem(mode_label, mode_id)
        self.display_mode_combo.setToolTip("host=APK 主界面表单+固定启停；minimal=仅悬浮条；form 同 host")
        adv_row.addWidget(self.display_mode_combo)
        self.mode_hint_label = QLabel()
        self.mode_hint_label.setObjectName("InfoBar")
        adv_row.addWidget(self.mode_hint_label, 1)
        self.show_log_cb = QCheckBox("显示日志")
        self.show_on_launch_cb = QCheckBox("启动时显示")
        adv_row.addWidget(self.show_log_cb)
        adv_row.addWidget(self.show_on_launch_cb)
        adv_row.addWidget(QLabel("透明度"))
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(50, 100)
        self.opacity_spin.setSuffix("%")
        adv_row.addWidget(self.opacity_spin)
        adv_row.addWidget(QLabel("球大小"))
        self.ball_size_spin = QSpinBox()
        self.ball_size_spin.setRange(32, 72)
        self.ball_size_spin.setSuffix("dp")
        adv_row.addWidget(self.ball_size_spin)
        adv_row.addWidget(QLabel("设计宽"))
        self.design_width_spin = QSpinBox()
        self.design_width_spin.setRange(480, 1440)
        self.design_width_spin.setSuffix("px")
        adv_row.addWidget(self.design_width_spin)
        adv_row.addWidget(QLabel("设计高"))
        self.design_height_spin = QSpinBox()
        self.design_height_spin.setRange(480, 2560)
        self.design_height_spin.setSuffix("px")
        adv_row.addWidget(self.design_height_spin)
        root.addWidget(self.adv_header)

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

        workflow_hint = QLabel(
            "三步：① 从模板创建或添加控件  ② 右边改名称  ③ 保存\n"
            "排乱了？点「一键整理」；脚本用「插入面板读取」自动生成代码。"
        )
        workflow_hint.setObjectName("HintLabel")
        workflow_hint.setWordWrap(True)
        self.workflow_hint = workflow_hint
        left_layout.addWidget(workflow_hint)

        wizard_btn = QPushButton("从模板创建（推荐）")
        set_button_role(wizard_btn, "primary")
        wizard_btn.setMinimumHeight(38)
        wizard_btn.setToolTip("登录 / 运行 / 提醒 / 双列等现代自由布局，不用从零排版")
        wizard_btn.clicked.connect(self.open_layout_wizard)
        left_layout.addWidget(wizard_btn)

        left_layout.addWidget(section_title("添加控件"))
        add_menu = self._build_add_menu()
        add_main_btn = QPushButton("＋ 添加控件")
        set_button_role(add_main_btn, "accent")
        add_main_btn.setMinimumHeight(40)
        add_main_btn.setMenu(add_menu)
        add_main_btn.setToolTip("向当前页签添加输入框、下拉等（自动流式落行）")
        left_layout.addWidget(add_main_btn)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(6)
        for t, desc in [("section", "分区"), ("text", "说明"), ("input", "输入"), ("select", "下拉"), ("switch", "开关")]:
            b = QPushButton(desc)
            set_button_role(b, "ghost")
            b.setMinimumHeight(32)
            b.clicked.connect(lambda _c=False, wt=t: self.add_widget(wt))
            quick_row.addWidget(b)
        left_layout.addLayout(quick_row)

        self.screen_tabs_editor = ScreenTabsEditor(self._on_screens_changed)
        left_layout.addWidget(self.screen_tabs_editor)

        left_layout.addWidget(section_title("当前界面控件"))
        self.widget_list = QListWidget()
        self.widget_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.widget_list.currentRowChanged.connect(self._on_select_widget)
        left_layout.addWidget(self.widget_list, 1)

        tool_button_row(
            left_layout,
            [
                ("删除", self.remove_widget, "danger"),
                ("流式重排", self.reflow_layout_manual, "accent"),
            ],
            columns=2,
        )
        tool_button_row(
            left_layout,
            [
                ("左对齐", self.align_left_manual, "ghost"),
                ("统一宽度", self.unify_width_manual, "ghost"),
                ("两列并排", self.pair_columns_manual, "ghost"),
                ("一键整理", self.repair_layout_manual, "ghost"),
            ],
            columns=2,
        )

        self._left_more_btn = QPushButton("▸ 更多操作（撤销、移动、模板…）")
        set_button_role(self._left_more_btn, "ghost")
        self._left_more_btn.setMinimumHeight(32)
        self._left_more_btn.clicked.connect(self._toggle_left_more)
        left_layout.addWidget(self._left_more_btn)

        self._left_more_wrap = QWidget()
        more_layout = QVBoxLayout(self._left_more_wrap)
        more_layout.setContentsMargins(0, 0, 0, 0)
        more_layout.setSpacing(8)

        tool_button_row(
            more_layout,
            [
                ("撤销", self._undo_layout, "ghost"),
                ("重做", self._redo_layout, "ghost"),
                ("复制", self._copy_widget, "ghost"),
                ("粘贴", self._paste_widget, "ghost"),
            ],
            columns=2,
        )

        tool_button_row(
            more_layout,
            [
                ("上移", lambda: self._move_widget(-1), "ghost"),
                ("下移", lambda: self._move_widget(1), "ghost"),
            ],
            columns=2,
        )

        tool_button_row(
            more_layout,
            [
                ("加载", self.load_from_project, "ghost"),
                ("保存", self.save_to_project, "primary"),
                ("导出界面", self.export_active_screen, "ghost"),
                ("导入界面", self.import_screen, "ghost"),
            ],
            columns=2,
        )
        tool_button_row(
            more_layout,
            [
                ("旧版模板", self.apply_legacy_template, "ghost"),
                ("拉取实机", self.pull_device_layout, "ghost"),
                ("恢复默认", self.reset_default, "ghost"),
            ],
            columns=2,
        )
        left_layout.addWidget(self._left_more_wrap)
        self._left_more_expanded = False

        left_scroll.setWidget(left_inner)
        left_card_lay.addWidget(left_scroll)

        center_wrap = self._build_preview_column(add_menu)
        form_scroll = self._build_property_panel()

        root.addWidget(
            three_column_splitter(
                left_card,
                center_wrap,
                form_scroll,
                sizes=(280, 720, 380),
                mins=(260, 400, 300),
                stretches=(1, 4, 1),
            ),
            1,
        )

        self._wire_preview_signals()
        self._wire_property_signals()

        self.enabled_cb.currentIndexChanged.connect(self._on_header_changed)
        self.theme_combo.currentIndexChanged.connect(self._on_header_changed)
        self.cols_spin.valueChanged.connect(self._on_header_changed)
        self.width_dp_spin.valueChanged.connect(self._on_header_changed)
        self.allow_design_cb.toggled.connect(self._on_header_changed)
        # layout_mode 由 _on_layout_mode_changed 单独处理，避免重复 rebuild

        self.start_confirm_cb.toggled.connect(self._on_header_changed)
        self.display_mode_combo.currentIndexChanged.connect(self._on_display_mode_changed)
        self.show_log_cb.toggled.connect(self._on_header_changed)
        self.show_on_launch_cb.toggled.connect(self._on_header_changed)
        self.opacity_spin.valueChanged.connect(self._on_header_changed)
        self.ball_size_spin.valueChanged.connect(self._on_header_changed)
        self.design_width_spin.valueChanged.connect(self._on_header_changed)
        self.design_height_spin.valueChanged.connect(self._on_header_changed)

        self.layout_mode_combo.blockSignals(True)
        mode_idx = self.layout_mode_combo.findData(self._layout.get("panel", {}).get("layout_mode", "free"))
        self.layout_mode_combo.setCurrentIndex(max(0, mode_idx))
        self.layout_mode_combo.blockSignals(False)
        self._sync_canvas_mode()
        self._apply_simple_mode_ui()
        self._refresh_ui()
        self._commit_history()

    def _is_simple_mode(self) -> bool:
        return self.simple_mode_cb.isChecked()

    def _on_simple_mode_toggled(self, _checked: bool = False) -> None:
        self._left_more_expanded = False
        self._apply_simple_mode_ui()
        # 简易模式默认打开 APK 外壳预览，所见即打包主页
        if self._is_simple_mode() and hasattr(self, "apk_shell_preview_cb"):
            self.apk_shell_preview_cb.setChecked(True)

    def _toggle_left_more(self) -> None:
        self._left_more_expanded = not self._left_more_expanded
        self._left_more_wrap.setVisible(self._left_more_expanded)
        self._left_more_btn.setText(
            "▾ 收起更多操作" if self._left_more_expanded else "▸ 更多操作（撤销、移动、模板…）"
        )

    def _apply_simple_mode_ui(self) -> None:
        simple = self._is_simple_mode()
        self._header_adv_wrap.setVisible(not simple)
        self.adv_header.setVisible(not simple)
        self._left_more_btn.setVisible(simple)
        if simple and not self._left_more_expanded:
            self._left_more_wrap.setVisible(False)
        elif not simple:
            self._left_more_wrap.setVisible(True)
            self._left_more_btn.setVisible(False)
        wtype = ""
        if self.widget_list.currentRow() >= 0:
            widgets = self._widgets()
            row = self.widget_list.currentRow()
            if 0 <= row < len(widgets):
                wtype = str(widgets[row].get("type", ""))
        if hasattr(self, "property_form_box"):
            self.property_form_box.setTitle("编辑这一项" if simple else "控件属性")
        if wtype:
            self._update_form_visibility(wtype)
        elif hasattr(self, "id_hint_label"):
            self.id_hint_label.setVisible(simple)

    def _flash_status(self, message: str) -> None:
        self.workflow_hint.setText(message)
        QTimer.singleShot(4000, self._restore_workflow_hint)

    def _restore_workflow_hint(self) -> None:
        self.workflow_hint.setText(
            "三步：① 从模板创建或添加控件  ② 右边改名称  ③ 保存\n"
            "排乱了？点「一键整理」；脚本用「插入面板读取」自动生成代码。"
        )

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def _clear_dirty(self) -> None:
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

    def _on_layout_mode_changed(self, _index: int = 0) -> None:
        self._apply_header()
        self._mark_dirty()
        self._sync_canvas_mode()
        self._emit_layout_changed()

    def _on_screens_changed(self) -> None:
        self._flush_property_sync()
        # screens[] 已与 layout 共享引用，仅同步当前界面索引
        self._layout.setdefault("panel", {})["active_screen"] = self.screen_tabs_editor.active_index()
        self._selected_path = ()
        self._refresh_widget_list()
        self._clear_form()
        self._update_preview(force=True)
        self._mark_dirty()
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

    def open_layout_wizard(self) -> None:
        panel_title = str(self._layout.get("panel", {}).get("title", "") or "")
        dlg = LayoutWizardDialog(self, default_title=panel_title)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        key = dlg.selected_key()
        title = dlg.panel_title()
        try:
            if dlg.replace_all():
                self._layout = build_wizard_layout(key, panel_title=title)
            else:
                if key == "full":
                    QMessageBox.information(
                        self,
                        "提示",
                        "「登录+设置」完整模板请选「替换当前全部」。\n"
                        "追加模式请用登录 / 运行 / 提醒 / 双列。",
                    )
                    return
                sc = wizard_screen_for_append(key)
                screens(self._layout).append(sc)
                repair_all_screens(self._layout)
                if title:
                    self._layout.setdefault("panel", {})["title"] = title
        except ValueError as exc:
            QMessageBox.warning(self, "创建失败", str(exc))
            return
        self._commit_history()
        self._refresh_ui()
        self._mark_dirty()
        self._emit_layout_changed()
        self._flash_status("✓ 模板已创建，请改右侧文字后保存")
        if self._is_simple_mode():
            ans = QMessageBox.question(
                self,
                "插入脚本读取代码？",
                "是否根据新界面，自动在脚本里插入 panel.get 读取代码？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if ans == QMessageBox.StandardButton.Yes:
                self._insert_panel_reads_all()

    def _insert_panel_reads_all(self) -> None:
        block = lua_reads_block_for_layout(self._layout)
        self.insert_lua.emit(block)

    def _insert_selected_widget_lua(self) -> None:
        target = self._edit_target()
        if target is None:
            QMessageBox.information(self, "提示", "请先在左侧列表选一个控件")
            return
        w, _, _ = target
        spec = widget_lua_spec(w)
        if spec is None:
            QMessageBox.information(self, "提示", "当前控件类型不支持 panel.get 读取")
            return
        self.insert_lua.emit(lua_reads_for_widget_spec(spec))

    def apply_template(self) -> None:
        """兼容旧入口：改为推荐向导。"""
        self.open_layout_wizard()

    def apply_legacy_template(self) -> None:
        ans = QMessageBox.warning(
            self,
            "旧版 grid 模板",
            "这些模板仍是旧版网格布局，观感与主页表单不一致。\n"
            "建议改用「从模板创建（推荐）」。\n\n仍要继续套用旧模板吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        choices = template_choices()
        if not choices:
            return
        labels = [c[1] for c in choices]
        keys = [c[0] for c in choices]
        label, ok = QInputDialog.getItem(self, "套用旧版模板", "选择模板:", labels, 0, False)
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
            self._layout = migrate_layout(clone_layout(tpl))
        else:
            panel = self._layout.setdefault("panel", {})
            panel.update(tpl.get("panel", {}))
            self._layout["enabled"] = tpl.get("enabled", True)
            if is_free_mode(self._layout):
                active_screen_widgets(self._layout).extend(
                    clone_list(tpl.get("widgets", []))
                )
            else:
                self._layout.setdefault("widgets", []).extend(
                    clone_list(tpl.get("widgets", []))
                )
        self._refresh_ui()
        self._mark_dirty()
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
        return editor_widget_list(self._layout)

    def _chrome_widgets(self) -> list:
        ensure_migrated(self._layout)
        return chrome_widgets(self._layout)

    def load_from_project(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return
        self._layout = load_layout(project)
        if is_free_mode(self._layout):
            sanitize_free_layout(self._layout)
        repaired = self._auto_repair_layout_if_needed(refresh=False)
        self._history.clear()
        self._refresh_ui()
        self._commit_history()
        self._clear_dirty()
        self._emit_layout_changed()
        if repaired:
            self._mark_dirty()

    def _auto_repair_layout_if_needed(self, *, refresh: bool = True) -> bool:
        """自由布局下自动整理可修复的坐标/尺寸问题。"""
        if not is_free_mode(self._layout):
            return False
        errors = validate_layout(self._layout)
        if not errors or not is_auto_repairable(errors):
            return False
        sanitize_free_layout(self._layout)
        if refresh:
            self._refresh_ui()
            self._update_preview(force=True)
            self._emit_layout_changed()
        return True

    def _validate_for_save(self, *, auto_repair: bool = True) -> tuple[list[str], bool]:
        """保存前校验；可自动修复时整理后重试。返回 (errors, repaired)."""
        self._flush_property_sync()
        if self._edit_target() is None:
            self._apply_header()
        errors = validate_layout(self._layout)
        repaired = False
        if errors and auto_repair and is_free_mode(self._layout) and is_auto_repairable(errors):
            sanitize_free_layout(self._layout)
            repaired = True
            self._refresh_ui()
            self._update_preview(force=True)
            errors = validate_layout(self._layout)
        return errors, repaired

    def current_layout(self) -> dict[str, Any]:
        return clone_layout(self._layout)

    def save_to_project(self, *, silent: bool = False) -> bool:
        project = self._project_dir_getter()
        if not project:
            if not silent:
                QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return False
        self._flush_property_sync()
        self._apply_header()
        errors, repaired = self._validate_for_save(auto_repair=True)
        if errors:
            if not silent:
                QMessageBox.warning(self, "布局校验", "\n".join(errors[:10]))
            return False
        save_layout(project, self._layout)
        self._clear_dirty()
        self.layout_changed.emit(clone_layout(self._layout))
        if not silent:
            if self._is_simple_mode():
                self._flash_status(
                    "✓ 已保存到 ui/layout.json，并已同步到 APK 资源"
                    + ("（已自动整理布局）" if repaired else "")
                )
            else:
                msg = "已保存 ui/layout.json，并已同步到 android-runtime/assets"
                if repaired:
                    msg += "\n（已自动整理过小/重叠的控件，无需手调坐标）"
                QMessageBox.information(self, "完成", msg)
        return True

    def _commit_history(self) -> None:
        self._history.push(self._layout)

    def _apply_layout_snapshot(self, snap: dict) -> None:
        self._layout = clone_layout(snap)
        self._selected_path = ()
        self._refresh_ui()
        self._mark_dirty()
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
        self._clipboard_widget = clone_widget(w)

    def _paste_widget(self) -> None:
        if not self._clipboard_widget:
            return
        self._flush_property_sync()
        src = clone_widget(self._clipboard_widget)
        widgets = self._widgets()
        w = default_widget(str(src.get("type", "label")), len(widgets) + 1)
        w.update({k: v for k, v in src.items() if k != "id"})
        w["id"] = next_widget_id(self._layout)
        w["layout_y"] = int(w.get("layout_y", 40)) + 72
        widgets.append(w)
        row = len(widgets) - 1
        self._commit_history()
        self._refresh_widget_list(select_row=row)
        if self.widget_list.currentRow() != row:
            self._selected_path = (active_screen_index(self._layout), row)
            self._load_widget_into_form(widgets[row])
        self._mark_dirty()
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
        self._mark_dirty()
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
        self._mark_dirty()
        self._emit_layout_changed()

    def save_if_dirty(self) -> bool:
        if not self._dirty:
            return False
        project = self._project_dir_getter()
        if not project:
            return False
        errors, repaired = self._validate_for_save(auto_repair=True)
        if errors:
            QMessageBox.warning(
                self,
                "布局校验",
                "自动保存已取消：\n" + "\n".join(errors[:8])
                + "\n\n可点左侧「一键整理」后重试，或检查重复 ID 等问题。",
            )
            return False
        save_layout(project, self._layout)
        self._clear_dirty()
        self.layout_changed.emit(clone_layout(self._layout))
        if repaired:
            self._update_preview(force=True)
        return True

    def add_widget(self, wtype: str) -> None:
        ensure_migrated(self._layout)
        # 先把当前属性面板写回旧控件，避免切换选中后把旧类型（如下拉）覆盖到新控件
        self._flush_property_sync()
        if wtype == "stop_script" and is_free_mode(self._layout):
            QMessageBox.information(
                self,
                "提示",
                "手机自由布局不再使用「停止」按钮；脚本运行后请点右侧悬浮球 ■ 图标停止。",
            )
            return
        if is_action_type(wtype) and wtype in ("start_script", "stop_script"):
            from studio.services.screen_layout import is_host_display

            if is_host_display(self._layout.get("panel")):
                QMessageBox.information(
                    self,
                    "提示",
                    "当前为「主页面表单 + 悬浮球启停」模式：\n"
                    "开始/停止请用悬浮窗，不要在界面里添加开始/停止按钮。",
                )
                return
            widgets = self._chrome_widgets()
            w = default_widget(wtype, len(widgets) + 1)
            w["id"] = next_widget_id(self._layout)
            widgets.append(w)
            self._selected_path = (CHROME_PATH_TAG, len(widgets) - 1)
            self._load_widget_into_form(w)
        else:
            if is_action_type(wtype) and is_host_display(self._layout.get("panel")):
                QMessageBox.information(
                    self,
                    "提示",
                    "主页面模式不支持在表单界面内添加动作按钮（开始/停止等）。",
                )
                return
            widgets = self._widgets()
            w = default_widget(wtype, len(widgets) + 1)
            w["id"] = next_widget_id(self._layout)
            if is_free_mode(self._layout):
                from studio.services.flow_layout import place_widget_in_flow
                from studio.services.free_layout import panel_design_size

                dw, _ = panel_design_size(self._layout.get("panel") or {})
                place_widget_in_flow(widgets, w, design_w=dw)
            elif widgets:
                bottom = max(
                    int(x.get("layout_y", 0) + x.get("layout_h", 56)) for x in widgets
                )
                w["layout_y"] = bottom + 16
            widgets.append(w)
            row = len(widgets) - 1
            repair_screen_widgets(widgets)
            if self._is_simple_mode():
                repair_all_screens(self._layout)
            self._sync_screen_tabs_from_layout()
            # 选中新行时由 _on_select_widget 再 flush（此时已指向旧控件）并加载新控件
            self._refresh_widget_list(select_row=row)
            if self.widget_list.currentRow() != row:
                self._selected_path = (active_screen_index(self._layout), row)
                self._load_widget_into_form(widgets[row])
        self._mark_dirty()
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
        self._mark_dirty()
        self._commit_history()
        self._emit_layout_changed()

    def _on_display_mode_changed(self, _index: int = 0) -> None:
        self._apply_header()
        self._update_mode_hint()
        self._update_preview()
        self._mark_dirty()
        self._emit_layout_changed()

    def _update_mode_hint(self) -> None:
        mode = self.display_mode_combo.currentData() or "host"
        hints = {
            "host": "主页面填表 · 启停由悬浮球控制 · 长按主页面板标题可进设计模式",
            "minimal": "仅悬浮球/条 · 无内嵌表单",
            "form": "悬浮窗内完整表单 · 可长按标题栏进入设计模式",
        }
        self.mode_hint_label.setText(hints.get(str(mode), ""))
        self.allow_design_cb.setToolTip("APK 主页/悬浮窗长按标题栏 1.2 秒进入布局设计模式")

    def _selected_widget_indices(self) -> list[int]:
        rows = [i.row() for i in self.widget_list.selectedIndexes()]
        if not rows and self.widget_list.currentRow() >= 0:
            rows = [self.widget_list.currentRow()]
        return sorted(set(rows))

    def _after_geometry_edit(self, flash: str) -> None:
        self._refresh_widget_list(keep_row=True)
        self._mark_dirty()
        self._update_preview(force=True)
        self._commit_history()
        self._emit_layout_changed()
        if self._is_simple_mode():
            self._flash_status(flash)

    def reflow_layout_manual(self) -> None:
        if not is_free_mode(self._layout):
            QMessageBox.information(self, "提示", "仅「手机自由」布局支持流式重排")
            return
        from studio.services.flow_layout import reflow_active_screen

        if not reflow_active_screen(self._layout):
            return
        self._after_geometry_edit("✓ 已流式重排，记得保存")

    def align_left_manual(self) -> None:
        if not is_free_mode(self._layout):
            return
        from studio.services.flow_layout import align_left
        from studio.services.free_layout import panel_design_size

        widgets = self._widgets()
        idxs = self._selected_widget_indices()
        targets = [widgets[i] for i in idxs] if idxs else widgets
        dw, _ = panel_design_size(self._layout.get("panel") or {})
        align_left(targets, design_w=dw)
        self._after_geometry_edit("✓ 已左对齐")

    def unify_width_manual(self) -> None:
        if not is_free_mode(self._layout):
            return
        from studio.services.flow_layout import unify_width
        from studio.services.free_layout import panel_design_size

        widgets = self._widgets()
        idxs = self._selected_widget_indices()
        targets = [widgets[i] for i in idxs] if idxs else widgets
        dw, _ = panel_design_size(self._layout.get("panel") or {})
        unify_width(targets, design_w=dw)
        self._after_geometry_edit("✓ 已统一宽度")

    def pair_columns_manual(self) -> None:
        if not is_free_mode(self._layout):
            return
        idxs = self._selected_widget_indices()
        if len(idxs) < 2:
            QMessageBox.information(self, "提示", "请先在列表中多选至少两个控件，再点「两列并排」")
            return
        from studio.services.flow_layout import pair_two_columns
        from studio.services.free_layout import panel_design_size

        dw, _ = panel_design_size(self._layout.get("panel") or {})
        pair_two_columns(self._widgets(), idxs, design_w=dw)
        self._after_geometry_edit("✓ 已两列并排")

    def repair_layout_manual(self) -> None:
        if not is_free_mode(self._layout):
            QMessageBox.information(self, "提示", "仅「手机自由」布局支持一键整理")
            return
        from studio.services.flow_layout import reflow_active_screen

        reflow_active_screen(self._layout)
        sanitize_free_layout(self._layout)
        self._refresh_ui()
        self._mark_dirty()
        self._update_preview(force=True)
        self._emit_layout_changed()
        errors = validate_layout(self._layout)
        if errors:
            QMessageBox.warning(
                self,
                "整理完成",
                "已重排控件并修正重复 ID，但仍有以下问题需手动处理：\n"
                + "\n".join(errors[:10]),
            )
            return
        if self._is_simple_mode():
            self._flash_status("✓ 已一键整理，记得点「保存」")
        else:
            QMessageBox.information(
                self,
                "完成",
                "已按自上而下重排控件、修正过小尺寸，并自动修正重复 ID。\n请点「保存」同步到工程。",
            )

    def pull_device_layout(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return
        project_dir = Path(project)
        cfg_path = project_dir / "project.json"
        if not cfg_path.is_file():
            QMessageBox.warning(self, "提示", "缺少 project.json")
            return
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "提示", f"project.json 无效: {exc}")
            return
        package_id = str(cfg.get("package_id") or "").strip()
        if not package_id:
            QMessageBox.warning(self, "提示", "未配置 package_id")
            return
        ans = QMessageBox.question(
            self,
            "拉取实机布局",
            "将从已连接设备读取 layout-overrides 并覆盖工程 ui/layout.json（自动备份 .bak）。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            from studio.services.adb_service import AdbService
            from studio.services.layout_override_sync import pull_and_merge_to_project

            pull_and_merge_to_project(AdbService(), project_dir, package_id)
        except Exception as exc:
            QMessageBox.warning(self, "拉取失败", str(exc))
            return
        self.load_from_project()
        QMessageBox.information(self, "完成", "已合并设备 layout 覆盖到工程，请检查并保存。")

    def reset_default(self) -> None:
        ans = QMessageBox.question(
            self,
            "恢复默认",
            "将覆盖当前布局为默认模板，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._layout = clone_layout(DEFAULT_LAYOUT)
        self._history.clear()
        self._refresh_ui()
        self._commit_history()
        self._mark_dirty()

    def _move_widget(self, delta: int) -> None:
        row = self.widget_list.currentRow()
        widgets = self._widgets()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= len(widgets):
            return
        widgets[row], widgets[new_row] = widgets[new_row], widgets[row]
        self._refresh_ui()
        self.widget_list.setCurrentRow(new_row)
        self._mark_dirty()

    def _apply_header(self) -> None:
        panel = self._layout.setdefault("panel", {})
        new_dw = self.design_width_spin.value()
        new_dh = self.design_height_spin.value()
        if is_free_mode(self._layout):
            old_dw, old_dh = self._last_design_wh
            if new_dw != old_dw or new_dh != old_dh:
                from studio.services.free_layout import rescale_layout_for_design_change

                rescale_layout_for_design_change(self._layout, old_dw, old_dh, new_dw, new_dh)
                self._last_design_wh = (new_dw, new_dh)
        panel["title"] = self.title_edit.text().strip() or "脚本助手"
        panel["columns"] = self.cols_spin.value()
        panel["width_dp"] = self.width_dp_spin.value()
        panel["start_x"] = self.start_x_spin.value()
        panel["start_y"] = self.start_y_spin.value()
        panel["theme"] = self.theme_combo.currentData() or "light"
        panel["allow_design"] = self.allow_design_cb.isChecked()
        panel["start_confirm_collapse"] = self.start_confirm_cb.isChecked()
        panel["layout_mode"] = self.layout_mode_combo.currentData() or "free"
        panel["display_mode"] = self.display_mode_combo.currentData() or "host"
        panel["show_log"] = self.show_log_cb.isChecked()
        panel["show_on_launch"] = self.show_on_launch_cb.isChecked()
        panel["opacity"] = round(self.opacity_spin.value() / 100.0, 2)
        panel["ball_size_dp"] = self.ball_size_spin.value()
        panel["design_width"] = self.design_width_spin.value()
        panel["design_height"] = self.design_height_spin.value()
        if is_free_mode(self._layout):
            panel["active_screen"] = self.screen_tabs_editor.active_index()
            editor_screens = self.screen_tabs_editor.get_screens()
            if self._layout.get("screens") is not editor_screens:
                self._layout["screens"] = editor_screens
        self._layout["enabled"] = self.enabled_cb.currentIndex() == 0

    def _on_header_changed(self, *_args) -> None:
        self._apply_header()
        self._update_preview()
        self._mark_dirty()
        self._emit_layout_changed()

    def _sync_panel_position(self, *_args) -> None:
        panel = self._layout.setdefault("panel", {})
        panel["start_x"] = self.start_x_spin.value()
        panel["start_y"] = self.start_y_spin.value()
        self._apply_header()
        self._emit_layout_changed()

    def _emit_layout_changed(self) -> None:
        self._layout_emit_timer.start()

    def _flush_layout_changed(self) -> None:
        self.layout_changed.emit(clone_layout(self._layout))

    def _refresh_ui(self) -> None:
        self._layout = migrate_layout(self._layout)
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
        dm_idx = self.display_mode_combo.findData(panel.get("display_mode", "host"))
        self.display_mode_combo.blockSignals(True)
        self.display_mode_combo.setCurrentIndex(max(0, dm_idx))
        self.display_mode_combo.blockSignals(False)
        self.show_log_cb.blockSignals(True)
        self.show_log_cb.setChecked(bool(panel.get("show_log", True)))
        self.show_log_cb.blockSignals(False)
        self.show_on_launch_cb.blockSignals(True)
        self.show_on_launch_cb.setChecked(bool(panel.get("show_on_launch", False)))
        self.show_on_launch_cb.blockSignals(False)
        self.opacity_spin.blockSignals(True)
        self.opacity_spin.setValue(int(float(panel.get("opacity", 0.96)) * 100))
        self.opacity_spin.blockSignals(False)
        self.ball_size_spin.blockSignals(True)
        self.ball_size_spin.setValue(int(panel.get("ball_size_dp", 48)))
        self.ball_size_spin.blockSignals(False)
        self.design_width_spin.blockSignals(True)
        self.design_width_spin.setValue(int(panel.get("design_width", 720)))
        self.design_width_spin.blockSignals(False)
        self.design_height_spin.blockSignals(True)
        self.design_height_spin.setValue(int(panel.get("design_height", 1280)))
        self.design_height_spin.blockSignals(False)
        self._last_design_wh = (
            int(panel.get("design_width", 720)),
            int(panel.get("design_height", 1280)),
        )
        self._update_mode_hint()
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
        self._apply_simple_mode_ui()

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
        self._mark_dirty()
        self._emit_layout_changed()

    def _insert_panel_lua_example(self) -> None:
        self._insert_panel_reads_all()

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
        self._mark_dirty()
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
        self._mark_dirty()

    # 兼容旧信号名
    @property
    def btn_list(self) -> QListWidget:
        return self.widget_list
