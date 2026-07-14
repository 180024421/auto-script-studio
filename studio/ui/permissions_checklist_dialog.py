"""安装 APK 后的手机权限清单（傻瓜式提示）。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

_CHECKLIST = (
    "请在手机上依次开启以下权限，脚本才能正常运行：\n\n"
    "1. 无障碍服务 — 允许本应用（用于自动点击）\n"
    "2. 悬浮窗 / 显示在其他应用上层 — 显示控制面板\n"
    "3. 录屏或截图权限 — 抓图、找色找图（按系统提示授权）\n"
    "4. 存储权限 — 若需读写模板图（部分机型）\n\n"
    "开启后回到应用，点悬浮球 ▶ 开始运行脚本。"
)


def show_permissions_checklist(parent=None) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("请在手机上开启权限")
    dlg.setMinimumWidth(460)
    lay = QVBoxLayout(dlg)
    title = QLabel("安装成功！还差这几步")
    title.setObjectName("DialogTitle")
    lay.addWidget(title)
    body = QLabel(_CHECKLIST)
    body.setWordWrap(True)
    lay.addWidget(body)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
    buttons.accepted.connect(dlg.accept)
    lay.addWidget(buttons)
    dlg.exec()


def ask_open_grab_after_install(parent=None) -> bool:
    ans = QMessageBox.question(
        parent,
        "去抓抓试试？",
        "权限开好后，可在「抓抓」页连接设备并截图取色/取点。\n是否现在切换到抓抓页？",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    return ans == QMessageBox.StandardButton.Yes
