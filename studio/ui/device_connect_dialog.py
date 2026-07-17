"""设备连接助理：刷新列表 / adb connect / 常见状态说明。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from studio.services.adb_service import AdbService


class DeviceConnectDialog(QDialog):
    def __init__(self, parent=None, *, adb: AdbService) -> None:
        super().__init__(parent)
        self.adb = adb
        self.setWindowTitle("设备连接助理")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "连接模拟器或真机后，抓抓 / 脚本 / 打包会共用同一台设备。\n"
                "若显示 unauthorized：手机上点「允许 USB 调试」。"
            )
        )
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        lay.addWidget(self.log)

        row = QHBoxLayout()
        self.host_edit = QLineEdit("127.0.0.1:5555")
        self.host_edit.setPlaceholderText("网络调试地址，如 127.0.0.1:5555")
        connect_btn = QPushButton("adb connect")
        connect_btn.clicked.connect(self._connect)
        refresh_btn = QPushButton("刷新设备")
        refresh_btn.clicked.connect(self._refresh)
        row.addWidget(self.host_edit, 1)
        row.addWidget(connect_btn)
        row.addWidget(refresh_btn)
        lay.addLayout(row)

        tips = QLabel(
            "雷电常见端口 5555/5557；MuMu 多为 16384/16416。\n"
            "也可先在终端运行: adb devices"
        )
        tips.setWordWrap(True)
        lay.addWidget(tips)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        lay.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        try:
            # 也列出 offline / unauthorized
            proc = self.adb._run(["devices", "-l"], check=False, text=True, timeout=15)
            raw = (proc.stdout or "").strip() or "(无输出)"
            self.log.setPlainText(raw)
            ok = self.adb.list_devices(auto_connect=False)
            if not ok:
                self.log.append("\n未发现可用 device。请检查 USB/模拟器调试开关。")
        except Exception as exc:
            self.log.setPlainText(f"刷新失败: {exc}")

    def _connect(self) -> None:
        host = self.host_edit.text().strip()
        if not host:
            QMessageBox.warning(self, "提示", "请填写地址")
            return
        try:
            proc = self.adb._run(["connect", host], check=False, text=True, timeout=20)
            out = (proc.stdout or proc.stderr or "").strip()
            self.log.append(f"\n$ adb connect {host}\n{out}")
            self._refresh()
        except Exception as exc:
            QMessageBox.warning(self, "连接失败", str(exc))
