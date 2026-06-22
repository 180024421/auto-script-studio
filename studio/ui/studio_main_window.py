"""Auto Script Studio 主窗口：复用 adb-ide 全套 IDE + 打包 APK。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QProcess
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMessageBox

from studio.adb_ide_bridge import ensure_adb_ide_path
from studio.services.adb_service import AdbService as PackAdbService

ensure_adb_ide_path()

from app.ui.main_window import MainWindow as AdbIdeMainWindow  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


class StudioMainWindow(AdbIdeMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Script Studio — ADB 抓抓 IDE + 打包 APK")
        self._pack_adb = PackAdbService()
        self._lua_proc: QProcess | None = None
        self._install_pack_menu()
        self._install_lua_menu()

    def _current_project_dir(self) -> Path | None:
        root = getattr(self.script_ide, "_project_root", None)
        if root and (Path(root) / "project.json").is_file():
            return Path(root)
        return None

    def _install_lua_menu(self) -> None:
        menu = self.menuBar().addMenu("Lua 调试")
        act = QAction("PC 运行 main.lua (ADB)", self)
        act.triggered.connect(self._run_lua_pc)
        menu.addAction(act)
        stop_act = QAction("停止 PC Lua", self)
        stop_act.triggered.connect(self._stop_lua_pc)
        menu.addAction(stop_act)

    def _install_pack_menu(self) -> None:
        menu = self.menuBar().addMenu("打包 APK")
        for label, slot in (
            ("校验工程", self._validate_project),
            ("打包 APK…", self._build_apk),
            ("打包并安装到设备", self._build_and_install),
        ):
            act = QAction(label, self)
            act.triggered.connect(slot)
            menu.addAction(act)

        hint = QAction(
            "说明：PC 端编辑 main.lua（bot API）；打包后 APK 在设备上离线执行",
            self,
        )
        hint.setEnabled(False)
        menu.addSeparator()
        menu.addAction(hint)

    def _require_project(self) -> Path | None:
        proj = self._current_project_dir()
        if proj:
            return proj
        QMessageBox.warning(
            self,
            "打包",
            "请先在左侧「脚本工程」打开含 project.json 的目录。\n"
            "推荐结构：main.lua + image/ + models/（与 adb-ide 工程目录相同）。",
        )
        return None

    def _run_packager(self, args: list[str]) -> int:
        cmd = [sys.executable, "-m", "packager.packager_cli", *args]
        self._log("$ " + " ".join(cmd))
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.stdout:
            self._log(proc.stdout.rstrip())
        if proc.stderr:
            self._log(proc.stderr.rstrip())
        self._log("完成" if proc.returncode == 0 else f"失败，退出码 {proc.returncode}")
        return proc.returncode

    def _run_lua_pc(self) -> None:
        proj = self._require_project()
        if not proj:
            return
        if self._lua_proc is not None and self._lua_proc.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Lua 调试", "Lua 脚本正在运行")
            return
        serial = self.current_serial or self._pack_adb.default_serial()
        args = ["-m", "studio.runtime.lua_runner", str(proj)]
        if serial:
            args.extend(["--serial", serial])
        self._lua_proc = QProcess(self)
        self._lua_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._lua_proc.setWorkingDirectory(str(REPO_ROOT))
        self._lua_proc.readyReadStandardOutput.connect(self._on_lua_output)
        self._lua_proc.finished.connect(self._on_lua_finished)
        self._log("$ " + sys.executable + " " + " ".join(args))
        self._lua_proc.start(sys.executable, args)

    def _stop_lua_pc(self) -> None:
        if self._lua_proc is not None and self._lua_proc.state() != QProcess.NotRunning:
            self._lua_proc.kill()
            self._log("已请求停止 PC Lua")

    def _on_lua_output(self) -> None:
        if self._lua_proc is None:
            return
        data = bytes(self._lua_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._log(line)

    def _on_lua_finished(self, code: int, _status) -> None:
        self._log("Lua 运行完成" if code == 0 else f"Lua 运行失败，退出码 {code}")

    def _validate_project(self) -> None:
        proj = self._require_project()
        if not proj:
            return
        self._run_packager(["validate", str(proj)])

    def _build_apk(self) -> None:
        proj = self._require_project()
        if not proj:
            return
        default = REPO_ROOT / "dist" / f"{proj.name}.apk"
        out, _ = QFileDialog.getSaveFileName(self, "输出 APK", str(default), "APK (*.apk)")
        if not out:
            return
        self._run_packager(["build", str(proj), "-o", out])

    def _build_and_install(self) -> None:
        proj = self._require_project()
        if not proj:
            return
        serial = self.current_serial or self._pack_adb.default_serial()
        if not serial:
            QMessageBox.warning(self, "打包", "请先在抓抓页连接 ADB 设备")
            return
        out = REPO_ROOT / "dist" / f"{proj.name}.apk"
        out.parent.mkdir(parents=True, exist_ok=True)
        if self._run_packager(["build", str(proj), "-o", str(out)]) != 0:
            return
        try:
            self._pack_adb.install_apk(str(out), serial, timeout=300)
            cfg = json.loads((proj / "project.json").read_text(encoding="utf-8"))
            pkg = cfg.get("package_id", "")
            if pkg:
                self._pack_adb.start_package(pkg, serial)
            self._log(f"已安装并启动: {out.name} @ {serial}")
        except Exception as exc:
            self._log(f"安装/启动失败: {exc}")
            QMessageBox.warning(self, "安装", str(exc))


def run_app() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = StudioMainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
