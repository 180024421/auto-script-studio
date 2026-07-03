"""Auto Script Studio 全局主题与样式。"""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QWidget

# 浅色商务风：干净底 + 商务蓝主色
COLORS = {
    "bg": "#f4f6f9",
    "surface": "#ffffff",
    "surface2": "#f8fafc",
    "surface3": "#eef2f7",
    "border": "#dce3ed",
    "border_light": "#c8d3e0",
    "text": "#1a2332",
    "text_dim": "#4a5d75",
    "text_muted": "#7a8da3",
    "accent": "#0d9488",
    "accent_dim": "#0f766e",
    "accent_bg": "#ecfdf5",
    "primary": "#2563eb",
    "primary_dim": "#1d4ed8",
    "primary_bg": "#eff6ff",
    "danger": "#dc2626",
    "danger_bg": "#fef2f2",
    "success": "#16a34a",
    "warning": "#d97706",
}

APP_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}}

/* —— 顶栏（已并入主标签栏） —— */
#AppHeader {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ffffff, stop:1 {COLORS['surface2']});
    border-bottom: 1px solid {COLORS['border']};
    min-height: 44px;
}}
QTabWidget#MainTabs::pane {{
    border: none;
    background: {COLORS['bg']};
    top: 0px;
}}
QTabWidget#MainTabs > QTabBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ffffff, stop:1 {COLORS['surface2']});
    border-bottom: 1px solid {COLORS['border']};
    min-height: 40px;
}}
QTabWidget#MainTabs > QTabBar::tab {{
    background: transparent;
    color: {COLORS['text_muted']};
    padding: 6px 16px;
    margin: 0;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 600;
    font-size: 13px;
}}
QTabWidget#MainTabs > QTabBar::tab:selected {{
    color: {COLORS['primary']};
    border-bottom: 3px solid {COLORS['primary']};
    background: {COLORS['bg']};
}}
QTabWidget#MainTabs > QTabBar::tab:hover:!selected {{
    color: {COLORS['text']};
    background: {COLORS['surface2']};
}}
#TabBarCorner {{
    background: transparent;
}}

#ProjectChip {{
    background-color: {COLORS['primary_bg']};
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    padding: 4px 10px;
    color: {COLORS['primary_dim']};
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 11px;
}}

/* —— 标签页（通用） —— */
QTabWidget::pane {{
    border: none;
    background: {COLORS['bg']};
    top: -1px;
}}
QTabBar {{
    background: {COLORS['surface']};
    border-bottom: 1px solid {COLORS['border']};
}}
QTabBar::tab {{
    background: transparent;
    color: {COLORS['text_muted']};
    padding: 8px 18px;
    margin: 0;
    border: none;
    border-bottom: 3px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {COLORS['primary']};
    border-bottom: 3px solid {COLORS['primary']};
    background: {COLORS['bg']};
}}
QTabBar::tab:hover:!selected {{
    color: {COLORS['text']};
    background: {COLORS['surface2']};
}}

/* —— 卡片容器 —— */
QFrame#Card, QGroupBox {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}
QGroupBox {{
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
    font-weight: 600;
    color: {COLORS['text']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {COLORS['text_dim']};
}}

/* —— 按钮 —— */
QPushButton {{
    background-color: {COLORS['surface']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 12px;
    min-height: 28px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {COLORS['surface3']};
    border-color: {COLORS['border_light']};
}}
QPushButton:pressed {{
    background-color: {COLORS['border']};
}}
QPushButton:disabled {{
    color: {COLORS['text_muted']};
    background-color: {COLORS['surface2']};
}}
QPushButton[role="primary"] {{
    background-color: {COLORS['primary']};
    border-color: {COLORS['primary_dim']};
    color: #ffffff;
}}
QPushButton[role="primary"]:hover {{
    background-color: {COLORS['primary_dim']};
}}
QPushButton[role="accent"] {{
    background-color: {COLORS['accent_bg']};
    border-color: #99f6e4;
    color: {COLORS['accent_dim']};
}}
QPushButton[role="accent"]:hover {{
    background-color: #d1fae5;
    color: {COLORS['accent']};
}}
QPushButton[role="danger"] {{
    background-color: {COLORS['danger_bg']};
    border-color: #fecaca;
    color: {COLORS['danger']};
}}
QPushButton[role="danger"]:hover {{
    background-color: #fee2e2;
}}
QPushButton[role="ghost"] {{
    background: transparent;
    border-color: transparent;
    color: {COLORS['text_dim']};
}}
QPushButton[role="ghost"]:hover {{
    background: {COLORS['surface3']};
    color: {COLORS['text']};
    border-color: {COLORS['border']};
}}
QPushButton:checked {{
    background-color: {COLORS['primary_bg']};
    border-color: {COLORS['primary']};
    color: {COLORS['primary']};
}}

/* —— 输入 —— */
QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget {{
    background-color: {COLORS['surface']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {COLORS['primary']};
    selection-color: #ffffff;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border-color: {COLORS['primary']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['primary_bg']};
    selection-color: {COLORS['primary']};
}}
QComboBox QAbstractItemView::item {{
    padding-left: 8px;
}}
QPushButton::menu-indicator {{
    width: 14px;
    subcontrol-position: right center;
    subcontrol-origin: padding;
    right: 6px;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 6px;
}}
QListWidget::item:selected {{
    background: {COLORS['primary_bg']};
    color: {COLORS['primary']};
}}
QTreeWidget {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 4px;
}}
QTreeWidget::item {{
    padding: 4px 6px;
    border-radius: 4px;
}}
QTreeWidget::item:selected {{
    background: {COLORS['primary_bg']};
    color: {COLORS['primary']};
}}
QTextBrowser#CommandHelpView {{
    background-color: {COLORS['surface2']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px;
    font-size: 12px;
}}
QListWidget::item:hover:!selected {{
    background: {COLORS['surface3']};
}}

QTextEdit#LogConsole, QTextEdit#ScriptEditor, QTextEdit#ScriptRunLog {{
    font-family: Consolas, "Cascadia Mono", "Microsoft YaHei UI", monospace;
    font-size: 13px;
    line-height: 1.45;
    padding: 12px;
}}
QTextEdit#LogConsole, QTextEdit#ScriptRunLog {{
    background-color: {COLORS['surface2']};
    border: 1px solid {COLORS['border']};
    color: {COLORS['text_dim']};
}}
QTextEdit#ScriptEditor {{
    background-color: {COLORS['surface']};
}}

/* —— 截图区 —— */
#CanvasWrap {{
    background-color: {COLORS['surface2']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}
#ScreenshotCanvas {{
    background-color: transparent;
    border: none;
    border-radius: 0;
    color: {COLORS['text_muted']};
    min-height: 320px;
}}
#InfoBar {{
    background-color: transparent;
    border: none;
    padding: 2px 6px;
    color: {COLORS['text_muted']};
    font-family: Consolas, monospace;
    font-size: 11px;
}}
#HintLabel {{
    color: {COLORS['text_muted']};
    font-size: 12px;
    line-height: 1.5;
    padding: 4px 2px;
}}
#PhoneFrame {{
    background: transparent;
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
}}
#PhoneScreen {{
    background: #FFFFFF;
}}
QScrollArea#PhoneCanvas {{
    background: #FFFFFF;
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
}}
#PreviewPanel {{
    background-color: #FFFFFF;
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
}}
#PreviewPanel > QWidget > QWidget {{
    background: transparent;
}}
#PreviewViewport {{
    background: #FFFFFF;
}}
#OverlayPanelCard {{
    background-color: #FFFFFF;
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
}}
#PanelTitleBar {{
    background-color: {COLORS['surface3']};
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 14px;
    font-weight: 600;
    color: {COLORS['text']};
}}
#PanelLogArea {{
    background-color: {COLORS['surface2']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 10px;
    color: {COLORS['text_muted']};
    font-size: 11px;
}}
#PanelFieldLabel {{
    font-size: 12px;
    font-weight: 600;
    color: {COLORS['text_dim']};
}}
QScrollArea#PropertyScroll {{
    background: transparent;
    border: none;
}}
QScrollArea#PropertyScroll > QWidget > QGroupBox {{
    margin-top: 8px;
}}
QSplitter#PageSplitter::handle {{
    background: {COLORS['border']};
    width: 4px;
    margin: 4px 2px;
    border-radius: 2px;
}}
QSplitter#PageSplitter::handle:hover {{
    background: {COLORS['primary']};
}}

QCheckBox {{
    spacing: 8px;
    color: {COLORS['text_dim']};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {COLORS['border_light']};
    background: {COLORS['surface']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['primary']};
    border-color: {COLORS['primary']};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {COLORS['surface2']};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border_light']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['text_muted']};
}}

QLabel#SectionTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS['text']};
    padding: 4px 0;
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)


def set_button_role(btn: QWidget, role: str) -> None:
    btn.setProperty("role", role)
    btn.style().unpolish(btn)
    btn.style().polish(btn)
