"""minimal 模式悬浮条 Studio 预览。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout


class MinimalBarPreviewWidget(QFrame):
    """模拟 APK minimal 悬浮猫条 + 球。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        title = QLabel("minimal 模式预览")
        title.setObjectName("HintLabel")
        lay.addWidget(title)
        row = QHBoxLayout()
        ball = QFrame()
        ball.setFixedSize(40, 40)
        ball.setStyleSheet(
            "QFrame { background:#2563EB; border-radius:20px; border:2px solid #1D4ED8; }"
        )
        row.addWidget(ball)
        bar = QFrame()
        bar.setMinimumHeight(36)
        bar.setStyleSheet(
            "QFrame { background:#F1F5F9; border:1px solid #CBD5E1; border-radius:18px; }"
        )
        inner = QHBoxLayout(bar)
        inner.setContentsMargins(12, 4, 12, 4)
        lbl = QLabel("▶  启动脚本")
        lbl.setStyleSheet("color:#334155;font-size:12px;background:transparent;")
        inner.addWidget(lbl)
        inner.addStretch(1)
        row.addWidget(bar, 1)
        lay.addLayout(row)
        hint = QLabel("实机：悬浮球 + 极简条，不含内嵌表单")
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        lay.addWidget(hint)

    def set_title(self, text: str) -> None:
        pass
