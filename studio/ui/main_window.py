"""PC Studio 主窗口 — 工程 / 抓抓 / 脚本。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt
from PySide6.QtGui import QCloseEvent, QFont, QGuiApplication, QKeySequence, QPixmap, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from studio.ui.app_theme import apply_theme, set_button_role
from studio.ui.grab_widget import GrabWidget
from studio.ui.layout_editor_widget import LayoutEditorWidget
from studio.ui.lua_code_editor import LuaCodeEditor
from studio.ui.lua_highlighter import LuaHighlighter
from studio.ui.script_panel_widget import ScriptPanelWidget
from studio.ui.script_command_toolbox import ScriptCommandToolbox
from studio.ui.image_gallery_widget import ImageGalleryWidget
from studio.ui.yolo_models_widget import YoloModelsWidget
from studio.ui.page_shell import (
    main_column,
    page_root,
    scroll_side_panel,
    section_title,
    side_column,
    tool_button_row,
    two_column_splitter,
)
from studio.services.adb_service import AdbService
from studio.services.async_command import AsyncCommand
from studio.ui.apk_pack_dialog import ApkPackDialog
from studio.ui.publish_update_dialog import PublishUpdateDialog
from studio.services.pack_preflight import validate_before_pack
from studio.services.runtime_presets import PRESETS, apply_preset
from studio.services.jiaoben_api import fetch_projects_for_combo
from studio.services.jiaoben_project_id import resolve_jiaoben_project_id
from packager.pack_metadata import read_project_cfg, save_pack_metadata, validate_pack_fields
from packager.icon_processor import resolve_icon_source
from studio.runtime.panel_state import PanelState
from studio.services.project_persistence import (
    export_project_zip,
    get_last_project,
    get_recent_projects,
    import_project_zip,
    remember_project,
)
from studio.ui.onboarding_dialog import OnboardingDialog, should_show_onboarding

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "studio" / "resources" / "project-template"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Script Studio")
        self.resize(1320, 840)
        self.setMinimumSize(1100, 720)
        self.project_dir: Path | None = None
        self.adb = AdbService()
        self._lua_proc: QProcess | None = None
        self._async_cmd = AsyncCommand(self)
        self._async_cmd.output.connect(self._on_async_output)
        self._async_cmd.finished.connect(self._on_async_finished)
        self._pack_action_buttons: list[QPushButton] = []
        self._pack_phase = ""
        self._pack_apk_out: Path | None = None
        self._pack_serial: str | None = None
        self._pack_package_id = ""
        self._pack_install_after = False
        self._script_dirty = False
        self._tab_titles = ("工程", "抓抓", "浮动面板", "脚本")

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        self.tabs.setDocumentMode(True)

        corner = QWidget()
        corner.setObjectName("TabBarCorner")
        corner_lay = QHBoxLayout(corner)
        corner_lay.setContentsMargins(0, 0, 12, 0)
        corner_lay.setSpacing(8)
        self.path_label = QLabel("未打开工程")
        self.path_label.setObjectName("ProjectChip")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        corner_lay.addWidget(self.path_label)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)

        self.tabs.addTab(self._build_project_tab(), "工程")
        self.grab = GrabWidget(lambda: self.project_dir)
        self.grab.log_message.connect(self.append)
        self.grab.insert_lua.connect(self._insert_lua_to_script)
        self.tabs.addTab(self.grab, "抓抓")
        self.layout_editor = LayoutEditorWidget(lambda: str(self.project_dir) if self.project_dir else None)
        self.layout_editor.layout_changed.connect(self.grab.apply_layout_from_editor)
        self.layout_editor.dirty_changed.connect(self._on_layout_dirty_changed)
        self.layout_editor.request_pick_mode.connect(self._on_request_pick_mode)
        self.layout_editor.insert_lua.connect(self._insert_lua_to_script)
        self.grab.panel_position_picked.connect(self.layout_editor.set_panel_position)
        self.grab.button_coords_picked.connect(self._on_button_coords_picked)
        self.tabs.addTab(self.layout_editor, "浮动面板")
        self.script_panel = ScriptPanelWidget(lambda: self.project_dir)
        self.script_panel.insert_lua.connect(self._insert_lua_to_script)
        self.script_panel.copy_lua.connect(self._copy_lua_snippet)
        self.image_gallery = ImageGalleryWidget(lambda: self.project_dir)
        self.yolo_models = YoloModelsWidget(lambda: self.project_dir)
        self.yolo_models.models_changed.connect(self.grab.refresh_yolo_models)
        self.grab.images_changed.connect(self.image_gallery.refresh)
        self.image_gallery.images_changed.connect(self.grab.refresh_image_assets)
        self.layout_editor.layout_changed.connect(self.script_panel.apply_layout)
        self._script_tab = self._build_script_tab()
        self.tabs.addTab(self._script_tab, "脚本")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        content_wrap = QWidget()
        content_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_lay = QVBoxLayout(content_wrap)
        content_lay.setContentsMargins(8, 0, 8, 6)
        content_lay.setSpacing(0)
        content_lay.addWidget(self.tabs, 1)
        root.addWidget(content_wrap, 1)

        self.setCentralWidget(central)
        self._refresh_recent_list()
        self.statusBar().showMessage("就绪")
        self._try_restore_last_project()
        self._setup_help_menu()

    def _setup_help_menu(self) -> None:
        menu = self.menuBar().addMenu("帮助")
        act_guide = menu.addAction("首次引导 / 环境预检")
        act_guide.triggered.connect(self._show_onboarding)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if should_show_onboarding():
            self._show_onboarding()

    def _show_onboarding(self) -> None:
        dlg = OnboardingDialog(self, adb_path=self.adb.adb_path)
        dlg.exec()

    def _build_project_tab(self) -> QWidget:
        w = QWidget()
        root = page_root(w)

        left, left_lay = side_column(260, None)
        left_lay.addWidget(section_title("工程"))
        tool_button_row(
            left_lay,
            [
                ("新建工程", self.new_project, "primary"),
                ("打开工程", self.open_project, "accent"),
                ("demo-game", self.open_demo_game, "ghost"),
            ],
            columns=1,
        )
        left_lay.addWidget(section_title("工程文件"))
        tool_button_row(
            left_lay,
            [
                ("保存工程", self.save_all_project, "primary"),
                ("导出工程", self.export_project, "ghost"),
                ("导入工程", self.import_project, "ghost"),
            ],
            columns=1,
        )
        left_lay.addWidget(section_title("最近打开"))
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("RecentProjectList")
        self.recent_list.itemDoubleClicked.connect(self._on_recent_item_activated)
        left_lay.addWidget(self.recent_list, 1)
        left_lay.addWidget(section_title("构建"))
        build_grid = QWidget()
        build_grid_lay = QHBoxLayout(build_grid)
        build_grid_lay.setContentsMargins(0, 0, 0, 0)
        build_col = QVBoxLayout()
        build_col.setSpacing(8)
        for text, slot, role in (
            ("校验工程", self.validate_project, "ghost"),
            ("YAML→Lua", self.convert_yaml_to_lua, "ghost"),
            ("打包 APK", self.build_apk, "accent"),
            ("打包安装", self.build_and_install, "primary"),
            ("发布热更新", self.publish_hot_update, "ghost"),
        ):
            btn = QPushButton(text)
            set_button_role(btn, role)
            btn.setMinimumHeight(34)
            btn.clicked.connect(slot)
            build_col.addWidget(btn)
            if text in ("打包 APK", "打包安装", "校验工程"):
                self._pack_action_buttons.append(btn)
        build_grid_lay.addLayout(build_col)
        left_lay.addWidget(build_grid)

        left_lay.addWidget(section_title("打包应用信息"))
        pack_form = QFormLayout()
        self.pack_name_edit = QLineEdit()
        self.pack_name_edit.setPlaceholderText("安装后显示的应用名称")
        pack_form.addRow("软件名称", self.pack_name_edit)
        self.pack_pkg_edit = QLineEdit()
        self.pack_pkg_edit.setPlaceholderText("com.example.myscript")
        pack_form.addRow("包名", self.pack_pkg_edit)
        self.pack_project_combo = QComboBox()
        self.pack_project_combo.setEditable(True)
        self.pack_project_combo.setPlaceholderText("jiaoben 发卡项目")
        pack_form.addRow("发卡项目", self.pack_project_combo)
        icon_row = QHBoxLayout()
        self.pack_icon_edit = QLineEdit()
        self.pack_icon_edit.setPlaceholderText("留空=默认图标；可点右侧选择")
        pick_icon_btn = QPushButton("选择…")
        set_button_role(pick_icon_btn, "ghost")
        pick_icon_btn.clicked.connect(self._pick_pack_icon)
        icon_row.addWidget(self.pack_icon_edit, 1)
        icon_row.addWidget(pick_icon_btn)
        icon_wrap = QWidget()
        icon_wrap.setLayout(icon_row)
        pack_form.addRow("应用图标", icon_wrap)
        self.pack_show_log_cb = QCheckBox("悬浮窗显示运行日志")
        self.pack_show_log_cb.setToolTip("勾选后 APK 悬浮窗可展开小块日志区，不影响脚本运行")
        pack_form.addRow("", self.pack_show_log_cb)
        pack_form_box = QWidget()
        pack_form_box.setLayout(pack_form)
        left_lay.addWidget(pack_form_box)
        self.pack_icon_preview = QLabel()
        self.pack_icon_preview.setFixedSize(56, 56)
        self.pack_icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pack_icon_preview.setStyleSheet(
            "border:1px solid #CBD5E1;border-radius:8px;background:#F8FAFC;"
        )
        left_lay.addWidget(self.pack_icon_preview)
        save_pack_btn = QPushButton("保存应用信息")
        set_button_role(save_pack_btn, "ghost")
        save_pack_btn.clicked.connect(lambda: self._save_pack_fields(show_ok=True))
        left_lay.addWidget(save_pack_btn)

        left_lay.addWidget(section_title("性能预设"))
        preset_row = QHBoxLayout()
        for key, preset in PRESETS.items():
            btn = QPushButton(str(preset["label"]).split("（")[0])
            set_button_role(btn, "ghost")
            btn.clicked.connect(lambda _c=False, k=key: self._apply_runtime_preset(k))
            preset_row.addWidget(btn)
        preset_wrap = QWidget()
        preset_wrap.setLayout(preset_row)
        left_lay.addWidget(preset_wrap)

        self.pack_icon_edit.textChanged.connect(self._refresh_pack_icon_preview)

        left_scroll = scroll_side_panel(left, min_width=260)

        center, center_lay = main_column()
        center_lay.addWidget(section_title("运行日志"))
        self.log = QTextEdit()
        self.log.setObjectName("LogConsole")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("操作与打包输出将显示在这里…")
        center_lay.addWidget(self.log, 1)

        root.addWidget(
            two_column_splitter(left_scroll, center, sizes=(300, 720), stretches=(1, 4)),
            1,
        )
        return w

    def _build_script_tab(self) -> QWidget:
        w = QWidget()
        root = page_root(w)

        v_split = QSplitter(Qt.Orientation.Horizontal)
        v_split.setObjectName("PageSplitter")
        v_split.setChildrenCollapsible(True)
        self._script_split = v_split

        self.command_toolbox = ScriptCommandToolbox(lambda: self.project_dir)
        self.command_toolbox.insert_code.connect(self._insert_lua_to_script)
        self.command_toolbox.copy_code.connect(self._copy_lua_snippet)
        self.image_gallery.images_changed.connect(self.command_toolbox.refresh_templates)
        self.grab.images_changed.connect(self.command_toolbox.refresh_templates)
        self.yolo_models.models_changed.connect(self.command_toolbox.refresh_yolo_models)
        v_split.addWidget(self.command_toolbox)

        editor_card, editor_lay = main_column()
        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(4)

        toolbar_row.addWidget(section_title("脚本"))
        for label, slot in (
            ("撤销", self.script_edit_undo),
            ("重做", self.script_edit_redo),
            ("剪切", self.script_edit_cut),
            ("复制", self.script_edit_copy),
            ("粘贴", self.script_edit_paste),
        ):
            btn = QPushButton(label)
            set_button_role(btn, "ghost")
            btn.clicked.connect(slot)
            toolbar_row.addWidget(btn)
        toolbar_row.addStretch()

        save_btn = QPushButton("保存")
        set_button_role(save_btn, "accent")
        save_btn.clicked.connect(self.save_script)
        self.run_lua_btn = QPushButton("运行")
        set_button_role(self.run_lua_btn, "primary")
        self.run_lua_btn.clicked.connect(self.run_lua_pc)
        toolbar_row.addWidget(save_btn)
        toolbar_row.addWidget(self.run_lua_btn)

        self._script_panel_expanded = True
        self._stop_lua_action = None
        more_btn = QPushButton("更多")
        set_button_role(more_btn, "ghost")
        more_btn.setToolTip("重新加载、停止运行、浮动面板")
        more_menu = QMenu(more_btn)
        more_menu.addAction("重新加载", self.reload_script)
        self._stop_lua_action = more_menu.addAction("停止运行")
        self._stop_lua_action.setEnabled(False)
        self._stop_lua_action.triggered.connect(self.stop_lua_pc)
        more_menu.addSeparator()
        self._panel_toggle_action = more_menu.addAction("收起浮动面板")
        self._panel_toggle_action.triggered.connect(self._toggle_script_panel)
        more_btn.setMenu(more_menu)
        toolbar_row.addWidget(more_btn)
        self._sync_script_panel_toggle_ui()
        editor_lay.addLayout(toolbar_row)

        editor_split = QSplitter(Qt.Orientation.Vertical)
        editor_split.setObjectName("ScriptEditorSplit")
        self.script_edit = LuaCodeEditor()
        self.script_edit.setObjectName("ScriptEditor")
        self.script_edit.setPlaceholderText("打开工程后编辑 main.lua …")
        self.script_edit.set_monospace_font(11)
        self._lua_highlighter = LuaHighlighter(self.script_edit.document())
        self.script_edit.textChanged.connect(self._on_script_text_changed)
        editor_split.addWidget(self.script_edit)

        log_wrap = QWidget()
        log_wrap_lay = QVBoxLayout(log_wrap)
        log_wrap_lay.setContentsMargins(0, 0, 0, 0)
        log_wrap_lay.setSpacing(4)
        log_header = QHBoxLayout()
        log_header.addWidget(section_title("运行日志"))
        log_header.addStretch()
        copy_log_btn = QPushButton("复制")
        set_button_role(copy_log_btn, "ghost")
        copy_log_btn.setToolTip("复制全部运行日志到剪贴板")
        copy_log_btn.clicked.connect(self._copy_script_run_log)
        clear_log_btn = QPushButton("清空")
        set_button_role(clear_log_btn, "ghost")
        log_header.addWidget(copy_log_btn)
        log_header.addWidget(clear_log_btn)
        log_wrap_lay.addLayout(log_header)

        self.script_run_log = QTextEdit()
        self.script_run_log.setObjectName("ScriptRunLog")
        self.script_run_log.setReadOnly(True)
        self.script_run_log.setPlaceholderText("PC 运行 Lua 的输出将显示在这里（含 bot.log / print / 报错行号）…")
        self.script_run_log.setMinimumHeight(120)
        log_font = QFont("Consolas")
        log_font.setStyleHint(QFont.StyleHint.Monospace)
        log_font.setPointSize(10)
        self.script_run_log.setFont(log_font)
        clear_log_btn.clicked.connect(self.script_run_log.clear)
        log_wrap_lay.addWidget(self.script_run_log, 1)
        editor_split.addWidget(log_wrap)
        editor_split.setStretchFactor(0, 3)
        editor_split.setStretchFactor(1, 2)
        editor_split.setSizes([480, 220])
        editor_lay.addWidget(editor_split, 1)
        self.script_tip = QLabel(
            "小技巧：Ctrl+S 保存 · 左侧搜索命令 · 行号在编辑器左侧 · 抓抓测试后复制脚本粘贴到此"
        )
        self.script_tip.setObjectName("HintLabel")
        self.script_tip.setWordWrap(True)
        editor_lay.addWidget(self.script_tip)
        v_split.addWidget(editor_card)
        self._script_side_tabs = QTabWidget()
        self._script_side_tabs.setObjectName("ScriptSideTabs")
        self._script_side_tabs.setDocumentMode(True)
        self._script_side_tabs.addTab(self.script_panel, "浮动面板")
        self._script_side_tabs.addTab(self.image_gallery, "附件")
        self._script_side_tabs.addTab(self.yolo_models, "模型")
        v_split.addWidget(self._script_side_tabs)
        self._script_editor_card = editor_card
        self._script_side_tabs.setMinimumWidth(0)
        editor_card.setMinimumWidth(360)
        self.command_toolbox.setMinimumWidth(260)
        v_split.setStretchFactor(0, 0)
        v_split.setStretchFactor(1, 2)
        v_split.setStretchFactor(2, 3)
        self._script_default_sizes = [280, 500, 460]
        v_split.setSizes(self._script_default_sizes)
        v_split.splitterMoved.connect(self._on_script_split_moved)
        root.addWidget(v_split, 1)

        QShortcut(QKeySequence.StandardKey.Save, self.script_edit, self.save_script)
        return w

    def _script_tab_index(self) -> int:
        return self.tabs.indexOf(self._script_tab)

    def _sync_script_panel_toggle_ui(self) -> None:
        action = getattr(self, "_panel_toggle_action", None)
        if action is None:
            return
        if self._script_panel_expanded:
            action.setText("收起浮动面板")
        else:
            action.setText("展开浮动面板")

    def _toggle_script_panel(self) -> None:
        if self._script_panel_expanded:
            self._script_panel_narrow()
        else:
            self._script_panel_wide()

    def _on_script_split_moved(self, *_args) -> None:
        split = getattr(self, "_script_split", None)
        if split is None:
            return
        sizes = split.sizes()
        if len(sizes) >= 3:
            expanded = sizes[2] > 0
            if expanded:
                self._script_side_tabs.show()
                self._script_saved_sizes = list(sizes)
            if expanded != self._script_panel_expanded:
                self._script_panel_expanded = expanded
                self._sync_script_panel_toggle_ui()
        self.script_panel.refresh_viewport()

    def _script_panel_narrow(self) -> None:
        """收起右侧浮动面板，代码编辑器占满。"""
        split = getattr(self, "_script_split", None)
        if split is None:
            return
        sizes = split.sizes()
        if len(sizes) >= 3 and sizes[2] > 0:
            self._script_saved_sizes = list(sizes)
        total = max(sum(split.sizes()), split.width(), 1)
        toolbox_w = sizes[0] if len(sizes) >= 3 else 220
        split.setSizes([toolbox_w, total - toolbox_w, 0])
        self._script_side_tabs.hide()
        self._script_panel_expanded = False
        self._sync_script_panel_toggle_ui()

    def _script_panel_wide(self) -> None:
        """展开右侧浮动面板，保留代码编辑区。"""
        split = getattr(self, "_script_split", None)
        if split is None:
            return
        self._script_side_tabs.show()
        total = max(sum(split.sizes()), split.width(), 1)
        editor_min = self._script_editor_card.minimumWidth() if hasattr(self, "_script_editor_card") else 360
        saved = getattr(self, "_script_saved_sizes", None)
        default = getattr(self, "_script_default_sizes", [220, 520, 480])
        if saved and len(saved) >= 3 and saved[2] > 0:
            toolbox_w, editor_w, panel_w = saved[0], saved[1], saved[2]
        elif len(default) >= 3:
            toolbox_w, editor_w, panel_w = default[0], default[1], default[2]
        else:
            toolbox_w, editor_w, panel_w = 220, int(total * 0.45), int(total * 0.35)
        ratio = total / max(toolbox_w + editor_w + panel_w, 1)
        toolbox_w = max(180, int(toolbox_w * ratio))
        editor_w = max(editor_min, int(editor_w * ratio))
        panel_w = total - toolbox_w - editor_w
        if panel_w < 260:
            panel_w = max(260, int(total * 0.3))
            editor_w = max(editor_min, total - toolbox_w - panel_w)
        split.setSizes([toolbox_w, editor_w, panel_w])
        self._script_panel_expanded = True
        self._sync_script_panel_toggle_ui()
        self.script_panel.refresh_viewport()

    def _on_tab_changed(self, index: int) -> None:
        if index < 0:
            return
        script_tab = getattr(self, "_script_tab", None)
        if script_tab is None:
            return
        if self.project_dir:
            self._save_current_project_quiet()
        widget = self.tabs.widget(index)
        if widget is script_tab and self.project_dir:
            self.script_panel.apply_layout(self.layout_editor.current_layout())

    def _on_request_pick_mode(self, mode: str) -> None:
        self.tabs.setCurrentWidget(self.grab)
        self.grab.enter_pick_mode(mode)
        self.append(f"请在抓抓页截图上点击取点（模式: {mode}）")

    def _on_button_coords_picked(self, x: int, y: int, mode: str) -> None:
        self.layout_editor.fill_button_coords(x, y, mode)
        self.tabs.setCurrentWidget(self.layout_editor)
        self.append(f"已填入浮动面板按钮坐标 ({x}, {y})")

    def append(self, msg: str) -> None:
        self.log.append(msg)

    def append_lua_log(self, msg: str) -> None:
        self.script_run_log.append(msg)
        self.log.append(msg)
        sb = self.script_run_log.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def _copy_script_run_log(self) -> None:
        text = self.script_run_log.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "复制日志", "运行日志为空")
            return
        QApplication.clipboard().setText(text)
        self.append("已复制运行日志到剪贴板")

    def _script_path(self) -> Path | None:
        if not self.project_dir:
            return None
        cfg_path = self.project_dir / "project.json"
        if not cfg_path.is_file():
            return self.project_dir / "main.lua"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        entry = cfg.get("entry", "main.lua")
        return self.project_dir / entry

    def _insert_lua_to_script(self, snippet: str) -> None:
        if not self.project_dir:
            QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return
        block = snippet.strip()
        if not block:
            return
        idx = self.tabs.indexOf(self._script_tab)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
        cursor = self.script_edit.textCursor()
        plain = self.script_edit.toPlainText()
        insert = block if block.endswith("\n") else block + "\n"
        if cursor.position() > 0 and plain and plain[cursor.position() - 1] != "\n":
            insert = "\n" + insert
        cursor.insertText(insert)
        self.script_edit.setTextCursor(cursor)
        self.script_edit.setFocus()
        self.append("已在光标处插入 Lua 代码")

    def _copy_lua_snippet(self, snippet: str) -> None:
        block = snippet.strip()
        if not block:
            return
        QGuiApplication.clipboard().setText(block)
        self.append("已复制 Lua 代码到剪贴板")

    def _goto_grab_tab(self) -> None:
        idx = self.tabs.indexOf(self.grab)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)

    def script_edit_undo(self) -> None:
        self.script_edit.undo()

    def script_edit_redo(self) -> None:
        self.script_edit.redo()

    def script_edit_cut(self) -> None:
        self.script_edit.cut()

    def script_edit_copy(self) -> None:
        self.script_edit.copy()

    def script_edit_paste(self) -> None:
        self.script_edit.paste()

    def new_project(self) -> None:
        dest = QFileDialog.getExistingDirectory(self, "选择新建工程目录")
        if not dest:
            return
        dest_path = Path(dest)
        if any(dest_path.iterdir()):
            QMessageBox.warning(self, "提示", "目录非空，请选空目录")
            return
        import shutil

        shutil.copytree(TEMPLATE, dest_path, dirs_exist_ok=False)
        cfg = dest_path / "project.json"
        text = cfg.read_text(encoding="utf-8").replace("com.autoscript.template", f"com.autoscript.{dest_path.name}")
        cfg.write_text(text.replace("Template Script", dest_path.name), encoding="utf-8")
        self._set_project(dest_path)

    def convert_yaml_to_lua(self) -> None:
        if not self._require_project():
            return
        yaml_candidates = ["main.yaml", "game.yaml"]
        src = None
        for name in yaml_candidates:
            p = self.project_dir / name
            if p.is_file():
                src = p
                break
        if not src:
            QMessageBox.warning(self, "提示", "工程内未找到 main.yaml 或 game.yaml")
            return
        self._pack_phase = "yaml_lua"
        self._run([sys.executable, str(ROOT / "tools" / "yaml_to_lua.py"), str(src)])

    def open_demo_game(self) -> None:
        demo = ROOT / "examples" / "demo-game"
        if not (demo / "project.json").is_file():
            QMessageBox.warning(self, "提示", f"未找到示例工程: {demo}")
            return
        self._set_project(demo)
        self.tabs.setCurrentWidget(self.grab)
        self.append("已打开 demo-game，建议先 ADB 截图查看面板预览")

    def open_project(self) -> None:
        dest = QFileDialog.getExistingDirectory(self, "打开脚本工程")
        if not dest:
            return
        self._set_project(Path(dest))

    def _refresh_recent_list(self) -> None:
        if not hasattr(self, "recent_list"):
            return
        self.recent_list.clear()
        for path in get_recent_projects():
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.recent_list.addItem(item)

    def _on_recent_item_activated(self, item: QListWidgetItem) -> None:
        raw = item.data(Qt.ItemDataRole.UserRole)
        if not raw:
            return
        path = Path(str(raw))
        if not path.is_dir():
            QMessageBox.warning(self, "提示", f"工程目录不存在:\n{path}")
            self._refresh_recent_list()
            return
        self._set_project(path)

    def _try_restore_last_project(self) -> None:
        path = get_last_project()
        if path is None:
            return
        self._set_project(path, remember=False)

    def _save_current_project_quiet(self) -> None:
        if not self.project_dir:
            return
        if self._script_dirty:
            self.save_script()
        self.layout_editor.save_if_dirty()
        if self.project_dir:
            PanelState.save_sidecar(self.project_dir)
        self._save_pack_fields(show_ok=False)

    def save_all_project(self) -> None:
        if not self._require_project():
            return
        self.save_script()
        layout_ok = self.layout_editor.save_to_project(silent=True)
        PanelState.save_sidecar(self.project_dir)
        pack_ok = self._save_pack_fields(show_ok=False)
        parts: list[str] = []
        if layout_ok:
            parts.append("ui/layout.json")
        parts.append("main.lua")
        parts.append(".studio/panel-state.json")
        if pack_ok:
            parts.append("project.json（应用信息）")
        self.append("已保存工程: " + "、".join(parts))
        QMessageBox.information(self, "完成", "工程已保存到当前目录。")

    def export_project(self) -> None:
        if not self._require_project():
            return
        self._save_current_project_quiet()
        default_name = f"{self.project_dir.name}.zip"
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "导出工程",
            str(self.project_dir.parent / default_name),
            "ZIP 压缩包 (*.zip)",
        )
        if not dest:
            return
        zip_path = Path(dest)
        if zip_path.suffix.lower() != ".zip":
            zip_path = zip_path.with_suffix(".zip")
        try:
            export_project_zip(self.project_dir, zip_path)
        except ValueError as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        self.append(f"已导出工程: {zip_path}")
        QMessageBox.information(self, "完成", f"工程已导出到:\n{zip_path}")

    def import_project(self) -> None:
        zip_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要导入的工程 ZIP",
            "",
            "ZIP 压缩包 (*.zip)",
        )
        if not zip_path:
            return
        dest = QFileDialog.getExistingDirectory(self, "选择导入目标目录（建议空目录）")
        if not dest:
            return
        try:
            project = import_project_zip(Path(zip_path), Path(dest))
        except ValueError as exc:
            QMessageBox.warning(self, "导入失败", str(exc))
            return
        self._set_project(project)
        self.append(f"已导入并打开工程: {project}")

    def _refresh_jiaoben_projects(self) -> None:
        if not self.project_dir:
            return
        try:
            cfg = read_project_cfg(self.project_dir)
        except Exception:
            return
        current = str((cfg.get("jiaoben") or {}).get("project_id") or "")
        self.pack_project_combo.blockSignals(True)
        self.pack_project_combo.clear()
        self.pack_project_combo.addItem("（手动输入 ID）", 0)
        for pid, label in fetch_projects_for_combo(cfg):
            self.pack_project_combo.addItem(label, pid)
        if current:
            idx = self.pack_project_combo.findData(int(current))
            if idx >= 0:
                self.pack_project_combo.setCurrentIndex(idx)
            else:
                self.pack_project_combo.setEditText(current)
        self.pack_project_combo.blockSignals(False)

    def _apply_runtime_preset(self, key: str) -> None:
        if not self._require_project():
            return
        try:
            label = apply_preset(self.project_dir, key)
        except Exception as exc:
            QMessageBox.warning(self, "预设失败", str(exc))
            return
        self.append(f"已应用性能预设: {label}")
        QMessageBox.information(self, "完成", f"已写入 project.json runtime\n{label}")

    def publish_hot_update(self) -> None:
        if not self._require_project():
            return
        dlg = PublishUpdateDialog(self, self.project_dir)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            manifest = dlg.publish()
        except Exception as exc:
            QMessageBox.warning(self, "发版失败", str(exc))
            return
        self.append(f"jiaoben 热更新已发布: v{manifest.get('version_code', '?')}")
        QMessageBox.information(self, "发版成功", f"已发布 v{manifest.get('version_code')}")

    def _run_pack_preflight(self) -> bool:
        errors, warnings = validate_before_pack(self.project_dir)
        if not errors and not warnings:
            return True
        parts: list[str] = []
        if errors:
            parts.append("错误（建议修复后再打包）：\n" + "\n".join(f"• {x}" for x in errors))
        if warnings:
            parts.append("提示（可忽略）：\n" + "\n".join(f"• {x}" for x in warnings))
        msg = "\n\n".join(parts)
        if errors:
            ans = QMessageBox.question(
                self,
                "打包预检",
                f"{msg}\n\n存在错误，仍要继续打包吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        else:
            ans = QMessageBox.question(
                self,
                "打包预检",
                f"{msg}\n\n仍要继续打包吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
        return ans == QMessageBox.StandardButton.Yes

    def _load_pack_fields(self) -> None:
        if not self.project_dir or not (self.project_dir / "project.json").is_file():
            self.pack_name_edit.clear()
            self.pack_pkg_edit.clear()
            self.pack_icon_edit.clear()
            self.pack_icon_preview.clear()
            self.pack_show_log_cb.setChecked(False)
            if hasattr(self, "pack_project_combo"):
                self.pack_project_combo.clear()
            return
        name, pkg, icon = ApkPackDialog.load_fields(self.project_dir)
        self.pack_name_edit.setText(name)
        self.pack_pkg_edit.setText(pkg)
        self.pack_icon_edit.setText(icon)
        try:
            from studio.services.layout_defaults import load_layout

            layout = load_layout(self.project_dir)
            self.pack_show_log_cb.setChecked(bool(layout.get("panel", {}).get("show_log", False)))
        except Exception:
            self.pack_show_log_cb.setChecked(False)
        self._refresh_pack_icon_preview()
        self._refresh_jiaoben_projects()

    def _refresh_pack_icon_preview(self) -> None:
        if not self.project_dir:
            return
        try:
            icon_text = self.pack_icon_edit.text().strip()
            cfg = {"name": self.pack_name_edit.text(), "package_id": self.pack_pkg_edit.text()}
            if icon_text:
                from packager.pack_metadata import resolve_icon_file

                p = resolve_icon_file(self.project_dir, icon_text)
                if p is None:
                    self.pack_icon_preview.setText("?")
                    return
                pix = QPixmap(str(p))
            else:
                pix = QPixmap(str(resolve_icon_source(self.project_dir, cfg)))
            if not pix.isNull():
                self.pack_icon_preview.setPixmap(
                    pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
            else:
                self.pack_icon_preview.setText("?")
        except Exception:
            self.pack_icon_preview.setText("?")

    def _pick_pack_icon(self) -> None:
        if not self.project_dir:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择应用图标",
            str(self.project_dir),
            "图片 (*.png *.jpg *.jpeg *.webp)",
        )
        if path:
            self.pack_icon_edit.setText(path)

    def _save_pack_fields(self, *, show_ok: bool = False) -> bool:
        if not self.project_dir:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return False
        err = validate_pack_fields(
            self.pack_name_edit.text(),
            self.pack_pkg_edit.text(),
            self.project_dir,
            self.pack_icon_edit.text(),
        )
        if err:
            QMessageBox.warning(self, "应用信息不完整", err)
            return False
        try:
            pid = resolve_jiaoben_project_id(self.pack_project_combo)
            combo_text = self.pack_project_combo.currentText().strip()
            if (
                pid <= 0
                and combo_text
                and combo_text != "（手动输入 ID）"
            ):
                QMessageBox.warning(
                    self,
                    "发卡项目 ID 无效",
                    "无法识别发卡项目 ID。\n\n"
                    "请从下拉列表选择项目，或仅在输入框中填写数字 ID（例如 123）。",
                )
                return False
            save_pack_metadata(
                self.project_dir,
                name=self.pack_name_edit.text(),
                package_id=self.pack_pkg_edit.text(),
                icon_text=self.pack_icon_edit.text(),
                jiaoben_project_id=pid if pid > 0 else 0,
            )
            from studio.services.layout_defaults import load_layout, save_layout

            layout = load_layout(self.project_dir)
            layout.setdefault("panel", {})["show_log"] = self.pack_show_log_cb.isChecked()
            save_layout(self.project_dir, layout)
        except ValueError as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return False
        self._load_pack_fields()
        if show_ok:
            msg = "已保存应用名 / 包名 / 图标到 project.json"
            if pid > 0:
                msg += f"（发卡项目 ID: {pid}）"
            self.append(msg)
        return True

    def _set_project(self, path: Path, *, remember: bool = True) -> None:
        self._save_current_project_quiet()
        PanelState.reset({})
        self.project_dir = path.resolve()
        self.path_label.setText(str(self.project_dir))
        self.append(f"已打开工程: {self.project_dir}")
        self._load_pack_fields()
        self.reload_script()
        self.layout_editor.on_project_opened()
        self.script_panel.on_project_opened()
        self.image_gallery.on_project_opened()
        self.yolo_models.on_project_opened()
        self.grab.on_project_opened()
        if hasattr(self, "command_toolbox"):
            self.command_toolbox.refresh_templates()
            self.command_toolbox.refresh_yolo_models()
        if remember:
            remember_project(self.project_dir)
            self._refresh_recent_list()

    def reload_script(self) -> None:
        main = self._script_path()
        if main and main.is_file():
            self.script_edit.blockSignals(True)
            self.script_edit.setPlainText(main.read_text(encoding="utf-8"))
            self.script_edit.blockSignals(False)
        self._script_dirty = False
        self._update_tab_titles()

    def save_script(self) -> None:
        if not self.project_dir:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return
        main = self._script_path()
        if main is None:
            main = self.project_dir / "main.lua"
        main.write_text(self.script_edit.toPlainText(), encoding="utf-8")
        self._script_dirty = False
        self._update_tab_titles()
        self.append(f"已保存 {main.name}")

    def _on_script_text_changed(self) -> None:
        if not self._script_dirty:
            self._script_dirty = True
            self._update_tab_titles()

    def _on_layout_dirty_changed(self, dirty: bool) -> None:
        self._update_tab_titles()

    def _update_tab_titles(self) -> None:
        layout_idx = self.tabs.indexOf(self.layout_editor)
        script_idx = self._script_tab_index()
        if layout_idx >= 0:
            title = self._tab_titles[2]
            if self.layout_editor.is_dirty:
                title += "*"
            self.tabs.setTabText(layout_idx, title)
        if script_idx >= 0:
            title = self._tab_titles[3]
            if self._script_dirty:
                title += "*"
            self.tabs.setTabText(script_idx, title)

    def closeEvent(self, event: QCloseEvent) -> None:
        unsaved: list[str] = []
        if self.layout_editor.is_dirty:
            unsaved.append("ui/layout.json")
        if self._script_dirty:
            unsaved.append("main.lua")
        if unsaved:
            names = "、".join(unsaved)
            ans = QMessageBox.question(
                self,
                "未保存的更改",
                f"以下文件有未保存修改：{names}\n是否保存后退出？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if ans == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if ans == QMessageBox.StandardButton.Save:
                if self._script_dirty:
                    self.save_script()
                if self.layout_editor.is_dirty:
                    self.layout_editor.save_to_project(silent=True)
                    if self.layout_editor.is_dirty:
                        event.ignore()
                        return
                if self.project_dir:
                    PanelState.save_sidecar(self.project_dir)
        elif self.project_dir:
            self._save_current_project_quiet()
        super().closeEvent(event)

    def run_lua_pc(self) -> None:
        if not self._require_project():
            return
        if self._lua_proc is not None and self._lua_proc.state() != QProcess.NotRunning:
            QMessageBox.information(self, "提示", "Lua 脚本正在运行")
            return
        self.save_script()
        if self.layout_editor.save_if_dirty():
            self.append_lua_log("已自动保存 ui/layout.json")
        from studio.runtime.panel_state import PanelState

        PanelState.save_sidecar(self.project_dir)
        summary = PanelState.format_summary()
        script_path = self._script_path()
        self.script_run_log.clear()
        idx = self._script_tab_index()
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
        self.append_lua_log("===== PC 运行 Lua =====")
        if script_path:
            self.append_lua_log(f"脚本: {script_path.name}")
        if PanelState.all():
            self.append_lua_log(f"panel 表单状态 → {summary}")
        serial = self.grab._serial() or self.adb.default_serial()
        if not serial:
            self.append_lua_log("警告: 未检测到 ADB 设备，bot.tap/截图 等可能失败")
        args = ["-u", "-m", "studio.runtime.lua_runner", str(self.project_dir)]
        if serial:
            args.extend(["--serial", serial])
        self._lua_proc = QProcess(self)
        self._lua_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._lua_proc.setWorkingDirectory(str(ROOT))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        self._lua_proc.setProcessEnvironment(env)
        self._lua_proc.readyReadStandardOutput.connect(self._on_lua_output)
        self._lua_proc.errorOccurred.connect(self._on_lua_process_error)
        self._lua_proc.finished.connect(self._on_lua_finished)
        self.append_lua_log("$ " + sys.executable + " " + " ".join(args))
        self._lua_proc.start(sys.executable, args)
        if not self._lua_proc.waitForStarted(5000):
            self.append_lua_log(f"错误: 无法启动 Lua 子进程 — {self._lua_proc.errorString()}")
            self._lua_proc = None
            return
        self.run_lua_btn.setEnabled(False)
        if self._stop_lua_action is not None:
            self._stop_lua_action.setEnabled(True)

    def _on_lua_process_error(self, err: QProcess.ProcessError) -> None:
        if self._lua_proc is None:
            return
        self.append_lua_log(f"进程错误: {self._lua_proc.errorString()} ({err})")

    def stop_lua_pc(self) -> None:
        if self._lua_proc is not None and self._lua_proc.state() != QProcess.NotRunning:
            self._lua_proc.kill()
            self.append_lua_log("已请求停止 Lua 运行")

    def _on_lua_output(self) -> None:
        if self._lua_proc is None:
            return
        data = bytes(self._lua_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if not data:
            return
        # 保留未换行结尾的片段，避免拆行丢失
        pending = getattr(self, "_lua_output_pending", "")
        text = pending + data
        lines = text.splitlines()
        if text.endswith("\n") or text.endswith("\r"):
            pending = ""
        else:
            pending = lines.pop() if lines else text
        self._lua_output_pending = pending
        for line in lines:
            self.append_lua_log(line.rstrip("\r"))
        if pending and not lines:
            pass  # 等待更多输出

    def _on_lua_finished(self, code: int, _status) -> None:
        pending = getattr(self, "_lua_output_pending", "")
        if pending.strip():
            self.append_lua_log(pending.rstrip("\r"))
        self._lua_output_pending = ""
        self.run_lua_btn.setEnabled(True)
        if self._stop_lua_action is not None:
            self._stop_lua_action.setEnabled(False)
        self.append_lua_log("Lua 运行完成" if code == 0 else f"Lua 运行失败，退出码 {code}")

    def _save_all_before_build(self) -> None:
        if self.project_dir:
            self.save_script()
            if self.layout_editor.save_if_dirty():
                self.append("已自动保存 ui/layout.json")
            PanelState.save_sidecar(self.project_dir)
            self._save_pack_fields(show_ok=False)

    def validate_project(self) -> None:
        if not self._require_project():
            return
        self._run([sys.executable, "-m", "packager.packager_cli", "validate", str(self.project_dir)])

    def _confirm_pack_metadata(self) -> bool:
        if not self.project_dir:
            return False
        if not self._save_pack_fields(show_ok=True):
            return False
        return True

    def build_apk(self) -> None:
        if not self._require_project():
            return
        if self._async_cmd.is_running():
            QMessageBox.information(self, "提示", "已有后台任务在执行，请稍候完成")
            return
        self._save_all_before_build()
        if not self._confirm_pack_metadata():
            return
        if not self._run_pack_preflight():
            return
        out, _ = QFileDialog.getSaveFileName(self, "输出 APK", "", "APK (*.apk)")
        if not out:
            return
        self._pack_phase = "build"
        self._pack_apk_out = Path(out)
        self._pack_serial = None
        self._pack_package_id = ""
        self._start_pack_build(install_after=False)

    def build_and_install(self) -> None:
        if not self._require_project():
            return
        if self._async_cmd.is_running():
            QMessageBox.information(self, "提示", "已有后台任务在执行，请稍候完成")
            return
        serial = self.grab._serial() or self.adb.default_serial()
        if not serial:
            QMessageBox.warning(self, "提示", "未检测到 ADB 设备，请先连接模拟器或真机")
            return
        self._save_all_before_build()
        if not self._confirm_pack_metadata():
            return
        if not self._run_pack_preflight():
            return
        DIST = ROOT / "dist"
        DIST.mkdir(parents=True, exist_ok=True)
        apk_out = DIST / f"{self.project_dir.name}.apk"
        cfg = json.loads((self.project_dir / "project.json").read_text(encoding="utf-8"))
        self._pack_phase = "build"
        self._pack_apk_out = apk_out
        self._pack_serial = serial
        self._pack_package_id = str(cfg.get("package_id", "") or "")
        self.append(f"目标设备: {serial}")
        self._start_pack_build(install_after=True)

    def _start_pack_build(self, *, install_after: bool) -> None:
        if not self.project_dir or not self._pack_apk_out:
            return
        self._pack_install_after = install_after
        cmd = [
            sys.executable,
            "-m",
            "packager.packager_cli",
            "build",
            str(self.project_dir),
            "-o",
            str(self._pack_apk_out),
        ]
        self._set_pack_busy(True, "正在打包 APK（可继续编辑，输出见下方日志）…")
        self.append("$ " + " ".join(cmd))
        if not self._async_cmd.start(sys.executable, cmd[1:], cwd=str(ROOT)):
            self._set_pack_busy(False)
            self.append("错误: 无法启动打包子进程")

    def _start_pack_install(self) -> None:
        if not self._pack_apk_out or not self._pack_serial:
            self._finish_pack_task(False, "缺少 APK 或设备信息")
            return
        if not self._pack_apk_out.is_file():
            self._finish_pack_task(False, "打包失败，已中止安装")
            return
        self._pack_phase = "install"
        self._set_pack_busy(True, f"正在安装到 {self._pack_serial}…")
        args = ["-s", self._pack_serial, "install", "-r", str(self._pack_apk_out)]
        self.append(f"$ {self.adb.adb_path} " + " ".join(args))
        if not self._async_cmd.start(self.adb.adb_path, args):
            self._finish_pack_task(False, "无法启动 adb install")

    def _start_pack_launch(self) -> None:
        if not self._pack_package_id or not self._pack_serial:
            self._finish_pack_task(True, f"已安装: {self._pack_apk_out.name if self._pack_apk_out else 'APK'}")
            return
        self._pack_phase = "launch"
        self._set_pack_busy(True, "正在启动应用…")
        args = [
            "-s",
            self._pack_serial,
            "shell",
            "monkey",
            "-p",
            self._pack_package_id,
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ]
        self.append(f"$ {self.adb.adb_path} " + " ".join(args))
        if not self._async_cmd.start(self.adb.adb_path, args):
            self._finish_pack_task(True, f"已安装（启动失败）: {self._pack_apk_out.name}")

    def _set_pack_busy(self, busy: bool, message: str = "") -> None:
        for btn in self._pack_action_buttons:
            btn.setEnabled(not busy)
        if busy:
            self.statusBar().showMessage(message or "后台任务执行中…")
        else:
            self.statusBar().showMessage("就绪")

    def _finish_pack_task(self, ok: bool, message: str) -> None:
        self._pack_phase = ""
        self._set_pack_busy(False)
        self.append(message if ok else f"失败: {message}")

    def _on_async_output(self, line: str) -> None:
        if line.strip():
            self.append(line)

    def _on_async_finished(self, code: int) -> None:
        phase = self._pack_phase
        if phase == "build":
            if code != 0:
                self._finish_pack_task(False, f"打包失败，退出码 {code}")
                return
            self.append("打包完成")
            if getattr(self, "_pack_install_after", False):
                self._start_pack_install()
            else:
                self._finish_pack_task(True, "完成")
                self._offer_publish_after_pack()
            return
        if phase == "install":
            if code != 0:
                self._finish_pack_task(False, f"ADB 安装失败，退出码 {code}")
                return
            self.append("安装完成")
            self._start_pack_launch()
            return
        if phase == "launch":
            name = self._pack_apk_out.name if self._pack_apk_out else "APK"
            if code == 0:
                self._finish_pack_task(True, f"已安装并启动: {name}")
            else:
                self._finish_pack_task(True, f"已安装（启动退出码 {code}）: {name}")
            self._offer_publish_after_pack()
            return
        if phase == "yaml_lua":
            self._set_pack_busy(False)
            if code == 0:
                self.reload_script()
                self.tabs.setCurrentIndex(self._script_tab_index())
                self.append("YAML→Lua 完成")
            else:
                self.append(f"YAML→Lua 失败，退出码 {code}")
            self._pack_phase = ""
            return
        self._pack_phase = ""
        self._set_pack_busy(False)
        self.append("完成" if code == 0 else f"退出码 {code}")

    def _offer_publish_after_pack(self) -> None:
        if not self.project_dir:
            return
        ans = QMessageBox.question(
            self,
            "发布热更新",
            "APK 已打包完成。是否立即发布脚本热更新到 jiaoben？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.publish_hot_update()

    def _require_project(self) -> bool:
        if self.project_dir and (self.project_dir / "project.json").is_file():
            return True
        QMessageBox.warning(self, "提示", "请先新建或打开工程")
        return False

    def _run(self, cmd: list[str]) -> None:
        if self._async_cmd.is_running():
            QMessageBox.information(self, "提示", "已有后台任务在执行，请稍候完成")
            return
        self._pack_phase = "cmd"
        self._set_pack_busy(True, "正在执行…")
        self.append("$ " + " ".join(cmd))
        if not self._async_cmd.start(cmd[0], cmd[1:]):
            self._set_pack_busy(False)
            self.append("错误: 无法启动子进程")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._async_cmd.is_running():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("任务进行中")
            box.setText("打包/安装仍在进行，确定要退出吗？")
            box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            box.setDefaultButton(QMessageBox.StandardButton.No)
            if box.exec() != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._async_cmd.kill()
        super().closeEvent(event)


def run_app() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
