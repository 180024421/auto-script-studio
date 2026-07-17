"""打包前环境向导：JDK / SDK / ADB 缺失时给出可操作说明。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from studio.services.env_preflight import PreflightReport, format_report_text, run_preflight


def ensure_pack_environment(parent, *, adb_path: str = "adb") -> bool:
    """
    检查打包所需环境。全部 OK 返回 True；
    有阻断项时弹窗，用户可选择「仍要继续」或取消。
    """
    report = run_preflight(adb_path=adb_path)
    # Gradle 可选；阻断项：Java、Android SDK（ADB 对「仅打包」非必须，但对安装有用）
    blocking = [i for i in report.items if not i.ok and i.name in ("Java", "Android SDK")]
    if not blocking:
        return True

    dlg = QDialog(parent)
    dlg.setWindowTitle("打包环境检查")
    dlg.setMinimumWidth(520)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("打包 APK 需要 JDK 17+ 与 Android SDK。当前检测结果："))
    box = QTextEdit()
    box.setReadOnly(True)
    box.setPlainText(format_report_text(report))
    box.setMinimumHeight(180)
    lay.addWidget(box)
    tips = QLabel(
        "建议：\n"
        "• 安装 JDK 17，设置 JAVA_HOME\n"
        "• 安装 Android Studio 或 command-line tools，设置 ANDROID_HOME，并安装 build-tools\n"
        "• 仅 PC 联调可不打包，见 docs/getting-started.md「路径 A」\n"
        "• 详细步骤见 docs/pack-guide.md"
    )
    tips.setWordWrap(True)
    lay.addWidget(tips)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ignore
    )
    buttons.button(QDialogButtonBox.StandardButton.Ignore).setText("仍要继续打包")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
    buttons.rejected.connect(dlg.reject)
    buttons.button(QDialogButtonBox.StandardButton.Ignore).clicked.connect(dlg.accept)
    lay.addWidget(buttons)
    return dlg.exec() == QDialog.DialogCode.Accepted


def show_preflight_summary(parent, *, adb_path: str = "adb") -> PreflightReport:
    report = run_preflight(adb_path=adb_path)
    from PySide6.QtWidgets import QMessageBox

    QMessageBox.information(parent, "环境预检", format_report_text(report))
    return report
