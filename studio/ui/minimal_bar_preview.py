"""minimal 模式悬浮条 Studio 预览。"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from studio.services.panel_theme import panel_theme_colors


class MinimalBarPreviewWidget(QFrame):
    """模拟 APK minimal 悬浮猫条 + 球。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(6)
        self._title = QLabel("minimal 模式预览")
        self._title.setObjectName("HintLabel")
        lay.addWidget(self._title)
        row = QHBoxLayout()
        self._ball = QFrame()
        self._ball.setFixedSize(40, 40)
        row.addWidget(self._ball)
        self._bar = QFrame()
        self._bar.setMinimumHeight(36)
        inner = QHBoxLayout(self._bar)
        inner.setContentsMargins(12, 4, 12, 4)
        self._bar_label = QLabel("▶  启动脚本")
        inner.addWidget(self._bar_label)
        inner.addStretch(1)
        row.addWidget(self._bar, 1)
        lay.addLayout(row)
        self._hint = QLabel("实机：悬浮球 + 极简条，不含内嵌表单")
        self._hint.setObjectName("HintLabel")
        self._hint.setWordWrap(True)
        lay.addWidget(self._hint)
        self.apply_panel({})

    def set_title(self, text: str) -> None:
        self._title.setText(text or "minimal 模式预览")

    def apply_panel(self, panel: dict[str, Any]) -> None:
        title = str(panel.get("title", "脚本助手"))
        ball_dp = int(panel.get("ball_size_dp", 48))
        opacity = float(panel.get("opacity", 0.96))
        show_log = bool(panel.get("show_log", True))
        theme = panel_theme_colors(str(panel.get("theme", "light")))
        ball_px = max(28, min(72, ball_dp))
        self._ball.setFixedSize(ball_px, ball_px)
        radius = ball_px // 2
        alpha = int(max(50, min(100, opacity * 100)))
        self._ball.setStyleSheet(
            f"QFrame {{ background:{theme.accent}; border-radius:{radius}px; "
            f"border:2px solid {theme.title_bg}; opacity:{alpha / 100.0}; }}"
        )
        self._bar.setStyleSheet(
            f"QFrame {{ background:{theme.chrome_bg}; border:1px solid {theme.chrome_border}; "
            f"border-radius:18px; opacity:{alpha / 100.0}; }}"
        )
        self._bar_label.setStyleSheet(
            f"color:{theme.label_muted};font-size:12px;background:transparent;"
        )
        self._bar_label.setText(f"▶  {title}")
        log_hint = " · 含日志条" if show_log else ""
        self._hint.setText(
            f"实机：{ball_dp}dp 悬浮球 + 极简条{log_hint}，不含内嵌表单"
        )
        self.set_title(f"minimal · {title}")
