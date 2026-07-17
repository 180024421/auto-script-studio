"""新建工程 / 从 demo 另存为 向导。"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip("_")
    return s or "myscript"


class NewProjectWizard(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        template_dir: Path,
        demo_dir: Path,
        default_parent: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建工程")
        self.setMinimumWidth(480)
        self.template_dir = template_dir
        self.demo_dir = demo_dir
        self.result_path: Path | None = None

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("创建可独立修改的工程（不会直接改仓库里的 demo）。"))

        form = QFormLayout()
        self.name_edit = QLineEdit("我的脚本")
        form.addRow("工程名称", self.name_edit)
        self.pkg_edit = QLineEdit("com.autoscript.myscript")
        form.addRow("包名", self.pkg_edit)
        self.source_combo = QComboBox()
        self.source_combo.addItem("空白模板", "template")
        self.source_combo.addItem("基于 demo-game（推荐）", "demo")
        form.addRow("起点", self.source_combo)
        self.input_combo = QComboBox()
        self.input_combo.addItem("无障碍（真机友好）", "accessibility")
        self.input_combo.addItem("Root（模拟器）", "root")
        form.addRow("触控模式", self.input_combo)
        dest_row = QHBoxLayout()
        self.dest_edit = QLineEdit(str(default_parent or Path.home() / "Documents" / "ass-projects"))
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._browse_parent)
        dest_row.addWidget(self.dest_edit, 1)
        dest_row.addWidget(browse)
        form.addRow("父目录", dest_row)
        lay.addLayout(form)

        self.name_edit.textChanged.connect(self._sync_pkg)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _sync_pkg(self, text: str) -> None:
        if self.pkg_edit.isModified():
            return
        self.pkg_edit.setText(f"com.autoscript.{_slug(text)}")

    def _browse_parent(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择父目录", self.dest_edit.text())
        if path:
            self.dest_edit.setText(path)

    def _accept(self) -> None:
        name = self.name_edit.text().strip()
        pkg = self.pkg_edit.text().strip()
        parent = Path(self.dest_edit.text().strip())
        if not name or not pkg:
            QMessageBox.warning(self, "提示", "请填写工程名称与包名")
            return
        if "." not in pkg or pkg.startswith(".") or pkg.endswith("."):
            QMessageBox.warning(self, "提示", "包名格式不正确，如 com.autoscript.demo")
            return
        folder_name = _slug(name)
        dest = parent / folder_name
        if dest.exists() and any(dest.iterdir()):
            QMessageBox.warning(self, "提示", f"目录非空: {dest}")
            return
        source_key = self.source_combo.currentData()
        src = self.demo_dir if source_key == "demo" else self.template_dir
        if not (src / "project.json").is_file():
            QMessageBox.warning(self, "提示", f"模板不存在: {src}")
            return
        parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        ignore = shutil.ignore_patterns(
            ".git",
            ".publish-staging",
            "__pycache__",
            "*.pyc",
            ".idea",
        )
        shutil.copytree(src, dest, ignore=ignore)
        cfg_path = dest / "project.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg["name"] = name
        cfg["package_id"] = pkg
        runtime = cfg.setdefault("runtime", {})
        runtime["input_mode"] = str(self.input_combo.currentData())
        # 新工程默认关掉远端 license，避免首日卡授权
        license_cfg = cfg.setdefault("license", {})
        license_cfg["enabled"] = False
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.result_path = dest
        self.accept()


def fork_demo_to(parent, *, demo_dir: Path, default_parent: Path | None = None) -> Path | None:
    dlg = NewProjectWizard(
        parent,
        template_dir=demo_dir,  # unused when forced demo
        demo_dir=demo_dir,
        default_parent=default_parent,
    )
    dlg.setWindowTitle("另存为我的工程")
    dlg.source_combo.setCurrentIndex(1)
    dlg.source_combo.setEnabled(False)
    dlg.name_edit.setText("我的脚本")
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.result_path
