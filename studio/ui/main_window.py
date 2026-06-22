"""PC Studio 主窗口（最小可用版）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "studio" / "resources" / "project-template"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Auto Script Studio")
        self.resize(900, 600)
        self.project_dir: Path | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        row = QHBoxLayout()
        self.path_label = QLabel("未打开工程")
        row.addWidget(self.path_label, 1)
        layout.addLayout(row)

        btn_row = QHBoxLayout()
        for text, slot in [
            ("新建工程", self.new_project),
            ("打开工程", self.open_project),
            ("校验工程", self.validate_project),
            ("打包 APK", self.build_apk),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        hint = QLabel(
            "开发联调可继续使用 adb-ide；本 Studio 负责工程管理与打包。\n"
            "文档: docs/script-api.md"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def append(self, msg: str) -> None:
        self.log.append(msg)

    def new_project(self) -> None:
        dest = QFileDialog.getExistingDirectory(self, "选择新建工程目录")
        if not dest:
            return
        dest_path = Path(dest)
        name = dest_path.name
        if any(dest_path.iterdir()):
            QMessageBox.warning(self, "提示", "目录非空，请选空目录")
            return
        import shutil

        shutil.copytree(TEMPLATE, dest_path, dirs_exist_ok=False)
        cfg = dest_path / "project.json"
        text = cfg.read_text(encoding="utf-8").replace("com.autoscript.template", f"com.autoscript.{name}")
        cfg.write_text(text.replace("Template Script", name), encoding="utf-8")
        self.project_dir = dest_path
        self.path_label.setText(str(dest_path))
        self.append(f"已创建工程: {dest_path}")

    def open_project(self) -> None:
        dest = QFileDialog.getExistingDirectory(self, "打开脚本工程")
        if not dest:
            return
        self.project_dir = Path(dest)
        self.path_label.setText(str(self.project_dir))
        self.append(f"已打开: {self.project_dir}")

    def validate_project(self) -> None:
        if not self._require_project():
            return
        cmd = [sys.executable, "-m", "packager.packager_cli", "validate", str(self.project_dir)]
        self._run(cmd)

    def build_apk(self) -> None:
        if not self._require_project():
            return
        out, _ = QFileDialog.getSaveFileName(self, "输出 APK", "", "APK (*.apk)")
        if not out:
            return
        cmd = [
            sys.executable,
            "-m",
            "packager.packager_cli",
            "build",
            str(self.project_dir),
            "-o",
            out,
        ]
        self._run(cmd)

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
            if proc.returncode != 0:
                self.append(f"退出码 {proc.returncode}")
            else:
                self.append("完成")
        except Exception as exc:
            self.append(f"错误: {exc}")


def run_app() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
