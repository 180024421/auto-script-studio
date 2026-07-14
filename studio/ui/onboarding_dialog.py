"""首次启动引导与环境预检对话框。"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
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
    """首次引导：可点按钮直接打开示例 / 抓抓。"""

    request_open_demo = Signal()
    request_open_grab = Signal()

    def __init__(self, parent=None, *, adb_path: str = "adb") -> None:
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 Auto Script Studio")
        self.setMinimumWidth(520)
        self._adb_path = adb_path

        root = QVBoxLayout(self)
        root.setSpacing(12)

        title = QLabel("三步上手（推荐跟着做）")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        intro = QLabel(
            "① 连接模拟器或真机（下方预检应显示 ADB 正常）\n"
            "② 点「打开示例并试跑」— 自动打开 demo 并在电脑上跑一遍\n"
            "③ 需要取色取点时，再去「抓抓」页截图"
        )
        intro.setWordWrap(True)
        intro.setObjectName("HintLabel")
        root.addWidget(intro)

        step_row = QHBoxLayout()
        step_row.setSpacing(8)
        demo_btn = QPushButton("打开示例并试跑")
        set_button_role(demo_btn, "primary")
        demo_btn.setMinimumHeight(38)
        demo_btn.clicked.connect(self._on_open_demo)
        grab_btn = QPushButton("去抓抓截图")
        set_button_role(grab_btn, "accent")
        grab_btn.setMinimumHeight(38)
        grab_btn.clicked.connect(self._on_open_grab)
        step_row.addWidget(demo_btn)
        step_row.addWidget(grab_btn)
        root.addLayout(step_row)

        root.addWidget(QLabel("环境预检"))
        self.report_edit = QTextEdit()
        self.report_edit.setReadOnly(True)
        self.report_edit.setMinimumHeight(120)
        root.addWidget(self.report_edit)

        recheck = QPushButton("重新检测")
        set_button_role(recheck, "ghost")
        recheck.clicked.connect(self._run_check)
        root.addWidget(recheck)

        self.skip_cb = QCheckBox("不再显示此引导")
        self.skip_cb.setChecked(True)
        root.addWidget(self.skip_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("我知道了")
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

        self._run_check()

    def _run_check(self) -> None:
        report = run_preflight(self._adb_path)
        self.report_edit.setPlainText(format_report_text(report))

    def _finish_skip(self) -> None:
        if self.skip_cb.isChecked():
            mark_onboarding_done()

    def _on_open_demo(self) -> None:
        self._finish_skip()
        self.request_open_demo.emit()
        self.accept()

    def _on_open_grab(self) -> None:
        self._finish_skip()
        self.request_open_grab.emit()
        self.accept()

    def accept(self) -> None:
        self._finish_skip()
        super().accept()
