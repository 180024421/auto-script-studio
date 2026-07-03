"""首次启动引导与环境预检对话框。"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from studio.services.env_preflight import format_report_text, run_preflight
from studio.ui.app_theme import set_button_role

_SETTINGS = Path.home() / ".auto-script-studio" / "settings.json"


def _load_settings() -> dict:
    if not _SETTINGS.is_file():
        return {}
    try:
        return json.loads(_SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings(data: dict) -> None:
    _SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def should_show_onboarding() -> bool:
    data = _load_settings()
    return not data.get("onboarding_done", False)


def mark_onboarding_done() -> None:
    data = _load_settings()
    data["onboarding_done"] = True
    _save_settings(data)


class OnboardingDialog(QDialog):
    def __init__(self, parent=None, *, adb_path: str = "adb") -> None:
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 Auto Script Studio")
        self.setMinimumWidth(520)
        self._adb_path = adb_path

        root = QVBoxLayout(self)
        root.setSpacing(12)

        title = QLabel("快速开始")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        intro = QLabel(
            "1. 连接模拟器或真机（ADB）\n"
            "2. 打开或新建 Lua 工程\n"
            "3. 在「抓抓」页截图取点，一键插入脚本\n"
            "4. 打包 APK 或 PC 联调运行"
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        root.addWidget(QLabel("环境预检"))
        self.report_edit = QTextEdit()
        self.report_edit.setReadOnly(True)
        self.report_edit.setMinimumHeight(140)
        root.addWidget(self.report_edit)

        btn_row = QVBoxLayout()
        recheck = QPushButton("重新检测")
        set_button_role(recheck, "ghost")
        recheck.clicked.connect(self._run_check)
        btn_row.addWidget(recheck)
        root.addLayout(btn_row)

        self.skip_cb = QCheckBox("不再显示此引导")
        self.skip_cb.setChecked(True)
        root.addWidget(self.skip_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

        self._run_check()

    def _run_check(self) -> None:
        report = run_preflight(self._adb_path)
        self.report_edit.setPlainText(format_report_text(report))

    def accept(self) -> None:
        if self.skip_cb.isChecked():
            mark_onboarding_done()
        super().accept()
