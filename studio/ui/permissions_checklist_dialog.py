"""安装后权限引导：文案 + 可选 ADB 深链打开系统设置页。"""

from __future__ import annotations

import subprocess

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
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

# 常见设置 Intent（不同 ROM 可能无效，失败时忽略）
_INTENTS = (
    ("打开无障碍设置", ["shell", "am", "start", "-a", "android.settings.ACCESSIBILITY_SETTINGS"]),
    (
        "打开悬浮窗设置",
        [
            "shell",
            "am",
            "start",
            "-a",
            "android.settings.action.MANAGE_OVERLAY_PERMISSION",
        ],
    ),
)


def _adb_run(adb_path: str, serial: str | None, args: list[str]) -> tuple[bool, str]:
    cmd = [adb_path]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=12,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, out
    except Exception as exc:
        return False, str(exc)


def show_permissions_checklist(
    parent=None,
    *,
    adb_path: str = "adb",
    serial: str | None = None,
    package_id: str = "",
) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("请在手机上开启权限")
    dlg.setMinimumWidth(480)
    lay = QVBoxLayout(dlg)
    title = QLabel("安装成功！还差这几步")
    title.setObjectName("DialogTitle")
    lay.addWidget(title)
    body = QLabel(_CHECKLIST)
    body.setWordWrap(True)
    lay.addWidget(body)

    btn_row = QHBoxLayout()
    for label, args in _INTENTS:
        b = QPushButton(label)

        def _open(_checked=False, a=args, lab=label):
            ok, detail = _adb_run(adb_path, serial, list(a))
            if not ok:
                # 部分机型 MANAGE_OVERLAY 需带 package
                if "MANAGE_OVERLAY" in " ".join(a) and package_id:
                    alt = [
                        "shell",
                        "am",
                        "start",
                        "-a",
                        "android.settings.action.MANAGE_OVERLAY_PERMISSION",
                        "-d",
                        f"package:{package_id}",
                    ]
                    ok, detail = _adb_run(adb_path, serial, alt)
                if not ok:
                    QMessageBox.warning(
                        dlg,
                        lab,
                        f"无法自动打开设置页，请在手机上手动开启。\n{detail}",
                    )

        b.clicked.connect(_open)
        btn_row.addWidget(b)
    btn_row.addStretch()
    lay.addLayout(btn_row)

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
