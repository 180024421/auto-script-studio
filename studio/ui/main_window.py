"""PC Studio 主窗口 — 工程 / 抓抓 / 脚本。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
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

from studio.ui.grab_widget import GrabWidget
from studio.services.adb_service import AdbService

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "studio" / "resources" / "project-template"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Script Studio — 按键精灵式 Android 脚本助手")
        self.resize(1100, 720)
        self.project_dir: Path | None = None
        self.adb = AdbService()
        self._lua_proc: QProcess | None = None

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_project_tab(), "工程")
        self.grab = GrabWidget(lambda: self.project_dir)
        self.grab.log_message.connect(self.append)
        self.grab.insert_lua.connect(self._insert_lua_to_script)
        self.tabs.addTab(self.grab, "抓抓 · 找图找色识字")
        self.tabs.addTab(self._build_script_tab(), "脚本编辑")
        self.setCentralWidget(self.tabs)

    def _build_project_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self.path_label = QLabel("未打开工程")
        layout.addWidget(self.path_label)

        row = QHBoxLayout()
        for text, slot in [
            ("新建工程", self.new_project),
            ("打开工程", self.open_project),
            ("校验工程", self.validate_project),
            ("打包 APK", self.build_apk),
            ("打包并安装", self.build_and_install),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            row.addWidget(b)
        layout.addLayout(row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        hint = QLabel(
            "PC IDE 负责抓抓、取色、存模板、截图与 main.lua 编辑；打包后的 APK 在设备上运行已打包脚本。\n"
            "「抓抓」页连 ADB 截图取色，可一键插入找色/找图/识字 Lua；「脚本编辑」可 PC 运行 Lua（ADB）联调。\n"
            "识字/YOLO 测试需可选安装 paddleocr / ultralytics。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return w

    def _build_script_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        row = QHBoxLayout()
        save_btn = QPushButton("保存 main.lua")
        save_btn.clicked.connect(self.save_script)
        reload_btn = QPushButton("重新加载")
        reload_btn.clicked.connect(self.reload_script)
        self.run_lua_btn = QPushButton("PC 运行 Lua (ADB)")
        self.run_lua_btn.clicked.connect(self.run_lua_pc)
        self.stop_lua_btn = QPushButton("停止")
        self.stop_lua_btn.clicked.connect(self.stop_lua_pc)
        self.stop_lua_btn.setEnabled(False)
        row.addWidget(save_btn)
        row.addWidget(reload_btn)
        row.addWidget(self.run_lua_btn)
        row.addWidget(self.stop_lua_btn)
        row.addStretch()
        layout.addLayout(row)
        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText("打开工程后编辑 main.lua …")
        layout.addWidget(self.script_edit)
        return w

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
        self.tabs.setCurrentIndex(2)
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

    def validate_project(self) -> None:
        if not self._require_project():
            return
        self._run([sys.executable, "-m", "packager.packager_cli", "validate", str(self.project_dir)])

    def build_apk(self) -> None:
        if not self._require_project():
            return
        self.save_script()
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
        serial = self.adb.default_serial()
        if not serial:
            QMessageBox.warning(self, "提示", "未检测到 ADB 设备，请先连接模拟器或真机")
            return
        self.save_script()
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
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
