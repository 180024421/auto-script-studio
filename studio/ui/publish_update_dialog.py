"""打包成功后发布热更新到 jiaoben。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from packager.pack_metadata import read_project_cfg
from packager.publish_update import publish_to_jiaoben


class PublishUpdateDialog(QDialog):
    def __init__(self, parent, project_dir) -> None:
        super().__init__(parent)
        self.project_dir = project_dir
        self.setWindowTitle("发布脚本热更新到 jiaoben")
        self.setMinimumWidth(460)
        cfg = read_project_cfg(project_dir)
        runtime = cfg.get("runtime") or {}
        jiaoben = cfg.get("jiaoben") or {}
        license_cfg = cfg.get("license") or {}
        api_base = str(jiaoben.get("api_base") or license_cfg.get("api_base") or "")

        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"工程: {cfg.get('name')} · {cfg.get('package_id')}"))
        form = QFormLayout()
        self.api_edit = QLineEdit(api_base)
        form.addRow("API 地址", self.api_edit)
        self.version_spin = QSpinBox()
        self.version_spin.setRange(1, 999_999)
        self.version_spin.setValue(int(cfg.get("version_code", 1)) + 1)
        form.addRow("version_code", self.version_spin)
        self.changelog_edit = QTextEdit()
        self.changelog_edit.setPlaceholderText("用户 APK 弹窗中展示的更新说明")
        self.changelog_edit.setMaximumHeight(120)
        form.addRow("更新说明", self.changelog_edit)
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("可选 X-Script-Update-Token")
        form.addRow("发版 Token", self.token_edit)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def publish(self) -> dict:
        changelog = self.changelog_edit.toPlainText().strip()
        if not changelog:
            raise ValueError("请填写更新说明")
        return publish_to_jiaoben(
            self.project_dir,
            self.api_edit.text().strip(),
            bump_version=self.version_spin.value(),
            changelog=changelog,
            publish_token=self.token_edit.text().strip(),
        )
