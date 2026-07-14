"""720×1280 手机画布 — 全局标签页 + 可滚动界面 + 自由拖动缩放。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QRect, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
  QApplication,
  QFrame,
  QGraphicsDropShadowEffect,
  QHBoxLayout,
  QLabel,
  QMenu,
  QPushButton,
  QScrollArea,
  QSizePolicy,
  QVBoxLayout,
  QWidget,
)

from studio.ui.panel_widget_factory import (
  FORM_PREVIEW_TYPES,
  INTERACTIVE_TYPES,
  build_design_preview,
  build_interactive_widget,
)

from studio.runtime.panel_state import PanelState
from studio.services.screen_layout import (
  CHROME_PATH_TAG,
  active_screen_index,
  chrome_widgets,
  content_height,
  is_host_display,
  migrate_layout,
  path_for_chrome,
  path_for_screen,
  screens,
  set_widget_rect,
)
from studio.services.free_layout import DESIGN_W, panel_design_size
from studio.services.layout_clone import clone_layout, clone_widget
from studio.services.panel_geometry import (
  compute_device_screen_px,
  compute_host_panel_overlay_rect,
)
from studio.services.panel_theme import panel_theme_colors
from studio.services.smart_snap import other_rects_excluding, smart_snap_rect
from studio.services.snap_design import SNAP_GRID, snap_design as _snap_design
from studio.services.widget_interior_scale import effective_content_scale

TITLE_DP = 48
TAB_BAR_DP = 44
CHROME_DP = 64
APK_SHELL_PAD_DP = 20
APK_SHELL_TOOLBAR_DP = 44
APK_SHELL_BTN_DP = 48
APK_SHELL_LOG_DP = 200
APK_SHELL_LOG_LABEL_DP = 28


def _apk_shell_extra_dp() -> int:
  return (
    APK_SHELL_PAD_DP * 2
    + APK_SHELL_TOOLBAR_DP
    + APK_SHELL_BTN_DP * 2
    + 16
    + APK_SHELL_LOG_LABEL_DP
    + APK_SHELL_LOG_DP
  )
DRAG_THRESHOLD = 5


def _chrome_dp(layout: dict[str, Any]) -> int:
  return 0 if is_host_display(layout.get("panel")) else CHROME_DP

CHROME_ICONS: dict[str, str] = {
  "start_script": "▶",
  "stop_script": "■",
  "collapse": "▼",
  "tap": "⌖",
  "lua": "{}",
}

DEFAULT_PHONE_SCREEN_PX = 360
AUTO_FIT_DEVICE = -1
DEVTOOLS_CANVAS_BG = "#E8EAED"
STATUS_BAR_DP = 24
HOME_INDICATOR_DP = 34
HOST_APP_BAR_DP = 44


def _status_bar_height(scale: float) -> int:
  return max(18, int(STATUS_BAR_DP * scale))


def _home_indicator_height(scale: float) -> int:
  return max(14, int(HOME_INDICATOR_DP * scale))


def _host_app_bar_height(scale: float) -> int:
  return max(28, int(HOST_APP_BAR_DP * scale))


def _build_status_bar_overlay(scale: float, *, parent: QWidget) -> QWidget:
  """模拟系统状态栏（类似 Chrome 设备仿真顶部）。"""
  h = _status_bar_height(scale)
  bar = QWidget(parent)
  bar.setObjectName("DeviceStatusBar")
  bar.setFixedHeight(h)
  fs = max(8, int(10 * scale))
  bar.setStyleSheet(
    f"QWidget#DeviceStatusBar {{ background:#1A1A1A; color:#FFFFFF; "
    f"border-top-left-radius:{max(0, int(4 * scale))}px; "
    f"border-top-right-radius:{max(0, int(4 * scale))}px; }}"
  )
  lay = QHBoxLayout(bar)
  lay.setContentsMargins(max(8, int(12 * scale)), 0, max(8, int(12 * scale)), 0)
  time_lbl = QLabel("9:41")
  time_lbl.setStyleSheet(f"color:#FFFFFF;font-size:{fs}px;font-weight:600;background:transparent;")
  lay.addWidget(time_lbl)
  lay.addStretch(1)
  icons = QLabel("▮▮▮  WiFi  🔋")
  icons.setStyleSheet(f"color:#FFFFFF;font-size:{max(7, fs - 1)}px;background:transparent;")
  lay.addWidget(icons)
  return bar


def _build_home_indicator_overlay(scale: float, *, parent: QWidget, screen_w: int) -> QWidget:
  """底部 Home 指示条（iPhone 风格药丸）。"""
  h = _home_indicator_height(scale)
  host = QWidget(parent)
  host.setObjectName("DeviceHomeArea")
  host.setFixedHeight(h)
  host.setStyleSheet("QWidget#DeviceHomeArea { background: transparent; }")
  lay = QVBoxLayout(host)
  lay.setContentsMargins(0, max(4, int(8 * scale)), 0, max(4, int(6 * scale)))
  lay.addStretch(1)
  pill_w = max(48, int(screen_w * 0.36))
  pill_h = max(3, int(4 * scale))
  pill = QFrame(host)
  pill.setFixedSize(pill_w, pill_h)
  pill.setStyleSheet(
    f"QFrame {{ background:#1A1A1A; border-radius:{pill_h // 2}px; opacity:0.35; }}"
  )
  pill_row = QHBoxLayout()
  pill_row.addStretch(1)
  pill_row.addWidget(pill)
  pill_row.addStretch(1)
  lay.addLayout(pill_row)
  return host


def _build_host_app_bar(scale: float, *, parent: QWidget, title: str) -> QWidget:
  """host 模式：模拟 MainActivity 顶栏（表单嵌入宿主页）。"""
  h = _host_app_bar_height(scale)
  bar = QWidget(parent)
  bar.setObjectName("HostAppBar")
  bar.setFixedHeight(h)
  fs = max(9, int(12 * scale))
  bar.setStyleSheet(
    "QWidget#HostAppBar { background:#F8FAFC; border-bottom:1px solid #E2E8F0; }"
  )
  lay = QHBoxLayout(bar)
  lay.setContentsMargins(max(8, int(12 * scale)), 0, max(8, int(12 * scale)), 0)
  app_title = QLabel(title or "Auto Script")
  app_title.setStyleSheet(f"color:#0F172A;font-size:{fs}px;font-weight:600;background:transparent;")
  lay.addWidget(app_title)
  lay.addStretch(1)
  gear = QLabel("⚙")
  gear.setStyleSheet(f"color:#64748B;font-size:{fs + 2}px;background:transparent;")
  lay.addWidget(gear)
  return bar


def _build_floating_ball(scale: float, *, parent: QWidget, ball_dp: int, accent: str) -> QWidget:
  """host 模式悬浮球（启停脚本）。"""
  size = max(28, int(ball_dp * scale))
  ball = QFrame(parent)
  ball.setObjectName("FloatingBall")
  ball.setFixedSize(size, size)
  radius = size // 2
  ball.setStyleSheet(
    f"QFrame#FloatingBall {{ background:{accent}; border-radius:{radius}px; "
    f"border:2px solid #FFFFFF; color:#FFFFFF; font-size:{max(10, int(14 * scale))}px; "
    f"font-weight:700; }}"
  )
  ball_lay = QVBoxLayout(ball)
  ball_lay.setContentsMargins(0, 0, 0, 0)
  icon = QLabel("▶")
  icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
  icon.setStyleSheet("color:#FFFFFF;background:transparent;font-weight:700;")
  ball_lay.addWidget(icon)
  ball.setToolTip("悬浮球：实机用于启停脚本")
  return ball


def _build_device_backdrop(parent: QWidget, w: int, h: int, pixmap: QPixmap | None) -> QLabel:
  """设备屏壁纸：实机截图或渐变占位。"""
  lbl = QLabel(parent)
  lbl.setObjectName("DeviceBackdrop")
  lbl.setGeometry(0, 0, w, h)
  lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
  if pixmap is not None and not pixmap.isNull():
    lbl.setPixmap(
      pixmap.scaled(
        w,
        h,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
      )
    )
    lbl.setStyleSheet("QLabel#DeviceBackdrop { background:#0F172A; }")
  else:
    lbl.setStyleSheet(
      "QLabel#DeviceBackdrop {"
      "background: qlineargradient("
      "x1:0,y1:0,x2:1,y2:1,"
      "stop:0 #E2E8F0, stop:0.45 #CBD5E1, stop:1 #94A3B8"
      ");"
      "color:#64748B;font-size:11px;"
      "}"
    )
    lbl.setText("宿主应用")
  return lbl


def compute_preview_scale(
  *,
  design_w: int,
  design_h: int,
  viewport_w: int,
  viewport_h: int,
  target_screen_px: int | None = None,
  fit_viewport: bool = False,
  min_scale: float = 0.35,
  hint_reserve: int = 0,
) -> float:
  """计算手机画布预览缩放（纯函数，便于单测）。"""
  gutter = 20
  vw = max(160, viewport_w - 48 - gutter)
  scale_w = vw / max(1, design_w)
  if target_screen_px is not None:
    target_scale = target_screen_px / max(1, design_w)
    if fit_viewport:
      vh = max(160, viewport_h - hint_reserve - 20)
      scale_h = vh / max(1, design_h)
      return max(min_scale, min(1.0, target_scale, scale_w, scale_h))
    return max(min_scale, min(1.0, target_scale, scale_w))
  if not fit_viewport:
    return max(min_scale, min(1.0, scale_w))
  vh = max(160, viewport_h - hint_reserve - 20)
  scale_h = vh / max(1, design_h)
  return max(min_scale, min(1.0, scale_w, scale_h))


def _bezel_px(scale: float, *, phone_style: bool) -> int:
  if not phone_style:
    return 2
  return max(6, int(8 * max(0.35, scale)))


def _phone_frame_radius(scale: float, *, phone_style: bool) -> int:
  if not phone_style:
    return 8
  return max(18, int(24 * max(0.35, scale)))


def _screen_tab_stylesheet(scale: float, *, checked: bool) -> str:
  """脚本页窄栏缩放时覆盖全局 QPushButton min-height，避免标签文字被裁切。"""
  fs = max(8, int(11 * scale))
  pad_v = max(2, int(4 * scale))
  pad_h = max(4, int(8 * scale))
  min_h = max(18, int(26 * scale))
  if checked:
    return (
      f"QPushButton#PanelScreenTab {{ min-height: {min_h}px; max-height: {min_h}px; "
      f"font-size: {fs}px; font-weight: 600; padding: {pad_v}px {pad_h}px; "
      f"background: #EFF6FF; color: #2563EB; border: 1px solid #2563EB; "
      f"border-radius: {max(4, int(6 * scale))}px; }}"
    )
  return (
    f"QPushButton#PanelScreenTab {{ min-height: {min_h}px; max-height: {min_h}px; "
    f"font-size: {fs}px; padding: {pad_v}px {pad_h}px; "
    f"background: #FFFFFF; color: #334155; border: 1px solid #CBD5E1; "
    f"border-radius: {max(4, int(6 * scale))}px; }}"
  )


def _screen_tab_bar_height(scale: float) -> int:
  return max(int(TAB_BAR_DP * scale), int(26 * scale) + 8)


def _build_screen_tab_bar(
  sc_list: list[dict[str, Any]],
  active: int,
  scale: float,
  on_tab_clicked,
) -> tuple[QScrollArea, list[QPushButton]]:
  """标签过多时可横向滚动，避免文字被裁切。"""
  tab_h = _screen_tab_bar_height(scale)
  tab_scroll = QScrollArea()
  tab_scroll.setFixedHeight(tab_h)
  tab_scroll.setWidgetResizable(True)
  tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
  tab_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
  tab_scroll.setFrameShape(QFrame.Shape.NoFrame)
  tab_scroll.setStyleSheet(
    "QScrollArea { background:#F1F5F9; border:none; border-bottom:1px solid #CBD5E1; }"
  )

  tab_row = QWidget()
  tab_lay = QHBoxLayout(tab_row)
  tab_lay.setContentsMargins(4, 4, 4, 4)
  tab_lay.setSpacing(4)
  tab_buttons: list[QPushButton] = []
  for i, sc in enumerate(sc_list):
    tb = QPushButton(sc.get("title", f"界面{i + 1}"))
    tb.setObjectName("PanelScreenTab")
    tb.setCheckable(True)
    tb.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    tb.blockSignals(True)
    tb.setChecked(i == active)
    tb.blockSignals(False)
    tb.setStyleSheet(_screen_tab_stylesheet(scale, checked=i == active))
    tb.clicked.connect(lambda _c=False, idx=i: on_tab_clicked(idx))
    tab_lay.addWidget(tb)
    tab_buttons.append(tb)
  tab_scroll.setWidget(tab_row)
  return tab_scroll, tab_buttons


def _layout_rect(spec: dict[str, Any], scale: float) -> tuple[int, int, int, int]:
    return (
        int(spec.get("layout_x", 24) * scale),
        int(spec.get("layout_y", 40) * scale),
        int(spec.get("layout_w", 200) * scale),
        int(spec.get("layout_h", 48) * scale),
    )


def _widget_content_signature(spec: dict[str, Any]) -> tuple:
    skip = {"layout_x", "layout_y", "layout_w", "layout_h"}
    return tuple(sorted((k, repr(v)) for k, v in spec.items() if k not in skip))


class FreeDesignItem(QFrame):
  """界面内可拖动、右下角可缩放的控件。"""

  rect_changed = Signal(tuple, int, int, int, int)
  clicked = Signal(tuple)

  GRIP = 14
  DRAG_STRIP = 18
  FORM_DRAG_GUTTER = 10

  def __init__(
    self,
    path: tuple[int, ...],
    spec: dict[str, Any],
    scale: float,
    parent: QWidget | None = None,
    *,
    interactive: bool = False,
    editable: bool = True,
    selectable: bool = False,
    on_values_changed: Any = None,
    icon_only: bool = False,
    theme: str = "light",
    snap_move: Any = None,
  ) -> None:
    super().__init__(parent)
    self._path = path
    self._scale = scale
    self._selected = False
    self._mode = ""
    self._press_global = QPoint()
    self._start_geom = QRect()
    self._interactive = interactive
    self._editable = editable
    self._selectable = selectable
    self._on_values_changed = on_values_changed
    self._theme = theme or "light"
    self._snap_move = snap_move
    self._spec = clone_widget(spec)
    wtype = spec.get("type", "")
    self._form_like = wtype in FORM_PREVIEW_TYPES
    self._label: QLabel | None = None
    self._drag_lightweight = False
    self._flash = False

    self.setObjectName("FreeDesignItem")
    self.setMouseTracking(True)
    title = spec.get("label") or spec.get("text") or spec.get("id", "?")
    icon = CHROME_ICONS.get(wtype, "")
    if icon_only and icon:
      display = icon
      title_line = f"{title} ({wtype})"
    elif self._form_like:
      display = ""
      title_line = str(title)
    else:
      display = f"{icon} {title}" if icon else f"{title}\n({wtype})"
      title_line = display
    self._drag_strip = QLabel(display, self)
    self._drag_strip.setObjectName("FreeDesignDragStrip")
    self._drag_strip.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._drag_strip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    if self._form_like:
      self._drag_strip.hide()
    self._content_host = QWidget(self)
    self._last_content_scale = 0.0
    self._mount_preview(self._spec)
    self._relayout_content()
    self._update_style()

  def _content_pixel_height(self) -> int:
    strip_h = self.DRAG_STRIP if self._interactive and not self._form_like else 0
    return max(20, self.height() - strip_h)

  def _effective_content_scale(self) -> float:
    layout_h = int(self._spec.get("layout_h", 48))
    return effective_content_scale(self._scale, layout_h, self._content_pixel_height())

  def _container_height(self) -> int:
    return self._content_pixel_height()

  def _mount_preview(self, spec: dict[str, Any]) -> None:
    wtype = spec.get("type", "")
    eff_scale = self._effective_content_scale()
    self._last_content_scale = eff_scale
    container_h = self._container_height()
    preview = None
    if self._interactive and wtype in INTERACTIVE_TYPES:
      preview = build_interactive_widget(
        spec,
        self._on_values_changed,
        scale=eff_scale,
        container_h=container_h,
        theme=self._theme,
      )
    elif wtype == "divider" or wtype in FORM_PREVIEW_TYPES:
      preview = build_design_preview(
        spec, scale=eff_scale, container_h=container_h, theme=self._theme
      )
    if preview is not None:
      lay = self._content_host.layout()
      if lay is None:
        lay = QVBoxLayout(self._content_host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
      else:
        while lay.count():
          item = lay.takeAt(0)
          child = item.widget()
          if child is not None:
            child.setParent(None)
            child.deleteLater()
      preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
      lay.addWidget(preview, 1)
      if self._label is not None:
        self._label.deleteLater()
        self._label = None
      return

    title = spec.get("label") or spec.get("text") or spec.get("id", "?")
    icon = CHROME_ICONS.get(wtype, "")
    icon_only = bool(icon and wtype in CHROME_ICONS)
    if icon_only and icon:
      display = icon
      title_line = f"{title} ({wtype})"
    elif self._form_like:
      display = ""
      title_line = str(title)
    else:
      display = f"{icon} {title}" if icon else f"{title}\n({wtype})"
      title_line = display
    lay = self._content_host.layout()
    if lay is not None:
      while lay.count():
        item = lay.takeAt(0)
        child = item.widget()
        if child is not None:
          child.setParent(None)
          child.deleteLater()
    if self._label is not None:
      self._label.deleteLater()
    self._label = QLabel(title_line if icon_only and icon else display, self._content_host)
    self._label.setObjectName("FreeDesignTitle")
    self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._label.setWordWrap(not (icon_only and icon))
    if icon_only and icon:
      self._label.setStyleSheet("font-size: 22px; font-weight: 600;")
    self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

  def reload_content(self, spec: dict[str, Any]) -> None:
    self._spec = clone_widget(spec)
    wtype = self._spec.get("type", "")
    self._form_like = wtype in FORM_PREVIEW_TYPES
    if self._form_like:
      self._drag_strip.hide()
    self._mount_preview(self._spec)
    self._relayout_content()
    self._update_style()

  def path(self) -> tuple[int, ...]:
    return self._path

  def set_selected(self, on: bool) -> None:
    self._selected = on
    self._update_style()

  def set_flash(self, on: bool) -> None:
    self._flash = bool(on)
    self._update_style()

  def _set_drag_lightweight(self, on: bool) -> None:
    if self._drag_lightweight == on:
      return
    self._drag_lightweight = on
    if on:
      self._content_host.hide()
      self._drag_strip.setGeometry(0, 0, self.width(), self.height())
      self._drag_strip.show()
      self._drag_strip.raise_()
    else:
      self._content_host.show()
      self._relayout_content()

  def _relayout_content(self) -> None:
    if self._drag_lightweight:
      self._drag_strip.setGeometry(0, 0, self.width(), self.height())
      return
    strip_h = 0
    if self._interactive and not self._form_like:
      strip_h = self.DRAG_STRIP
      self._drag_strip.setGeometry(0, 0, self.width(), strip_h)
      self._drag_strip.show()
    elif not self._form_like:
      self._drag_strip.setGeometry(0, 0, self.width(), 0)
    self._content_host.setGeometry(0, strip_h, self.width(), max(20, self.height() - strip_h))
    self._content_host.setMaximumHeight(max(20, self.height() - strip_h))
    if self._label is not None:
      self._label.setGeometry(4, 4, max(40, self._content_host.width() - 8), max(24, self._content_host.height() - 8))

  def resizeEvent(self, event) -> None:  # noqa: N802
    super().resizeEvent(event)
    self._relayout_content()
    if self._form_like or self._interactive:
      new_scale = self._effective_content_scale()
      if abs(new_scale - self._last_content_scale) > 0.04:
        self._mount_preview(self._spec)

  def _update_style(self) -> None:
    if self._flash:
      border = "#F59E0B"
      border_w = 2
    elif self._selected:
      border = "#2563EB"
      border_w = 2
    else:
      border = "transparent"
      border_w = 1
    bg = "rgba(245,158,11,0.10)" if self._flash else "transparent"
    radius = 6 if self._form_like else 8
    strip_bg = "rgba(37,99,235,0.12)" if self._interactive and not self._form_like else "transparent"
    self.setStyleSheet(
      f"QFrame#FreeDesignItem {{ background: {bg}; border: {border_w}px solid {border}; border-radius: {radius}px; }}"
      f"QLabel#FreeDesignDragStrip {{ background: {strip_bg}; color: #1E293B; font-size: 10px; }}"
      "QLabel#FreeDesignTitle { color: #1E293B; font-size: 11px; background: transparent; }"
    )

  def _canvas_width_px(self) -> int:
    parent = self.parentWidget()
    if parent is not None and parent.width() > 0:
      return parent.width()
    return max(48, int(DESIGN_W * self._scale) if hasattr(self, "_scale") else DESIGN_W)

  def _clamp_geometry(self, g: QRect) -> QRect:
    from studio.services.free_layout import min_rect_for_type

    pw = self._canvas_width_px()
    wtype = str(self._spec.get("type", ""))
    min_dw, min_dh = min_rect_for_type(wtype)
    min_sw = max(int(min_dw * self._scale), SNAP_GRID * 6)
    min_sh = max(int(min_dh * self._scale), SNAP_GRID * 4)
    w = max(min_sw, g.width())
    h = max(min_sh, g.height())
    x = max(0, min(pw - w, g.x()))
    y = max(0, g.y())
    if self._path and self._path[0] == CHROME_PATH_TAG:
      max_ph = int(CHROME_DP * self._scale)
      h = min(h, max_ph)
      y = min(y, max(0, max_ph - h))
    w = min(w, pw - x)
    return QRect(x, y, w, h)

  def _in_grip(self, pos: QPoint) -> bool:
    if self._interactive and self._form_like:
      return False
    return pos.x() >= self.width() - self.GRIP and pos.y() >= self.height() - self.GRIP

  def _in_drag_strip(self, pos: QPoint) -> bool:
    if not self._interactive:
      return True
    if self._form_like:
      return pos.x() <= self.FORM_DRAG_GUTTER or self._in_grip(pos)
    return pos.y() <= self.DRAG_STRIP

  def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if not self._editable:
      if (
        self._selectable
        and event.button() == Qt.MouseButton.LeftButton
      ):
        self.clicked.emit(self._path)
        event.accept()
        return
      return super().mousePressEvent(event)
    if event.button() != Qt.MouseButton.LeftButton:
      return super().mousePressEvent(event)
    self.clicked.emit(self._path)
    local = event.position().toPoint()
    if self._interactive and not self._in_drag_strip(local) and not self._in_grip(local):
      return super().mousePressEvent(event)
    self._press_global = event.globalPosition().toPoint()
    self._start_geom = QRect(self.geometry())
    self._mode = ""
    event.accept()

  def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if not self._editable:
      return super().mouseMoveEvent(event)
    pos = event.position().toPoint()
    if not (event.buttons() & Qt.MouseButton.LeftButton):
      self.setCursor(
        QCursor(Qt.CursorShape.SizeFDiagCursor)
        if self._in_grip(pos)
        else QCursor(Qt.CursorShape.SizeAllCursor)
      )
      return super().mouseMoveEvent(event)
    if not self._mode:
      delta = event.globalPosition().toPoint() - self._press_global
      if delta.manhattanLength() < DRAG_THRESHOLD:
        return super().mouseMoveEvent(event)
      local = event.position().toPoint()
      self._mode = "resize" if self._in_grip(local) else "move"
      self._set_drag_lightweight(True)
      self.grabMouse()
    if not self._mode:
      return super().mouseMoveEvent(event)
    delta = event.globalPosition().toPoint() - self._press_global
    g = QRect(self._start_geom)
    if self._mode == "move":
      g.translate(delta)
      g = self._clamp_geometry(g)
      snap_fn = getattr(self, "_snap_move", None)
      if callable(snap_fn):
        sg = snap_fn(self._path, g)
        if isinstance(sg, QRect):
          g = sg
    else:
      from studio.services.free_layout import min_rect_for_type

      wtype = str(self._spec.get("type", ""))
      min_dw, min_dh = min_rect_for_type(wtype)
      min_sw = max(int(min_dw * self._scale), SNAP_GRID * 6)
      min_sh = max(int(min_dh * self._scale), SNAP_GRID * 4)
      g.setWidth(max(min_sw, self._start_geom.width() + delta.x()))
      g.setHeight(max(min_sh, self._start_geom.height() + delta.y()))
      g = self._clamp_geometry(g)
    self.setGeometry(g)
    event.accept()

  def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if self._mode and event.button() == Qt.MouseButton.LeftButton:
      if self.mouseGrabber() is self:
        self.releaseMouse()
      self._set_drag_lightweight(False)
      geom = self.geometry()
      if geom != self._start_geom:
        x = int(round(geom.x() / self._scale))
        y = int(round(geom.y() / self._scale))
        w = int(round(geom.width() / self._scale))
        h = int(round(geom.height() / self._scale))
        self.rect_changed.emit(self._path, x, y, w, h)
      else:
        parent = self.parentWidget()
        if isinstance(parent, InterfaceCanvas):
          parent.set_snap_guides([], scale=self._scale)
    self._mode = ""
    self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    super().mouseReleaseEvent(event)


class InterfaceCanvas(QWidget):
  """单个界面的可滚动内容区。"""

  context_menu_requested = Signal(object)
  marquee_finished = Signal(object)  # list[tuple[int, ...]]

  def __init__(self, parent=None) -> None:
    super().__init__(parent)
    self.setObjectName("InterfaceCanvas")
    self._items: list[FreeDesignItem] = []
    self._guides: list[tuple[str, int]] = []
    self._guide_scale = 1.0
    self._marquee_enabled = True
    self._marquee_origin: QPoint | None = None
    self._marquee_rect: QRect | None = None
    self.setMouseTracking(True)
    self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.customContextMenuRequested.connect(
      lambda pos: self.context_menu_requested.emit(self.mapToGlobal(pos))
    )

  def clear_items(self) -> None:
    for it in self._items:
      it.deleteLater()
    self._items = []

  def add_item(self, item: FreeDesignItem) -> None:
    item.setParent(self)
    self._items.append(item)

  def set_marquee_enabled(self, enabled: bool) -> None:
    self._marquee_enabled = bool(enabled)

  def set_snap_guides(self, guides: list[tuple[str, int]], *, scale: float) -> None:
    self._guides = list(guides or [])
    self._guide_scale = max(0.01, scale)
    self.update()

  def _hit_design_item(self, pos: QPoint) -> FreeDesignItem | None:
    w = self.childAt(pos)
    while w is not None and w is not self:
      if isinstance(w, FreeDesignItem):
        return w
      w = w.parentWidget()
    return None

  def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if (
      self._marquee_enabled
      and event.button() == Qt.MouseButton.LeftButton
      and self._hit_design_item(event.position().toPoint()) is None
    ):
      self._marquee_origin = event.position().toPoint()
      self._marquee_rect = QRect(self._marquee_origin, self._marquee_origin)
      self.update()
      event.accept()
      return
    super().mousePressEvent(event)

  def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if self._marquee_origin is not None:
      self._marquee_rect = QRect(self._marquee_origin, event.position().toPoint()).normalized()
      self.update()
      event.accept()
      return
    super().mouseMoveEvent(event)

  def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if self._marquee_origin is not None and event.button() == Qt.MouseButton.LeftButton:
      rect = self._marquee_rect or QRect()
      paths = [it.path() for it in self._items if rect.intersects(it.geometry())]
      self._marquee_origin = None
      self._marquee_rect = None
      self.update()
      if paths:
        self.marquee_finished.emit(paths)
      event.accept()
      return
    super().mouseReleaseEvent(event)

  def paintEvent(self, event) -> None:  # noqa: N802
    super().paintEvent(event)
    p = QPainter(self)
    if self._guides:
      pen = QPen(QColor(37, 99, 235, 180))
      pen.setWidth(1)
      pen.setStyle(Qt.PenStyle.DashLine)
      p.setPen(pen)
      for kind, design_v in self._guides:
        if kind == "v":
          x = int(design_v * self._guide_scale)
          p.drawLine(x, 0, x, self.height())
        else:
          y = int(design_v * self._guide_scale)
          p.drawLine(0, y, self.width(), y)
    if self._marquee_rect is not None and self._marquee_rect.width() > 2:
      fill = QColor(37, 99, 235, 40)
      edge = QPen(QColor(37, 99, 235, 200))
      edge.setWidth(1)
      edge.setStyle(Qt.PenStyle.DashLine)
      p.setPen(edge)
      p.setBrush(fill)
      p.drawRect(self._marquee_rect)
    p.end()


@dataclass
class _PhoneShell:
    wrap: QWidget
    phone: QFrame
    inner: QWidget
    title: QLabel
    tab_bar: QWidget
    tab_buttons: list[QPushButton]
    scroll: QScrollArea
    canvas: InterfaceCanvas
    chrome_host: QWidget
    hint: QLabel | None
    design_wh: tuple[int, int]
    scale: float
    screen_count: int
    compact_preview: bool
    interactive_preview: bool
    phone_style: bool
    device_emulation: bool = False
    landscape: bool = False
    auto_fit: bool = False
    main_panel_preview: bool = False
    apk_shell_preview: bool = False
    compare_opacity: float = 0.0
    backdrop_key: int = 0
    device_wh: tuple[int, int] = (0, 0)
    status_bar: QWidget | None = None
    home_indicator: QWidget | None = None
    host_app_bar: QWidget | None = None
    floating_ball: QWidget | None = None
    backdrop: QLabel | None = None
    panel_card: QWidget | None = None
    content_host: QWidget | None = None


class PhoneCanvasWidget(QScrollArea):
  layout_changed = Signal(dict)
  widget_selected = Signal(tuple)
  selection_changed = Signal(object)  # list[tuple[int, ...]]
  screen_changed = Signal(int)
  values_changed = Signal()
  nudge_selected = Signal(int, int)
  delete_selected = Signal()
  duplicate_selected = Signal()
  undo_requested = Signal()
  redo_requested = Signal()
  context_menu_requested = Signal(object)

  def __init__(self) -> None:
    super().__init__()
    self.setObjectName("PhoneCanvas")
    self.setWidgetResizable(True)
    self._viewport = QWidget()
    self._viewport.setObjectName("PreviewViewport")
    self._viewport.setStyleSheet("background: #FFFFFF;")
    self.setWidget(self._viewport)
    self._root = QVBoxLayout(self._viewport)
    self._root.setContentsMargins(8, 8, 8, 8)
    self._layout: dict[str, Any] = {}
    self._selected_path: tuple[int, ...] = ()
    self._selected_paths: set[tuple[int, ...]] = set()
    self._items: list[FreeDesignItem] = []
    self._compare_opacity = 0.0
    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    self._scale = 0.45
    self._last_scale = 0.0
    self._interface_canvas: InterfaceCanvas | None = None
    self._chrome_host: QWidget | None = None
    self._shell: _PhoneShell | None = None
    self._suppress_rebuild = False
    self._rebuilding = False
    self._suppress_layout_emit = False
    self._interactive_preview = False
    self._editable = True
    self._selectable = False
    self._compact_preview = False
    self._fit_viewport = False
    self._min_scale = 0.35
    self._phone_style = False
    self._device_emulation = False
    self._landscape = False
    self._auto_fit_device = False
    self._main_panel_preview = False
    self._apk_shell_preview = False
    self._backdrop_pixmap: QPixmap | None = None
    self._target_screen_px: int | None = None
    self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.customContextMenuRequested.connect(
      lambda pos: self.context_menu_requested.emit(self.mapToGlobal(pos))
    )

  def set_interactive_preview(self, enabled: bool) -> None:
    if self._interactive_preview == enabled:
      return
    self._interactive_preview = enabled
    self._rebuild(full=True)

  def set_editable(self, enabled: bool) -> None:
    if self._editable == enabled:
      return
    self._editable = enabled
    self._rebuild(full=True)

  def set_selectable(self, enabled: bool) -> None:
    """只读预览下允许点击选中控件（脚本页插入 Lua）。"""
    if self._selectable == enabled:
      return
    self._selectable = enabled
    self._rebuild(full=True)

  def set_compact_preview(self, enabled: bool) -> None:
    if self._compact_preview == enabled:
      return
    self._compact_preview = enabled
    self._rebuild(full=True)

  def set_fit_viewport(self, enabled: bool) -> None:
    """缩放到当前视口内完整显示手机框（脚本页等窄栏预览）。"""
    if self._fit_viewport == enabled:
      return
    self._fit_viewport = enabled
    self.setVerticalScrollBarPolicy(
      Qt.ScrollBarPolicy.ScrollBarAlwaysOff
      if enabled
      else Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    )
    self._rebuild(full=True)

  def set_min_scale(self, value: float) -> None:
    """预览最小缩放（脚本页窄栏可设高一些，避免表单控件被裁切）。"""
    clamped = max(0.15, min(1.0, float(value)))
    if abs(clamped - self._min_scale) < 0.001:
      return
    self._min_scale = clamped
    self._rebuild(full=True)

  def set_phone_style(self, enabled: bool) -> None:
    """手机外框样式（圆角深色边框，编辑器紧凑预览）。"""
    if self._phone_style == enabled:
      return
    self._phone_style = enabled
    self._rebuild(full=True)

  def set_device_emulation(self, enabled: bool) -> None:
    """浏览器 DevTools 风格设备仿真：灰底居中、状态栏、Home 条、阴影外框。"""
    if self._device_emulation == enabled:
      return
    self._device_emulation = enabled
    self._apply_viewport_style()
    self._rebuild(full=True)

  def set_preview_landscape(self, enabled: bool) -> None:
    """横屏设备仿真（宽高对调，host 模式下面板按 position 浮动）。"""
    if self._landscape == enabled:
      return
    self._landscape = enabled
    self._rebuild(full=True)

  def set_auto_fit_device(self, enabled: bool) -> None:
    """设备尽量撑满预览区（类似 Chrome DevTools 适应窗口）。"""
    if self._auto_fit_device == enabled:
      return
    self._auto_fit_device = enabled
    if enabled:
      self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
      self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    elif not self._main_panel_preview:
      self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
      self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self._rebuild(full=True)

  def set_main_panel_preview(self, enabled: bool) -> None:
    """APK 主面板预览：layout 表单（对齐 HostPanelRenderer），不含悬浮球/Overlay 仿真。"""
    if self._main_panel_preview == enabled:
      return
    self._main_panel_preview = enabled
    if not enabled:
      self._apk_shell_preview = False
    self._apply_viewport_style()
    self._rebuild(full=True)

  def set_apk_shell_preview(self, enabled: bool) -> None:
    """在 main_panel_preview 上叠加 APK 固定外壳：设置 / 启停 / 运行日志。"""
    if self._apk_shell_preview == enabled:
      return
    self._apk_shell_preview = enabled
    if enabled:
      self._main_panel_preview = True
    self._apply_viewport_style()
    self._rebuild(full=True)

  def main_panel_preview(self) -> bool:
    return self._main_panel_preview

  def set_backdrop_pixmap(self, pixmap: QPixmap | None) -> None:
    """实机截图作为设备屏背景（类似 DevTools 中加载页面）。"""
    self._backdrop_pixmap = pixmap
    self._rebuild(full=True)

  def preview_landscape(self) -> bool:
    return self._landscape

  def _apply_viewport_style(self) -> None:
    if self._main_panel_preview:
      self._viewport.setStyleSheet("background: #F8FAFC;")
      self.setStyleSheet("QScrollArea#PhoneCanvas { background: #F8FAFC; border: none; }")
    elif self._device_emulation and self._phone_style:
      self._viewport.setStyleSheet(f"background: {DEVTOOLS_CANVAS_BG};")
      self.setStyleSheet(
        f"QScrollArea#PhoneCanvas {{ background: {DEVTOOLS_CANVAS_BG}; border: none; }}"
      )
    else:
      self._viewport.setStyleSheet("background: #FFFFFF;")
      self.setStyleSheet("")

  def set_target_screen_width(self, px: int | None) -> None:
    """固定屏幕宽度（设计像素换算后的目标 px；None 表示按视口自适应）。"""
    target = None if px is None else max(180, int(px))
    if target == self._target_screen_px:
      return
    self._target_screen_px = target
    self._rebuild(full=True)

  def refresh_viewport(self) -> None:
    if self._layout:
      self._rebuild(full=True)

  def interactive_preview(self) -> bool:
    return self._interactive_preview

  def set_layout(self, layout: dict[str, Any], *, selected_path: tuple[int, ...] | None = None, full: bool = False) -> None:
    old = PanelState.all()
    self._suppress_layout_emit = True
    try:
      self._layout = migrate_layout(clone_layout(layout or {}))
      PanelState.seed_from_layout(self._layout)
      if old:
        merged = dict(PanelState.all())
        merged.update({k: v for k, v in old.items() if k in merged})
        PanelState.reset(merged)
      if selected_path is not None:
        self._selected_path = selected_path
      self._rebuild(full=full or self._needs_full_rebuild())
      self.values_changed.emit()
    finally:
      self._suppress_layout_emit = False

  def set_selected_path(self, path: tuple[int, ...]) -> None:
    self._selected_path = path
    self._selected_paths = {path} if path else set()
    for it in self._items:
      it.set_selected(it.path() in self._selected_paths)
    self.selection_changed.emit(list(self._selected_paths))

  def set_selected_paths(self, paths: list[tuple[int, ...]]) -> None:
    cleaned = [p for p in paths if p]
    self._selected_paths = set(cleaned)
    self._selected_path = cleaned[0] if cleaned else ()
    for it in self._items:
      it.set_selected(it.path() in self._selected_paths)
    self.selection_changed.emit(list(self._selected_paths))
    if self._selected_path:
      self.widget_selected.emit(self._selected_path)

  def selected_paths(self) -> list[tuple[int, ...]]:
    return list(self._selected_paths)

  def flash_paths(self, paths: list[tuple[int, ...]], *, ms: int = 750) -> None:
    want = set(paths or [])
    for it in self._items:
      it.set_flash(it.path() in want)
    QTimer.singleShot(max(200, int(ms)), self._clear_item_flash)

  def _clear_item_flash(self) -> None:
    for it in self._items:
      it.set_flash(False)

  def _on_marquee_finished(self, paths: object) -> None:
    if not self._editable:
      return
    plist = [p for p in (paths or []) if isinstance(p, tuple) and len(p) == 2]
    # 框选仅当前界面控件
    active = active_screen_index(self._layout)
    plist = [p for p in plist if p[0] == active]
    if not plist:
      return
    mods = QApplication.keyboardModifiers()
    if mods & Qt.KeyboardModifier.ControlModifier:
      merged = set(self._selected_paths)
      merged.update(plist)
      self.set_selected_paths(list(merged))
    else:
      self.set_selected_paths(plist)

  def set_compare_opacity(self, opacity: float) -> None:
    """0=关闭对照；0.15~0.55 抓抓截图半透明叠在主面板底。"""
    self._compare_opacity = max(0.0, min(0.7, float(opacity)))
    self.refresh_viewport()

  def compare_opacity(self) -> float:
    return self._compare_opacity

  def refresh_widget_at(self, path: tuple[int, ...]) -> bool:
    from studio.services.screen_layout import resolve_widget

    spec = resolve_widget(self._layout, path)
    if spec is None:
      return False
    for item in self._items:
      if item.path() == path:
        item.reload_content(spec)
        return True
    return False

  def set_active_screen(self, idx: int) -> None:
    self._layout.setdefault("panel", {})["active_screen"] = idx
    self._selected_path = ()
    self._rebuild(full=False)
    self.screen_changed.emit(idx)

  def _needs_full_rebuild(self) -> bool:
    if self._shell is None:
      return True
    panel = self._layout.get("panel", {})
    dw, dh = panel_design_size(panel)
    if (dw, dh) != self._shell.design_wh:
      return True
    if len(screens(self._layout)) != self._shell.screen_count:
      return True
    if self._compact_preview != self._shell.compact_preview:
      return True
    if self._interactive_preview != self._shell.interactive_preview:
      return True
    if self._phone_style != self._shell.phone_style:
      return True
    if self._device_emulation != self._shell.device_emulation:
      return True
    if self._landscape != self._shell.landscape:
      return True
    backdrop_key = id(self._backdrop_pixmap) if self._backdrop_pixmap is not None else 0
    if backdrop_key != self._shell.backdrop_key:
      return True
    if self._auto_fit_device != getattr(self._shell, "auto_fit", False):
      return True
    if self._main_panel_preview != getattr(self._shell, "main_panel_preview", False):
      return True
    if self._apk_shell_preview != getattr(self._shell, "apk_shell_preview", False):
      return True
    if abs(self._compare_opacity - getattr(self._shell, "compare_opacity", 0.0)) >= 0.01:
      return True
    new_scale = self._effective_scale(dw, dh)
    if abs(new_scale - self._shell.scale) >= 0.01:
      return True
    return False

  def _hint_reserve_px(self) -> int:
    return 0 if self._compact_preview else 56

  def _effective_scale(self, design_w: int, design_h: int) -> float:
    vp = self.viewport()
    if self._main_panel_preview and not self._device_emulation:
      return compute_preview_scale(
        design_w=design_w,
        design_h=design_h,
        viewport_w=vp.width(),
        viewport_h=vp.height(),
        target_screen_px=self._target_screen_px,
        fit_viewport=True,
        min_scale=self._min_scale,
        hint_reserve=self._hint_reserve_px(),
      )
    pw, ph = design_w, design_h
    if self._landscape:
      pw, ph = design_h, design_w
    if self._auto_fit_device and self._device_emulation and self._phone_style:
      gutter = 32
      vw = max(160, vp.width() - gutter)
      vh = max(200, vp.height() - gutter)
      scale_w = vw / max(1, pw)
      scale_h = vh / max(1, ph)
      return max(self._min_scale, min(1.0, scale_w, scale_h))
    if self._landscape:
      design_w, design_h = design_h, design_w
    return compute_preview_scale(
      design_w=design_w,
      design_h=design_h,
      viewport_w=vp.width(),
      viewport_h=vp.height(),
      target_screen_px=self._target_screen_px,
      fit_viewport=self._fit_viewport,
      min_scale=self._min_scale,
      hint_reserve=self._hint_reserve_px(),
    )

  def resizeEvent(self, event) -> None:  # noqa: N802
    super().resizeEvent(event)
    if not self._layout or self._suppress_rebuild or self._rebuilding:
      return
    panel = self._layout.get("panel", {})
    dw, dh = panel_design_size(panel)
    new_scale = self._effective_scale(dw, dh)
    if self._last_scale > 0 and abs(new_scale - self._last_scale) < 0.01:
      return
    self._rebuild(full=True)

  def _rebuild(self, *, full: bool = True) -> None:
    if self._suppress_rebuild or self._rebuilding:
      return
    if not full and self._shell is not None and not self._needs_full_rebuild():
      self._rebuilding = True
      self._viewport.setUpdatesEnabled(False)
      try:
        self._sync_shell_content()
      finally:
        self._viewport.setUpdatesEnabled(True)
        self._rebuilding = False
      return
    self._rebuilding = True
    self._viewport.setUpdatesEnabled(False)
    try:
      self._destroy_shell()
      self._shell = self._build_shell()
      self._interface_canvas = self._shell.canvas
      self._chrome_host = self._shell.chrome_host
      self._sync_shell_content()
      self._attach_shell_to_root()
    finally:
      self._viewport.setUpdatesEnabled(True)
      self._rebuilding = False

  def _destroy_shell(self) -> None:
    while self._root.count():
      item = self._root.takeAt(0)
      w = item.widget()
      if w is not None:
        w.setParent(None)
        w.deleteLater()
    self._root.setContentsMargins(8, 8, 8, 8)
    self._items = []
    self._interface_canvas = None
    self._chrome_host = None
    self._shell = None

  def _build_shell(self) -> _PhoneShell:
    panel = self._layout.get("panel", {})
    theme = panel_theme_colors(str(panel.get("theme", "light")))
    dw, dh = panel_design_size(panel)
    self._scale = self._effective_scale(dw, dh)
    self._last_scale = self._scale
    bezel = _bezel_px(self._scale, phone_style=self._phone_style)
    frame_radius = _phone_frame_radius(self._scale, phone_style=self._phone_style)
    active = active_screen_index(self._layout)
    sc_list = screens(self._layout)
    emulate = self._device_emulation and self._phone_style and not self._main_panel_preview
    host = is_host_display(panel)
    landscape = self._landscape and emulate
    host_overlay = host and emulate and not self._main_panel_preview

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)

    phone = QFrame()
    phone.setObjectName("PhoneFrame")
    phone_lay = QVBoxLayout(phone)
    phone_lay.setContentsMargins(bezel, bezel, bezel, bezel)
    phone_lay.setSpacing(0)
    if self._phone_style and not self._main_panel_preview:
      phone.setStyleSheet(
        f"QFrame#PhoneFrame {{ background:#0F172A; border:2px solid #334155; "
        f"border-radius:{frame_radius}px; }}"
      )
      if emulate:
        shadow = QGraphicsDropShadowEffect(phone)
        shadow.setBlurRadius(max(24, int(32 * self._scale)))
        shadow.setOffset(0, max(4, int(8 * self._scale)))
        shadow.setColor(QColor(0, 0, 0, 90))
        phone.setGraphicsEffect(shadow)
    elif self._main_panel_preview and self._apk_shell_preview:
      phone.setStyleSheet(
        "QFrame#PhoneFrame { background:#F8FAFC; border:1px solid #CBD5E1; "
        f"border-radius:{max(8, int(12 * self._scale))}px; }}"
      )
    elif self._main_panel_preview:
      phone.setStyleSheet(
        f"QFrame#PhoneFrame {{ background:{theme.screen_bg}; border:1px solid #CBD5E1; "
        f"border-radius:{max(8, int(12 * self._scale))}px; }}"
      )
    else:
      phone.setFixedWidth(int(dw * self._scale) + 4)
      phone_lay.setContentsMargins(2, 2, 2, 2)

    if landscape or host_overlay:
      device_sw, device_sh = compute_device_screen_px(dw, dh, self._scale, landscape=landscape)
    elif self._main_panel_preview:
      device_sw = int(dw * self._scale)
      shell_extra = _apk_shell_extra_dp() if self._apk_shell_preview else 0
      device_sh = int(dh * self._scale) + int(shell_extra * self._scale)
    else:
      device_sw = int(dw * self._scale)
      device_sh = 0
    sw = device_sw

    overlay_rect = None
    panel_scale = self._scale
    if host_overlay:
      overlay_rect = compute_host_panel_overlay_rect(self._layout, device_sw, device_sh)
      panel_scale = overlay_rect.inner_scale

    inner = QWidget()
    inner.setObjectName("PhoneScreen")
    inner.setFixedWidth(device_sw)
    if landscape or host_overlay or (self._main_panel_preview and not self._apk_shell_preview):
      inner.setFixedHeight(device_sh)
    if self._phone_style:
      inner_radius = max(4, frame_radius - bezel)
      screen_bg = "transparent" if host_overlay else theme.screen_bg
      inner.setStyleSheet(
        f"QWidget#PhoneScreen {{ background:{screen_bg}; border-radius:{inner_radius}px; }}"
      )

    backdrop: QLabel | None = None
    panel_card: QFrame | None = None
    apk_page_lay: QVBoxLayout | None = None
    ui_scale = self._scale
    if emulate and (landscape or host_overlay):
      backdrop = _build_device_backdrop(inner, device_sw, device_sh, self._backdrop_pixmap)
      backdrop.lower()
    elif (
      self._main_panel_preview
      and self._compare_opacity > 0
      and self._backdrop_pixmap is not None
      and not self._backdrop_pixmap.isNull()
    ):
      from PySide6.QtWidgets import QGraphicsOpacityEffect

      backdrop = _build_device_backdrop(inner, device_sw, max(device_sh, 1), self._backdrop_pixmap)
      eff = QGraphicsOpacityEffect(backdrop)
      eff.setOpacity(self._compare_opacity)
      backdrop.setGraphicsEffect(eff)
      backdrop.raise_()

    if host_overlay and overlay_rect is not None:
      panel_card = QFrame(inner)
      panel_card.setObjectName("PanelOverlayCard")
      panel_card.setStyleSheet(
        "QFrame#PanelOverlayCard { background:#FFFFFF; border-radius:8px; "
        "border:1px solid #CBD5E1; }"
      )
      panel_card.setGeometry(overlay_rect.x, overlay_rect.y, overlay_rect.w, overlay_rect.h)
      content_root = panel_card
      content_lay = QVBoxLayout(panel_card)
      content_lay.setContentsMargins(0, 0, 0, 0)
      content_lay.setSpacing(0)
      ui_scale = panel_scale
      show_host_bar = False
    elif self._apk_shell_preview and self._main_panel_preview:
      pad = int(APK_SHELL_PAD_DP * ui_scale)
      page = QWidget()
      page.setObjectName("PhoneScreen")
      page.setFixedWidth(device_sw)
      apk_page_lay = QVBoxLayout(page)
      apk_page_lay.setContentsMargins(pad, pad, pad, pad)
      apk_page_lay.setSpacing(int(8 * ui_scale))

      toolbar = QWidget()
      tb_lay = QHBoxLayout(toolbar)
      tb_lay.setContentsMargins(0, 0, 0, 0)
      tb_lay.addStretch()
      settings_btn = QPushButton("⚙")
      settings_btn.setToolTip("设置（APK 固定入口，预览不可点）")
      settings_btn.setEnabled(False)
      btn_sz = int(40 * ui_scale)
      settings_btn.setFixedSize(btn_sz, btn_sz)
      settings_btn.setStyleSheet(
        "QPushButton { border:1px solid #CBD5E1; border-radius:8px; background:#FFFFFF; }"
      )
      tb_lay.addWidget(settings_btn)
      toolbar.setFixedHeight(int(APK_SHELL_TOOLBAR_DP * ui_scale))
      apk_page_lay.addWidget(toolbar)

      layout_host = QFrame()
      layout_host.setObjectName("LayoutPanelHost")
      layout_host.setStyleSheet(
        "QFrame#LayoutPanelHost { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; }"
      )
      content_root = layout_host
      content_lay = QVBoxLayout(layout_host)
      content_lay.setContentsMargins(0, 0, 0, 0)
      content_lay.setSpacing(0)
      inner = page
      ui_scale = self._scale
      show_host_bar = False
    else:
      content_root = inner
      content_lay = QVBoxLayout(inner)
      content_lay.setContentsMargins(0, 0, 0, 0)
      content_lay.setSpacing(0)
      ui_scale = self._scale
      show_host_bar = host and emulate and not landscape and not host_overlay
      if emulate and not landscape and not host_overlay:
        top_pad = _status_bar_height(ui_scale)
        if show_host_bar:
          top_pad += _host_app_bar_height(ui_scale)
        content_lay.setContentsMargins(0, top_pad, 0, _home_indicator_height(ui_scale))
      elif emulate and landscape and not host_overlay:
        content_lay.setContentsMargins(0, _status_bar_height(ui_scale), 0, _home_indicator_height(ui_scale))

    title_h = int(TITLE_DP * ui_scale)
    title = QLabel(panel.get("title", "脚本助手"), content_root)
    title.setFixedHeight(title_h)
    title_fs = max(9, int(13 * ui_scale))
    title_radius = 0 if emulate else max(0, frame_radius - bezel) if self._phone_style else 0
    title.setStyleSheet(
      f"background:{theme.title_bg};color:{theme.title_fg};font-weight:600;font-size:{title_fs}px;"
      + (f"border-top-left-radius:{title_radius}px;border-top-right-radius:{title_radius}px;" if title_radius else "")
    )
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    content_lay.addWidget(title)

    tab_scroll, tab_buttons = _build_screen_tab_bar(
      sc_list, active, ui_scale, self._on_tab_clicked
    )
    content_lay.addWidget(tab_scroll)

    tab_h = _screen_tab_bar_height(ui_scale)
    chrome_dp = int(_chrome_dp(self._layout) * ui_scale)
    if self._main_panel_preview:
      layout_body_h = int(dh * self._scale)
      view_h = max(120, layout_body_h - title_h - tab_h - chrome_dp)
    else:
      view_h = int((dh - TITLE_DP - TAB_BAR_DP - _chrome_dp(self._layout)) * ui_scale)
    if host_overlay and overlay_rect is not None:
      view_h = max(80, overlay_rect.h - title_h - tab_h - int(_chrome_dp(self._layout) * ui_scale))
    elif landscape and not host_overlay:
      reserved = _status_bar_height(ui_scale) + _home_indicator_height(ui_scale)
      view_h = min(
        view_h,
        max(
          120,
          device_sh - reserved - title_h - tab_h - int(_chrome_dp(self._layout) * ui_scale),
        ),
      )
    scroll = QScrollArea(content_root)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFixedHeight(max(120 if landscape else 200, view_h))
    scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {theme.screen_bg}; }}")

    canvas = InterfaceCanvas()
    canvas.context_menu_requested.connect(self.context_menu_requested.emit)
    canvas.set_marquee_enabled(self._editable)
    canvas.marquee_finished.connect(self._on_marquee_finished)
    scroll.setWidget(canvas)
    content_lay.addWidget(scroll, 1)

    chrome_h = int(_chrome_dp(self._layout) * ui_scale)
    chrome_host = QWidget(content_root)
    chrome_host.setFixedHeight(max(0, chrome_h))
    chrome_host.setVisible(chrome_h > 0)
    chrome_host.setStyleSheet(
      f"background:{theme.chrome_bg};border-top:1px solid {theme.chrome_border};"
    )
    chrome_host.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    chrome_host.customContextMenuRequested.connect(
      lambda pos, host=chrome_host: self.context_menu_requested.emit(host.mapToGlobal(pos))
    )
    content_lay.addWidget(chrome_host)

    if apk_page_lay is not None:
      apk_page_lay.addWidget(content_root, 1)
      btn_h = int(APK_SHELL_BTN_DP * ui_scale)
      start_btn = QPushButton("开始运行脚本")
      start_btn.setEnabled(False)
      start_btn.setFixedHeight(btn_h)
      start_btn.setStyleSheet(
        f"QPushButton {{ background:{theme.accent}; color:#FFFFFF; font-weight:600; "
        "border:none; border-radius:8px; }"
      )
      apk_page_lay.addWidget(start_btn)
      stop_btn = QPushButton("停止")
      stop_btn.setEnabled(False)
      stop_btn.setFixedHeight(btn_h)
      stop_btn.setStyleSheet(
        "QPushButton { background:#F1F5F9; color:#334155; border:1px solid #CBD5E1; border-radius:8px; }"
      )
      apk_page_lay.addWidget(stop_btn)
      log_title = QLabel("运行日志")
      log_title.setStyleSheet(
        f"font-weight:600; font-size:{max(10, int(14 * ui_scale))}px; color:#1A2332;"
      )
      apk_page_lay.addWidget(log_title)
      log_box = QLabel("（脚本运行日志将显示于此）")
      log_box.setFixedHeight(int(APK_SHELL_LOG_DP * ui_scale))
      log_box.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
      log_box.setWordWrap(True)
      log_box.setStyleSheet(
        "QLabel { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; "
        f"padding:{max(4, int(8 * ui_scale))}px; font-family:Consolas,monospace; "
        f"font-size:{max(9, int(11 * ui_scale))}px; color:#64748B; }}"
      )
      apk_page_lay.addWidget(log_box)
      inner.setFixedHeight(device_sh)

    if host_overlay and panel_card is not None and overlay_rect is not None:
      panel_card.setGeometry(overlay_rect.x, overlay_rect.y, overlay_rect.w, overlay_rect.h)
      panel_card.raise_()
      self._scale = panel_scale
    else:
      self._scale = ui_scale

    status_bar: QWidget | None = None
    home_indicator: QWidget | None = None
    host_app_bar: QWidget | None = None
    floating_ball: QWidget | None = None
    chrome_sw = device_sw
    if emulate:
      status_bar = _build_status_bar_overlay(self._scale, parent=inner)
      status_bar.setFixedWidth(chrome_sw)
      status_bar.move(0, 0)
      status_bar.raise_()
      if show_host_bar:
        host_app_bar = _build_host_app_bar(
          self._scale,
          parent=inner,
          title=str(panel.get("title", "Auto Script")),
        )
        host_app_bar.setFixedWidth(chrome_sw)
        host_app_bar.move(0, _status_bar_height(self._scale))
        host_app_bar.raise_()
      if host and not self._main_panel_preview:
        ball_dp = int(panel.get("ball_size_dp", 48))
        floating_ball = _build_floating_ball(
          self._scale,
          parent=inner,
          ball_dp=ball_dp,
          accent=theme.accent,
        )
      if not self._main_panel_preview:
        home_indicator = _build_home_indicator_overlay(self._scale, parent=inner, screen_w=chrome_sw)

    phone_lay.addWidget(inner)
    row.addWidget(phone)
    wrap = QWidget()
    wrap.setLayout(row)
    wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    hint: QLabel | None = None
    if not self._compact_preview:
      hint = QLabel()
      hint.setObjectName("HintLabel")
      hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
      hint.setWordWrap(True)

    phone_outer_w = device_sw + bezel * 2
    phone.setFixedWidth(phone_outer_w)
    if landscape or host_overlay or self._main_panel_preview:
      phone.setFixedHeight(device_sh + bezel * 2)

    backdrop_key = id(self._backdrop_pixmap) if self._backdrop_pixmap is not None else 0

    return _PhoneShell(
      wrap=wrap,
      phone=phone,
      inner=inner,
      title=title,
      tab_bar=tab_scroll,
      tab_buttons=tab_buttons,
      scroll=scroll,
      canvas=canvas,
      chrome_host=chrome_host,
      hint=hint,
      design_wh=(dw, dh),
      scale=self._scale,
      screen_count=len(sc_list),
      compact_preview=self._compact_preview,
      interactive_preview=self._interactive_preview,
      phone_style=self._phone_style,
      device_emulation=emulate,
      landscape=landscape,
      auto_fit=self._auto_fit_device,
      main_panel_preview=self._main_panel_preview,
      apk_shell_preview=self._apk_shell_preview,
      compare_opacity=self._compare_opacity,
      backdrop_key=backdrop_key,
      device_wh=(device_sw, device_sh if (landscape or host_overlay) else 0),
      status_bar=status_bar,
      home_indicator=home_indicator,
      host_app_bar=host_app_bar,
      floating_ball=floating_ball,
      backdrop=backdrop,
      panel_card=panel_card,
    )

  def _hint_text(self, dw: int, dh: int) -> str:
    if self._apk_shell_preview:
      base = (
        f"APK 完整预览 {dw}×{dh}  ·  中间为 layout.json 脚本面板（标题=panel.title）"
        "  ·  下方为打包固定增加的启停与日志"
      )
    elif self._main_panel_preview:
      base = (
        f"脚本面板预览 {dw}×{dh}  ·  与 APK 内 layout 一致（panel.title + 标签页 + 控件）"
        "  ·  打包后 APK 另增设置/启停/日志"
      )
    elif self._device_emulation and self._phone_style:
      orient = "横屏" if self._landscape else "竖屏"
      preset = f"{sw}px 屏宽" if (sw := self._target_screen_px) else f"设计 {dw}×{dh}"
      base = f"设备仿真 · {orient} · {preset}  ·  Ctrl+滚轮微调宽度"
      if self._backdrop_pixmap is not None and not self._backdrop_pixmap.isNull():
        base += "  ·  已加载截图背景"
    elif is_host_display(self._layout.get("panel")):
      base = (
        f"主页面表单预览 {dw}×{dh}  ·  点击标签切换界面  ·  拖动移动控件"
        "  ·  APK 启停由悬浮球控制"
      )
    else:
      base = (
        f"设计 {dw}×{dh}  ·  点击标签切换界面  ·  拖动移动控件  ·  右下角缩放  ·  界面可上下滚动"
      )
    if self._interactive_preview:
      base += "  ·  交互预览：顶部色条拖动，控件区内可操作"
    if self._device_emulation and is_host_display(self._layout.get("panel")):
      base += "  ·  右侧悬浮球为实机启停入口"
    return base

  def _sync_shell_content(self) -> None:
    if self._shell is None:
      return
    shell = self._shell
    panel = self._layout.get("panel", {})
    theme = panel_theme_colors(str(panel.get("theme", "light")))
    dw, dh = shell.design_wh
    self._scale = self._effective_scale(dw, dh)
    shell.scale = self._scale
    emulate = shell.device_emulation
    landscape = shell.landscape
    host = is_host_display(panel)
    host_overlay = host and emulate and shell.panel_card is not None and not shell.main_panel_preview
    if landscape or host_overlay:
      device_sw, device_sh = compute_device_screen_px(dw, dh, self._scale, landscape=landscape)
    elif shell.main_panel_preview:
      device_sw = int(dw * self._scale)
      shell_extra = _apk_shell_extra_dp() if shell.apk_shell_preview else 0
      device_sh = int(dh * self._scale) + int(shell_extra * self._scale)
    else:
      device_sw = int(dw * self._scale)
      device_sh = 0
    sw = device_sw
    bezel = _bezel_px(self._scale, phone_style=self._phone_style)
    frame_radius = _phone_frame_radius(self._scale, phone_style=self._phone_style)
    active = active_screen_index(self._layout)
    sc_list = screens(self._layout)

    shell.title.setText(panel.get("title", "脚本助手"))
    title_h = int(TITLE_DP * self._scale)
    shell.title.setFixedHeight(title_h)
    title_fs = max(9, int(13 * self._scale))
    title_radius = 0 if emulate else max(0, frame_radius - bezel) if self._phone_style else 0
    shell.title.setStyleSheet(
      f"background:{theme.title_bg};color:{theme.title_fg};font-weight:600;font-size:{title_fs}px;"
      + (f"border-top-left-radius:{title_radius}px;border-top-right-radius:{title_radius}px;" if title_radius else "")
    )
    tab_h = _screen_tab_bar_height(self._scale)
    shell.tab_bar.setFixedHeight(tab_h)
    for i, tb in enumerate(shell.tab_buttons):
      if i < len(sc_list):
        tb.setText(sc_list[i].get("title", f"界面{i + 1}"))
      tb.blockSignals(True)
      tb.setChecked(i == active)
      tb.blockSignals(False)
      tb.setStyleSheet(_screen_tab_stylesheet(self._scale, checked=i == active))

    if 0 <= active < len(shell.tab_buttons):
      shell.tab_bar.ensureWidgetVisible(shell.tab_buttons[active], 12, 0)

    content_h_design = content_height(
      self._layout,
      active,
      min_canvas=0 if (self._fit_viewport or self._target_screen_px or self._auto_fit_device) else 800,
    )
    chrome_h = int(_chrome_dp(self._layout) * self._scale)
    if shell.main_panel_preview:
      layout_body_h = int(dh * self._scale)
      view_h = max(120, layout_body_h - title_h - tab_h - chrome_h)
    else:
      view_h = int((dh - TITLE_DP - TAB_BAR_DP - _chrome_dp(self._layout)) * self._scale)
    if host_overlay and shell.panel_card is not None:
      overlay_rect = compute_host_panel_overlay_rect(self._layout, device_sw, device_sh)
      view_h = max(80, overlay_rect.h - title_h - tab_h - chrome_h)
    elif landscape and not host_overlay:
      reserved = _status_bar_height(self._scale) + _home_indicator_height(self._scale)
      view_h = min(
        view_h,
        max(
          120,
          device_sh - reserved - title_h - tab_h - chrome_h,
        ),
      )
    min_view = 120 if landscape else 200
    shell.scroll.setFixedHeight(max(min_view, view_h))
    canvas_h = int(content_h_design * self._scale)
    canvas_w = shell.panel_card.width() if host_overlay and shell.panel_card else sw
    shell.canvas.setFixedSize(canvas_w, max(canvas_h, shell.scroll.height()))

    shell.chrome_host.setFixedHeight(max(0, chrome_h))
    shell.chrome_host.setVisible(chrome_h > 0)

    show_host_bar = host and emulate and not landscape and not host_overlay
    top_pad = 0
    bottom_pad = 0
    if emulate and not host_overlay:
      top_pad = _status_bar_height(self._scale)
      if show_host_bar:
        top_pad += _host_app_bar_height(self._scale)
      bottom_pad = _home_indicator_height(self._scale)

    panel_body_h = title_h + tab_h + shell.scroll.height() + chrome_h
    if landscape or host_overlay or shell.main_panel_preview:
      phone_h = device_sh
      shell.inner.setFixedWidth(device_sw)
      shell.inner.setFixedHeight(device_sh)
      shell.phone.setFixedHeight(device_sh + bezel * 2)
    else:
      phone_h = panel_body_h + top_pad + bottom_pad
      shell.inner.setFixedWidth(device_sw)
      shell.inner.setFixedHeight(phone_h)
      shell.phone.setFixedHeight(phone_h + bezel * 2)

    phone_outer_w = device_sw + bezel * 2
    shell.phone.setFixedWidth(phone_outer_w)

    if shell.backdrop is not None:
      bh = device_sh if (landscape or host_overlay or shell.main_panel_preview) else phone_h
      shell.backdrop.setGeometry(0, 0, device_sw, bh)
      if self._backdrop_pixmap is not None and not self._backdrop_pixmap.isNull():
        shell.backdrop.setPixmap(
          self._backdrop_pixmap.scaled(
            device_sw,
            bh,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
          )
        )
        shell.backdrop.setText("")
      else:
        shell.backdrop.setPixmap(QPixmap())
        shell.backdrop.setText("宿主应用")
      shell.backdrop.lower()

    if host_overlay and shell.panel_card is not None:
      overlay_rect = compute_host_panel_overlay_rect(self._layout, device_sw, device_sh)
      shell.panel_card.setGeometry(overlay_rect.x, overlay_rect.y, overlay_rect.w, overlay_rect.h)
      shell.panel_card.raise_()
      top_pad = overlay_rect.y

    if shell.status_bar is not None:
      shell.status_bar.setFixedWidth(device_sw)
      shell.status_bar.move(0, 0)
      shell.status_bar.raise_()
    if shell.host_app_bar is not None:
      shell.host_app_bar.setFixedWidth(device_sw)
      shell.host_app_bar.move(0, _status_bar_height(self._scale))
      shell.host_app_bar.raise_()
    if shell.home_indicator is not None:
      shell.home_indicator.setFixedWidth(device_sw)
      home_y = (device_sh if (landscape or host_overlay) else phone_h) - _home_indicator_height(self._scale)
      shell.home_indicator.move(0, home_y)
      shell.home_indicator.raise_()
    if shell.floating_ball is not None and not shell.main_panel_preview:
      ball = shell.floating_ball
      margin = max(8, int(12 * self._scale))
      ball_y = top_pad + max(8, int(16 * self._scale)) if not host_overlay else margin
      ball.move(device_sw - ball.width() - margin, ball_y)
      ball.raise_()

    screen_widgets = sc_list[active].get("widgets") or [] if sc_list else []
    self._sync_widget_layer(shell.canvas, screen_widgets, active)
    self._sync_widget_layer(shell.chrome_host, chrome_widgets(self._layout), CHROME_PATH_TAG)

    if shell.hint is not None:
      shell.hint.setText(self._hint_text(dw, dh))
    hint_h = 0 if shell.hint is None else shell.hint.sizeHint().height() + 24
    total_h = phone_h + bezel * 2 + hint_h
    if self._fit_viewport:
      self._viewport.setMinimumHeight(0)
    else:
      self._viewport.setMinimumHeight(total_h)

  def _attach_shell_to_root(self) -> None:
    if self._shell is None:
      return
    shell = self._shell
    center_device = (
      self._device_emulation
      and self._phone_style
      and not self._fit_viewport
    )
    use_stretch = center_device and not self._auto_fit_device
    if use_stretch:
      self._root.setContentsMargins(12, 12, 12, 12)
      self._root.addStretch(1)
    elif center_device:
      self._root.setContentsMargins(8, 8, 8, 8)
    align_top = (not self._fit_viewport or self._target_screen_px is not None) and use_stretch
    v_align = Qt.AlignmentFlag.AlignTop if align_top else Qt.AlignmentFlag.AlignVCenter
    self._root.addWidget(shell.wrap, 0, Qt.AlignmentFlag.AlignHCenter | v_align)
    if shell.hint is not None:
      self._root.addWidget(shell.hint, 0, Qt.AlignmentFlag.AlignHCenter)
    if use_stretch:
      self._root.addStretch(1)

  def _make_design_item(
    self,
    path: tuple[int, ...],
    spec: dict[str, Any],
    scale: float,
    parent: QWidget,
    screen_idx: int,
  ) -> FreeDesignItem:
    theme_id = "light"
    if self._layout:
      theme_id = str((self._layout.get("panel") or {}).get("theme", "light") or "light")
    item = FreeDesignItem(
      path,
      spec,
      scale,
      parent,
      interactive=self._interactive_preview,
      editable=self._editable,
      selectable=self._selectable,
      on_values_changed=self.values_changed.emit,
      icon_only=screen_idx == CHROME_PATH_TAG and spec.get("type") in CHROME_ICONS,
      theme=theme_id,
      snap_move=self._snap_item_geometry,
    )
    item.rect_changed.connect(self._on_rect_changed)
    item.clicked.connect(self._on_item_clicked)
    item.set_selected(path in self._selected_paths or path == self._selected_path)
    item.show()
    item.raise_()
    self._items.append(item)
    return item

  def _sync_widget_layer(
    self,
    parent: QWidget,
    widgets: list,
    screen_idx: int,
  ) -> None:
    scale = self._scale
    existing = {it.path(): it for it in self._items if it.parent() is parent}
    seen: set[tuple[int, ...]] = set()
    kept: list[FreeDesignItem] = []

    for idx, spec in enumerate(widgets):
      if screen_idx == CHROME_PATH_TAG:
        path = path_for_chrome(idx)
      else:
        path = path_for_screen(screen_idx, idx)
      seen.add(path)
      x, y, w, h = _layout_rect(spec, scale)
      geom = QRect(x, y, w, h)
      if path in existing:
        item = existing[path]
        item._scale = scale
        if _widget_content_signature(item._spec) != _widget_content_signature(spec):
          item.reload_content(spec)
        elif item.geometry() != geom:
          item.setGeometry(geom)
          if item._form_like or item._interactive:
            item._mount_preview(item._spec)
        else:
          item.setGeometry(geom)
        item.set_selected(path in self._selected_paths or path == self._selected_path)
        item._snap_move = self._snap_item_geometry
        kept.append(item)
      else:
        kept.append(self._make_design_item(path, spec, scale, parent, screen_idx))
        kept[-1].setGeometry(geom)

    for path, item in existing.items():
      if path not in seen:
        if item in self._items:
          self._items.remove(item)
        item.deleteLater()

    self._items = [it for it in self._items if it.parent() is not parent] + kept
    # section 卡片垫底，表单控件叠在上面
    for it in kept:
      if str(it._spec.get("type", "")) == "section":
        it.lower()
      else:
        it.raise_()

  def _on_tab_clicked(self, idx: int) -> None:
    if self._rebuilding or self._suppress_layout_emit:
      return
    cur = active_screen_index(self._layout)
    if idx == cur:
      return
    self._layout.setdefault("panel", {})["active_screen"] = idx
    self._selected_path = ()
    self._rebuild(full=False)
    self.screen_changed.emit(idx)

  def _on_item_clicked(self, path: tuple[int, ...]) -> None:
    mods = QApplication.keyboardModifiers()
    if mods & Qt.KeyboardModifier.ControlModifier:
      if path in self._selected_paths:
        self._selected_paths.discard(path)
      else:
        self._selected_paths.add(path)
      self._selected_path = path if path in self._selected_paths else (
        next(iter(self._selected_paths)) if self._selected_paths else ()
      )
      for it in self._items:
        it.set_selected(it.path() in self._selected_paths)
      self.selection_changed.emit(list(self._selected_paths))
      if self._selected_path:
        self.widget_selected.emit(self._selected_path)
      return
    self.set_selected_path(path)
    self.widget_selected.emit(path)

  def _snap_item_geometry(self, path: tuple[int, ...], geom: QRect) -> QRect:
    if not path or len(path) != 2 or path[0] == CHROME_PATH_TAG:
      return geom
    sc_list = screens(self._layout)
    active = path[0]
    if active < 0 or active >= len(sc_list):
      return geom
    widgets = sc_list[active].get("widgets") or []
    idx = path[1]
    if idx < 0 or idx >= len(widgets):
      return geom
    scale = max(0.01, self._scale)
    dx = int(round(geom.x() / scale))
    dy = int(round(geom.y() / scale))
    dw = int(round(geom.width() / scale))
    dh = int(round(geom.height() / scale))
    panel = self._layout.get("panel") or {}
    design_w, _ = panel_design_size(panel)
    snapped = smart_snap_rect(
      dx,
      dy,
      dw,
      dh,
      other_rects_excluding(widgets, idx),
      threshold=8,
      design_w=design_w,
    )
    canvas = self._shell.canvas if self._shell else None
    if isinstance(canvas, InterfaceCanvas):
      canvas.set_snap_guides(snapped.guides, scale=scale)
    return QRect(
      int(snapped.x * scale),
      int(snapped.y * scale),
      geom.width(),
      geom.height(),
    )

  def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
    if event.modifiers() & Qt.KeyboardModifier.ControlModifier and self._device_emulation:
      delta = event.angleDelta().y()
      if delta == 0:
        super().wheelEvent(event)
        return
      if self._auto_fit_device:
        self._auto_fit_device = False
        panel = self._layout.get("panel", {})
        dw, dh = panel_design_size(panel)
        self._target_screen_px = max(240, int(dw * self._scale))
      step = 20 if delta > 0 else -20
      base = self._target_screen_px or DEFAULT_PHONE_SCREEN_PX
      nw = max(240, min(480, base + step))
      if nw != self._target_screen_px:
        self._target_screen_px = nw
        self._rebuild(full=True)
      event.accept()
      return
    super().wheelEvent(event)

  def keyPressEvent(self, event) -> None:  # noqa: N802
    key = event.key()
    mods = event.modifiers()
    step = 10 if mods & Qt.KeyboardModifier.ShiftModifier else 1
    if key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier:
      if mods & Qt.KeyboardModifier.ShiftModifier:
        self.redo_requested.emit()
      else:
        self.undo_requested.emit()
      event.accept()
      return
    if key == Qt.Key.Key_Y and mods & Qt.KeyboardModifier.ControlModifier:
      self.redo_requested.emit()
      event.accept()
      return
    if key == Qt.Key.Key_Delete and (self._selected_path or self._selected_paths):
      self.delete_selected.emit()
      event.accept()
      return
    if key == Qt.Key.Key_D and mods & Qt.KeyboardModifier.ControlModifier:
      self.duplicate_selected.emit()
      event.accept()
      return
    dx = dy = 0
    if key == Qt.Key.Key_Left:
      dx = -step
    elif key == Qt.Key.Key_Right:
      dx = step
    elif key == Qt.Key.Key_Up:
      dy = -step
    elif key == Qt.Key.Key_Down:
      dy = step
    if dx or dy:
      self.nudge_selected.emit(dx, dy)
      event.accept()
      return
    super().keyPressEvent(event)

  def _on_rect_changed(self, path: tuple[int, ...], x: int, y: int, w: int, h: int) -> None:
    if self._suppress_layout_emit:
      return
    canvas = self._shell.canvas if self._shell else None
    if isinstance(canvas, InterfaceCanvas):
      canvas.set_snap_guides([], scale=self._scale)
    from studio.services.screen_layout import resolve_widget
    from studio.services.widget_align import move_widgets_by, widgets_inside_bounds

    nx, ny, nw, nh = _snap_design(x), _snap_design(y), _snap_design(w), _snap_design(h)
    old = resolve_widget(self._layout, path)
    old_x = old_y = old_w = old_h = 0
    wtype = ""
    if old is not None:
      old_x = int(old.get("layout_x", 0))
      old_y = int(old.get("layout_y", 0))
      old_w = int(old.get("layout_w", 120))
      old_h = int(old.get("layout_h", 48))
      wtype = str(old.get("type", ""))
    self._suppress_rebuild = True
    set_widget_rect(self._layout, path, nx, ny, nw, nh)
    # 拖动分区时，原先落在框内的控件跟着平移（仅位移，不含对齐缩放）
    if (
      wtype == "section"
      and len(path) == 2
      and path[0] != CHROME_PATH_TAG
      and old is not None
    ):
      dx, dy = nx - old_x, ny - old_y
      if dx or dy:
        sc_list = screens(self._layout)
        si, wi = path[0], path[1]
        if 0 <= si < len(sc_list):
          widgets = sc_list[si].get("widgets") or []
          kids = widgets_inside_bounds(
            widgets, old_x, old_y, old_w, old_h, exclude_idx=wi
          )
          if kids:
            panel = self._layout.get("panel") or {}
            dw, _ = panel_design_size(panel)
            move_widgets_by(widgets, kids, dx, dy, design_w=dw)
    self._suppress_rebuild = False
    self.layout_changed.emit(clone_layout(self._layout))
    self.values_changed.emit()
