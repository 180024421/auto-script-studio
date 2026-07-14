"""傻瓜式布局向导：一键生成登录页 / 运行设置 / 完整双页。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from studio.services.layout_wizard_templates import WIZARD_CHOICES
from studio.ui.app_theme import set_button_role


class LayoutWizardDialog(QDialog):
    def __init__(self, parent=None, *, default_title: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("从模板创建界面")
        self.setMinimumWidth(480)
        self._selected_key = "full"

        root = QVBoxLayout(self)
        root.setSpacing(12)

        tip = QLabel("选一个最接近你需求的模板，创建后只需改文字和选项。")
        tip.setObjectName("HintLabel")
        tip.setWordWrap(True)
        root.addWidget(tip)

        self._choice_group = QButtonGroup(self)
        for i, item in enumerate(WIZARD_CHOICES):
            box = QGroupBox()
            box_lay = QVBoxLayout(box)
            radio = QRadioButton(item["title"])
            radio.setChecked(item["key"] == "full")
            desc = QLabel(item["desc"])
            desc.setObjectName("HintLabel")
            desc.setWordWrap(True)
            box_lay.addWidget(radio)
            box_lay.addWidget(desc)
            self._choice_group.addButton(radio, i)
            root.addWidget(box)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("面板标题"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("安装后显示的名称，如：我的助手")
        self.title_edit.setText(default_title)
        title_row.addWidget(self.title_edit, 1)
        root.addLayout(title_row)

        mode_box = QGroupBox("创建方式")
        mode_lay = QVBoxLayout(mode_box)
        self.replace_rb = QRadioButton("替换当前全部界面（推荐新建工程时用）")
        self.append_rb = QRadioButton("追加为新页签（保留已有界面）")
        self.replace_rb.setChecked(True)
        mode_lay.addWidget(self.replace_rb)
        mode_lay.addWidget(self.append_rb)
        root.addWidget(mode_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("创建")
            set_button_role(ok_btn, "primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def selected_key(self) -> str:
        idx = self._choice_group.checkedId()
        if idx < 0 or idx >= len(WIZARD_CHOICES):
            return "full"
        return WIZARD_CHOICES[idx]["key"]

    def panel_title(self) -> str:
        return self.title_edit.text().strip()

    def replace_all(self) -> bool:
        return self.replace_rb.isChecked()
