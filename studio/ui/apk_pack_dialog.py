"""打包 APK 前填写应用名、包名与图标（可选弹窗，逻辑与工程页共用）。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
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

from packager.icon_processor import default_icon_path, resolve_icon_source
from packager.pack_metadata import read_project_cfg, save_pack_metadata, validate_pack_fields


class ApkPackDialog(QDialog):
    def __init__(self, parent, project_dir: Path) -> None:
        super().__init__(parent)
        self.project_dir = project_dir.resolve()
        self.setWindowTitle("打包 APK — 应用信息")
        self.setMinimumWidth(480)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        cfg = read_project_cfg(self.project_dir)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(cfg.get("name", ""))
        self.name_edit.setPlaceholderText("例如：我的挂机脚本")
        form.addRow("软件名称", self.name_edit)

        self.pkg_edit = QLineEdit(cfg.get("package_id", ""))
        self.pkg_edit.setPlaceholderText("com.example.myscript")
        form.addRow("包名", self.pkg_edit)

        jiaoben_cfg = cfg.get("jiaoben") or {}
        self.project_id_edit = QLineEdit(str(jiaoben_cfg.get("project_id") or ""))
        self.project_id_edit.setPlaceholderText("在 jiaoben 管理端「脚本发版」中查看项目 ID")
        form.addRow("发卡项目 ID", self.project_id_edit)

        icon_row = QHBoxLayout()
        self.icon_edit = QLineEdit((cfg.get("icon") or "").strip())
        self.icon_edit.setPlaceholderText("留空则使用默认猫咪图标")
        browse = QPushButton("选择图标…")
        browse.clicked.connect(self._pick_icon)
        clear_btn = QPushButton("恢复默认")
        clear_btn.clicked.connect(self._use_default_icon)
        icon_row.addWidget(self.icon_edit, 1)
        icon_row.addWidget(browse)
        icon_row.addWidget(clear_btn)
        form.addRow("应用图标", icon_row)
        root.addLayout(form)

        self.preview = QLabel()
        self.preview.setFixedSize(96, 96)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "border:1px solid #CBD5E1;border-radius:12px;background:#F8FAFC;"
        )
        hint = QLabel("自定义图标会写入工程 icon.png，并用于桌面图标与悬浮球。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B;font-size:12px;")
        jiaoben_hint = QLabel(
            "发卡项目 ID 用于脚本热更新发版归属；须与 jiaoben 管理端绑定该包名的项目一致。"
        )
        jiaoben_hint.setWordWrap(True)
        jiaoben_hint.setStyleSheet("color:#64748B;font-size:12px;")
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.preview)
        preview_row.addWidget(hint, 1)
        root.addLayout(preview_row)
        root.addWidget(jiaoben_hint)

        self.icon_edit.textChanged.connect(self._refresh_preview)
        self._refresh_preview()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _resolved_icon_path(self) -> Path:
        icon_text = self.icon_edit.text().strip()
        if icon_text:
            from packager.pack_metadata import resolve_icon_file

            path = resolve_icon_file(self.project_dir, icon_text)
            if path is not None:
                return path
        cfg = read_project_cfg(self.project_dir)
        cfg.pop("icon", None)
        return resolve_icon_source(self.project_dir, cfg)

    def _refresh_preview(self) -> None:
        try:
            path = self._resolved_icon_path()
            pix = QPixmap(str(path))
            if not pix.isNull():
                self.preview.setPixmap(
                    pix.scaled(
                        88,
                        88,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.preview.setToolTip(str(path))
            else:
                self.preview.setText("无预览")
        except Exception as exc:
            self.preview.setText("无效")
            self.preview.setToolTip(str(exc))

    def _pick_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择应用图标",
            str(self.project_dir),
            "图片 (*.png *.jpg *.jpeg *.webp)",
        )
        if path:
            self.icon_edit.setText(path)

    def _use_default_icon(self) -> None:
        self.icon_edit.clear()

    def _on_accept(self) -> None:
        err = validate_pack_fields(
            self.name_edit.text(),
            self.pkg_edit.text(),
            self.project_dir,
            self.icon_edit.text(),
        )
        if err:
            QMessageBox.warning(self, "提示", err)
            return
        pid_text = self.project_id_edit.text().strip()
        if pid_text and not pid_text.isdigit():
            QMessageBox.warning(self, "提示", "发卡项目 ID 须为正整数")
            return
        try:
            self._resolved_icon_path()
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "图标无效", str(exc))
            return
        self.accept()

    def save_to_project(self) -> None:
        pid_text = self.project_id_edit.text().strip()
        jiaoben_project_id = int(pid_text) if pid_text else 0
        save_pack_metadata(
            self.project_dir,
            name=self.name_edit.text(),
            package_id=self.pkg_edit.text(),
            icon_text=self.icon_edit.text(),
            jiaoben_project_id=jiaoben_project_id,
        )

    @staticmethod
    def load_fields(project_dir: Path) -> tuple[str, str, str]:
        cfg = read_project_cfg(project_dir)
        icon = (cfg.get("icon") or "").strip()
        if icon and (project_dir / icon).is_file():
            icon = str((project_dir / icon).resolve())
        return str(cfg.get("name", "")), str(cfg.get("package_id", "")), icon
