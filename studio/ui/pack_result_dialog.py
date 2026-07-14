"""打包 / 安装完成结果页。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from studio.ui.app_theme import set_button_role


class PackResultDialog(QDialog):
    def __init__(self, parent, summary: dict, *, can_publish: bool) -> None:
        super().__init__(parent)
        self.summary = summary
        self.setWindowTitle("打包结果")
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        ok = summary.get("layout_ok", True) and bool(summary.get("apk_path"))
        headline = "打包安装成功" if summary.get("installed") else ("打包成功" if ok else "打包完成（请检查）")
        title = QLabel(headline)
        title.setStyleSheet("font-size:16px;font-weight:600;")
        root.addWidget(title)

        form = QFormLayout()
        form.addRow("应用", QLabel(f"{summary.get('name', '')} ({summary.get('package_id', '')})"))
        form.addRow("版本", QLabel(f"v{summary.get('version_code')} ({summary.get('version_name')})"))
        if summary.get("apk_path"):
            form.addRow(
                "APK",
                QLabel(f"{summary.get('apk_path')} · {summary.get('apk_size_kb', 0)} KB"),
            )
        if summary.get("installed"):
            dev = summary.get("device_serial") or "当前设备"
            launch = "已启动" if summary.get("launched") else "未启动"
            form.addRow("安装", QLabel(f"{dev} · {launch}"))
        panel_title = summary.get("panel_title") or "—"
        layout_lbl = QLabel(summary.get("layout_message") or panel_title)
        layout_lbl.setWordWrap(True)
        if summary.get("layout_ok"):
            layout_lbl.setStyleSheet("color:#15803D;")
        else:
            layout_lbl.setStyleSheet("color:#B45309;")
        form.addRow("脚本面板标题", QLabel(panel_title))
        form.addRow("Layout 校验", layout_lbl)
        perf_lbl = QLabel(
            f"点击 {summary.get('input_mode')} · 截屏 {summary.get('screenshot_mode')} · "
            f"YOLO {summary.get('yolo_imgsz')}px"
        )
        form.addRow("性能配置", perf_lbl)
        root.addLayout(form)

        self.publish_cb = QCheckBox("立即发布脚本热更新到 jiaoben")
        self.publish_cb.setVisible(can_publish)
        if can_publish:
            pid = int(summary.get("jiaoben_project_id") or 0)
            if pid > 0:
                self.publish_cb.setChecked(True)
                self.publish_cb.setToolTip(f"发卡项目 ID: {pid}")
            else:
                self.publish_cb.setChecked(False)
                self.publish_cb.setEnabled(False)
                self.publish_cb.setToolTip("请先在高级打包选项中选择 jiaoben 发卡项目")
        root.addWidget(self.publish_cb)

        self.grab_cb = QCheckBox("打开抓抓页对照实机")
        self.grab_cb.setChecked(bool(summary.get("installed")))
        self.grab_cb.setVisible(bool(summary.get("installed")))
        root.addWidget(self.grab_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn:
            close_btn.setText("完成")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def want_publish(self) -> bool:
        return self.publish_cb.isVisible() and self.publish_cb.isChecked()

    def want_open_grab(self) -> bool:
        return self.grab_cb.isVisible() and self.grab_cb.isChecked()
