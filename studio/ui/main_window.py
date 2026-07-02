"""PC Studio 主窗口 — 工程 / 抓抓 / 脚本。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from studio.ui.app_theme import apply_theme, set_button_role
from studio.ui.grab_widget import GrabWidget
from studio.ui.layout_editor_widget import LayoutEditorWidget
from studio.ui.lua_highlighter import LuaHighlighter
from studio.ui.page_shell import (
    hint_label,
    main_column,
    page_root,
    section_title,
    side_column,
    three_columns,
    tool_button_row,
)
from studio.services.adb_service import AdbService
from studio.ui.apk_pack_dialog import ApkPackDialog

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

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_project_tab(), "  工程  ")
        self.grab = GrabWidget(lambda: self.project_dir)
        self.grab.log_message.connect(self.append)
        self.grab.insert_lua.connect(self._insert_lua_to_script)
        self.tabs.addTab(self.grab, "  抓抓  ")
        self.layout_editor = LayoutEditorWidget(lambda: str(self.project_dir) if self.project_dir else None)
        self.layout_editor.layout_changed.connect(self.grab.apply_layout_from_editor)
        self.layout_editor.request_pick_mode.connect(self._on_request_pick_mode)
        self.layout_editor.insert_lua.connect(self._insert_lua_to_script)
        self.grab.panel_position_picked.connect(self.layout_editor.set_panel_position)
        self.grab.button_coords_picked.connect(self._on_button_coords_picked)
        self.tabs.addTab(self.layout_editor, "  浮动面板  ")
        self._script_tab = self._build_script_tab()
        self.tabs.addTab(self._script_tab, "  脚本  ")

        tab_wrap = QWidget()
        tab_layout = QVBoxLayout(tab_wrap)
        tab_layout.setContentsMargins(12, 6, 12, 10)
        tab_layout.addWidget(self.tabs)
        root.addWidget(tab_wrap, 1)

        self.setCentralWidget(central)

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("AppHeader")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 14, 24, 14)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Auto Script Studio")
        title.setObjectName("AppTitle")
        sub = QLabel("Android 脚本开发 · 抓抓联调 · 一键打包 APK")
        sub.setObjectName("AppSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        layout.addLayout(title_col)
        layout.addStretch()

        self.path_label = QLabel("未打开工程")
        self.path_label.setObjectName("ProjectChip")
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        return bar

    def _build_project_tab(self) -> QWidget:
        w = QWidget()
        root = page_root(w)
        root.addWidget(
            hint_label("左：工程快捷操作 · 中：运行日志（打包、校验、安装输出）")
        )

        left, left_lay = side_column(240, 300)
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
        left_lay.addWidget(section_title("构建"))
        tool_button_row(
            left_lay,
            [
                ("校验工程", self.validate_project, "ghost"),
                ("YAML→Lua", self.convert_yaml_to_lua, "ghost"),
                ("打包 APK", self.build_apk, "accent"),
                ("打包安装", self.build_and_install, "primary"),
            ],
            columns=1,
        )
        left_lay.addStretch()

        center, center_lay = main_column()
        center_lay.addWidget(section_title("运行日志"))
        self.log = QTextEdit()
        self.log.setObjectName("LogConsole")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("操作与打包输出将显示在这里…")
        center_lay.addWidget(self.log, 1)

        root.addLayout(three_columns(left, center), 1)

        root.addWidget(
            hint_label("推荐：打开工程 → 抓抓截图 → 浮动面板布局 → 编辑脚本 → 打包安装")
        )
        return w

    def _build_script_tab(self) -> QWidget:
        w = QWidget()
        root = page_root(w)
        root.addWidget(hint_label("编辑 main.lua；保存后可在本页 PC 运行 Lua，或与抓抓/浮动面板联调"))

        editor_card, editor_lay = main_column()
        toolbar = QHBoxLayout()
        save_btn = QPushButton("保存")
        set_button_role(save_btn, "accent")
        save_btn.clicked.connect(self.save_script)
        reload_btn = QPushButton("重新加载")
        set_button_role(reload_btn, "ghost")
        reload_btn.clicked.connect(self.reload_script)
        self.run_lua_btn = QPushButton("PC 运行 Lua")
        set_button_role(self.run_lua_btn, "primary")
        self.run_lua_btn.clicked.connect(self.run_lua_pc)
        self.stop_lua_btn = QPushButton("停止")
        set_button_role(self.stop_lua_btn, "danger")
        self.stop_lua_btn.clicked.connect(self.stop_lua_pc)
        self.stop_lua_btn.setEnabled(False)
        toolbar.addWidget(section_title("脚本"))
        toolbar.addStretch()
        toolbar.addWidget(save_btn)
        toolbar.addWidget(reload_btn)
        toolbar.addWidget(self.run_lua_btn)
        toolbar.addWidget(self.stop_lua_btn)
        editor_lay.addLayout(toolbar)

        self.script_edit = QTextEdit()
        self.script_edit.setObjectName("ScriptEditor")
        self.script_edit.setPlaceholderText("打开工程后编辑 main.lua …")
        font = QFont("Cascadia Mono")
        if not font.exactMatch():
            font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.script_edit.setFont(font)
        self._lua_highlighter = LuaHighlighter(self.script_edit.document())
        editor_lay.addWidget(self.script_edit, 1)
        root.addWidget(editor_card, 1)

        QShortcut(QKeySequence.StandardKey.Save, self.script_edit, self.save_script)
        return w

    def _script_tab_index(self) -> int:
        return self.tabs.indexOf(self._script_tab)

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
        cur = self.script_edit.toPlainText().rstrip()
        block = snippet.strip()
        text = (cur + "\n\n" + block + "\n") if cur else block + "\n"
        self.script_edit.setPlainText(text)
        idx = self.tabs.indexOf(self._script_tab)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)
        self.append("已从抓抓页插入 Lua 片段到脚本编辑")

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
        self._run([sys.executable, str(ROOT / "tools" / "yaml_to_lua.py"), str(src)])
        self.reload_script()
        self.tabs.setCurrentIndex(self._script_tab_index())

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

    def _set_project(self, path: Path) -> None:
        self.project_dir = path
        self.path_label.setText(str(path))
        self.append(f"已打开工程: {path}")
        self.reload_script()
        self.layout_editor.on_project_opened()
        self.grab.on_project_opened()
        self.grab.apply_layout_from_editor(self.layout_editor.current_layout())

    def reload_script(self) -> None:
        main = self._script_path()
        if main and main.is_file():
            self.script_edit.setPlainText(main.read_text(encoding="utf-8"))

    def save_script(self) -> None:
        if not self.project_dir:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return
        main = self._script_path()
        if main is None:
            main = self.project_dir / "main.lua"
        main.write_text(self.script_edit.toPlainText(), encoding="utf-8")
        self.append(f"已保存 {main.name}")

    def run_lua_pc(self) -> None:
        if not self._require_project():
            return
        if self._lua_proc is not None and self._lua_proc.state() != QProcess.NotRunning:
            QMessageBox.information(self, "提示", "Lua 脚本正在运行")
            return
        self.save_script()
        if self.layout_editor.save_if_dirty():
            self.append("已自动保存 ui/layout.json")
        from studio.runtime.panel_state import PanelState

        PanelState.save_sidecar(self.project_dir)
        summary = PanelState.format_summary()
        if PanelState.all():
            self.append(f"panel 表单状态 → {summary}")
        serial = self.grab._serial() or self.adb.default_serial()
        args = ["-m", "studio.runtime.lua_runner", str(self.project_dir)]
        if serial:
            args.extend(["--serial", serial])
        self._lua_proc = QProcess(self)
        self._lua_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._lua_proc.setWorkingDirectory(str(ROOT))
        self._lua_proc.readyReadStandardOutput.connect(self._on_lua_output)
        self._lua_proc.finished.connect(self._on_lua_finished)
        self.append("$ " + sys.executable + " " + " ".join(args))
        self._lua_proc.start(sys.executable, args)
        self.run_lua_btn.setEnabled(False)
        self.stop_lua_btn.setEnabled(True)

    def stop_lua_pc(self) -> None:
        if self._lua_proc is not None and self._lua_proc.state() != QProcess.NotRunning:
            self._lua_proc.kill()
            self.append("已请求停止 Lua 运行")

    def _on_lua_output(self) -> None:
        if self._lua_proc is None:
            return
        data = bytes(self._lua_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self.append(line)

    def _on_lua_finished(self, code: int, _status) -> None:
        self.run_lua_btn.setEnabled(True)
        self.stop_lua_btn.setEnabled(False)
        self.append("Lua 运行完成" if code == 0 else f"Lua 运行失败，退出码 {code}")

    def _save_all_before_build(self) -> None:
        if self.project_dir:
            self.save_script()
            if self.layout_editor.save_if_dirty():
                self.append("已自动保存 ui/layout.json")

    def validate_project(self) -> None:
        if not self._require_project():
            return
        self._run([sys.executable, "-m", "packager.packager_cli", "validate", str(self.project_dir)])

    def _confirm_pack_metadata(self) -> bool:
        if not self.project_dir:
            return False
        dlg = ApkPackDialog(self, self.project_dir)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        dlg.save_to_project()
        self.append("已保存应用名 / 包名 / 图标到 project.json")
        return True

    def build_apk(self) -> None:
        if not self._require_project():
            return
        self._save_all_before_build()
        if not self._confirm_pack_metadata():
            return
        out, _ = QFileDialog.getSaveFileName(self, "输出 APK", "", "APK (*.apk)")
        if not out:
            return
        self._run(
            [
                sys.executable,
                "-m",
                "packager.packager_cli",
                "build",
                str(self.project_dir),
                "-o",
                out,
            ]
        )

    def build_and_install(self) -> None:
        if not self._require_project():
            return
        serial = self.grab._serial() or self.adb.default_serial()
        if not serial:
            QMessageBox.warning(self, "提示", "未检测到 ADB 设备，请先连接模拟器或真机")
            return
        self._save_all_before_build()
        if not self._confirm_pack_metadata():
            return
        DIST = ROOT / "dist"
        DIST.mkdir(parents=True, exist_ok=True)
        apk_out = DIST / f"{self.project_dir.name}.apk"
        self.append(f"目标设备: {serial}")
        self._run(
            [
                sys.executable,
                "-m",
                "packager.packager_cli",
                "build",
                str(self.project_dir),
                "-o",
                str(apk_out),
            ]
        )
        if not apk_out.is_file():
            self.append("打包失败，已中止安装")
            return
        try:
            self.adb.install_apk(str(apk_out), serial)
            cfg = json.loads((self.project_dir / "project.json").read_text(encoding="utf-8"))
            package_id = cfg.get("package_id", "")
            if package_id:
                self.adb.start_package(package_id, serial)
            self.append(f"已安装并启动: {apk_out.name}")
        except Exception as exc:
            self.append(f"安装/启动失败: {exc}")

    def _require_project(self) -> bool:
        if self.project_dir and (self.project_dir / "project.json").is_file():
            return True
        QMessageBox.warning(self, "提示", "请先新建或打开工程")
        return False

    def _run(self, cmd: list[str]) -> None:
        self.append("$ " + " ".join(cmd))
        try:
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            if proc.stdout:
                self.append(proc.stdout.strip())
            if proc.stderr:
                self.append(proc.stderr.strip())
            self.append("完成" if proc.returncode == 0 else f"退出码 {proc.returncode}")
        except Exception as exc:
            self.append(f"错误: {exc}")


def run_app() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
