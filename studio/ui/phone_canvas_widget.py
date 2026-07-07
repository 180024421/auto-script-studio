"""720×1280 手机画布 — 全局标签页 + 可滚动界面 + 自由拖动缩放。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import (
  QFrame,
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

TITLE_DP = 48
TAB_BAR_DP = 44
CHROME_DP = 64
SNAP_GRID = 8
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


def _snap_design(v: int) -> int:
    g = SNAP_GRID
    return int(round(v / g) * g)


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
    self._spec = clone_widget(spec)
    wtype = spec.get("type", "")
    self._form_like = wtype in FORM_PREVIEW_TYPES
    self._label: QLabel | None = None
    self._drag_lightweight = False

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
    self._mount_preview(self._spec)
    self._relayout_content()
    self._update_style()

  def _mount_preview(self, spec: dict[str, Any]) -> None:
    wtype = spec.get("type", "")
    preview = None
    if self._interactive and wtype in INTERACTIVE_TYPES:
      preview = build_interactive_widget(spec, self._on_values_changed, scale=self._scale)
    elif wtype == "divider" or wtype in FORM_PREVIEW_TYPES:
      preview = build_design_preview(spec, scale=self._scale)
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

  def _update_style(self) -> None:
    if self._form_like:
      border = "#2563EB" if self._selected else "transparent"
      bg = "transparent"
      radius = 6
    else:
      border = "#2563EB" if self._selected else "transparent"
      bg = "transparent"
      radius = 8
    strip_bg = "rgba(37,99,235,0.12)" if self._interactive and not self._form_like else "transparent"
    self.setStyleSheet(
      f"QFrame#FreeDesignItem {{ background: {bg}; border: 1px solid {border}; border-radius: {radius}px; }}"
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
    else:
      from studio.services.free_layout import min_rect_for_type

      wtype = str(self._spec.get("type", ""))
      min_dw, min_dh = min_rect_for_type(wtype)
      min_sw = max(int(min_dw * self._scale), SNAP_GRID * 6)
      min_sh = max(int(min_dh * self._scale), SNAP_GRID * 4)
      g.setWidth(max(min_sw, self._start_geom.width() + delta.x()))
      g.setHeight(max(min_sh, self._start_geom.height() + delta.y()))
    self.setGeometry(self._clamp_geometry(g))
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
    self._mode = ""
    self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    super().mouseReleaseEvent(event)


class InterfaceCanvas(QWidget):
  """单个界面的可滚动内容区。"""

  context_menu_requested = Signal(object)

  def __init__(self, parent=None) -> None:
    super().__init__(parent)
    self.setObjectName("InterfaceCanvas")
    self._items: list[FreeDesignItem] = []
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


class PhoneCanvasWidget(QScrollArea):
  layout_changed = Signal(dict)
  widget_selected = Signal(tuple)
  screen_changed = Signal(int)
  values_changed = Signal()
  nudge_selected = Signal(int, int)
  delete_selected = Signal()
  duplicate_selected = Signal()
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
    self._items: list[FreeDesignItem] = []
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
    for it in self._items:
      it.set_selected(it.path() == path)

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
    new_scale = self._effective_scale(dw, dh)
    if abs(new_scale - self._shell.scale) >= 0.01:
      return True
    return False

  def _hint_reserve_px(self) -> int:
    return 0 if self._compact_preview else 56

  def _effective_scale(self, design_w: int, design_h: int) -> float:
    gutter = 20
    vw = max(200, self.viewport().width() - 48 - gutter)
    scale_w = vw / max(1, design_w)
    if not self._fit_viewport:
      return max(0.35, min(1.0, scale_w))
    vh = max(160, self.viewport().height() - self._hint_reserve_px() - 20)
    scale_h = vh / max(1, design_h)
    return max(0.2, min(1.0, scale_w, scale_h))

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
    self._items = []
    self._interface_canvas = None
    self._chrome_host = None
    self._shell = None

  def _build_shell(self) -> _PhoneShell:
    panel = self._layout.get("panel", {})
    dw, dh = panel_design_size(panel)
    self._scale = self._effective_scale(dw, dh)
    self._last_scale = self._scale
    sw = int(dw * self._scale)
    active = active_screen_index(self._layout)
    sc_list = screens(self._layout)

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)

    phone = QFrame()
    phone.setObjectName("PhoneFrame")
    phone.setFixedWidth(sw + 4)
    phone_lay = QVBoxLayout(phone)
    phone_lay.setContentsMargins(2, 2, 2, 2)
    phone_lay.setSpacing(0)

    inner = QWidget()
    inner.setObjectName("PhoneScreen")
    inner.setFixedWidth(sw)
    inner_lay = QVBoxLayout(inner)
    inner_lay.setContentsMargins(0, 0, 0, 0)
    inner_lay.setSpacing(0)

    title_h = int(TITLE_DP * self._scale)
    title = QLabel(panel.get("title", "脚本助手"))
    title.setFixedHeight(title_h)
    title.setStyleSheet(
      "background:#2563EB;color:white;font-weight:600;font-size:13px;"
    )
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    inner_lay.addWidget(title)

    tab_scroll, tab_buttons = _build_screen_tab_bar(
      sc_list, active, self._scale, self._on_tab_clicked
    )
    inner_lay.addWidget(tab_scroll)

    view_h = int((dh - TITLE_DP - TAB_BAR_DP - _chrome_dp(self._layout)) * self._scale)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFixedHeight(max(200, view_h))
    scroll.setStyleSheet("QScrollArea { border: none; background: #FFFFFF; }")

    canvas = InterfaceCanvas()
    canvas.context_menu_requested.connect(self.context_menu_requested.emit)
    scroll.setWidget(canvas)
    inner_lay.addWidget(scroll, 1)

    chrome_h = int(_chrome_dp(self._layout) * self._scale)
    chrome_host = QWidget()
    chrome_host.setFixedHeight(max(0, chrome_h))
    chrome_host.setVisible(chrome_h > 0)
    chrome_host.setStyleSheet("background:#F8FAFC;border-top:1px solid #E2E8F0;")
    chrome_host.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    chrome_host.customContextMenuRequested.connect(
      lambda pos, host=chrome_host: self.context_menu_requested.emit(host.mapToGlobal(pos))
    )
    inner_lay.addWidget(chrome_host)

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
    )

  def _hint_text(self, dw: int, dh: int) -> str:
    if is_host_display(self._layout.get("panel")):
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
    return base

  def _sync_shell_content(self) -> None:
    if self._shell is None:
      return
    shell = self._shell
    panel = self._layout.get("panel", {})
    dw, dh = shell.design_wh
    self._scale = shell.scale
    sw = int(dw * self._scale)
    active = active_screen_index(self._layout)
    sc_list = screens(self._layout)

    shell.title.setText(panel.get("title", "脚本助手"))
    title_h = int(TITLE_DP * self._scale)
    shell.title.setFixedHeight(title_h)
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
      min_canvas=0 if self._fit_viewport else 800,
    )
    view_h = int((dh - TITLE_DP - TAB_BAR_DP - _chrome_dp(self._layout)) * self._scale)
    shell.scroll.setFixedHeight(max(200, view_h))
    canvas_h = int(content_h_design * self._scale)
    shell.canvas.setFixedSize(sw, max(canvas_h, view_h))

    chrome_h = int(_chrome_dp(self._layout) * self._scale)
    shell.chrome_host.setFixedHeight(max(0, chrome_h))
    shell.chrome_host.setVisible(chrome_h > 0)
    phone_h = title_h + tab_h + shell.scroll.height() + chrome_h
    shell.inner.setFixedWidth(sw)
    shell.inner.setFixedHeight(phone_h)
    shell.phone.setFixedWidth(sw + 4)
    shell.phone.setFixedHeight(phone_h + 4)

    screen_widgets = sc_list[active].get("widgets") or [] if sc_list else []
    self._sync_widget_layer(shell.canvas, screen_widgets, active)
    self._sync_widget_layer(shell.chrome_host, chrome_widgets(self._layout), CHROME_PATH_TAG)

    if shell.hint is not None:
      shell.hint.setText(self._hint_text(dw, dh))
    hint_h = 0 if shell.hint is None else shell.hint.sizeHint().height() + 24
    total_h = phone_h + 4 + hint_h
    if self._fit_viewport:
      self._viewport.setMinimumHeight(0)
    else:
      self._viewport.setMinimumHeight(total_h)

  def _attach_shell_to_root(self) -> None:
    if self._shell is None:
      return
    shell = self._shell
    if self._fit_viewport:
      self._root.addWidget(shell.wrap, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
      if shell.hint is not None:
        self._root.addWidget(shell.hint, 0, Qt.AlignmentFlag.AlignHCenter)
    else:
      self._root.addWidget(shell.wrap, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
      if shell.hint is not None:
        self._root.addWidget(shell.hint, 0, Qt.AlignmentFlag.AlignHCenter)

  def _make_design_item(
    self,
    path: tuple[int, ...],
    spec: dict[str, Any],
    scale: float,
    parent: QWidget,
    screen_idx: int,
  ) -> FreeDesignItem:
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
    )
    item.rect_changed.connect(self._on_rect_changed)
    item.clicked.connect(self._on_item_clicked)
    item.set_selected(path == self._selected_path)
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
        if item.geometry() != geom:
          item.setGeometry(geom)
        item.set_selected(path == self._selected_path)
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
    self.set_selected_path(path)
    self.widget_selected.emit(path)

  def keyPressEvent(self, event) -> None:  # noqa: N802
    key = event.key()
    step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
    if key == Qt.Key.Key_Delete and self._selected_path:
      self.delete_selected.emit()
      event.accept()
      return
    if key == Qt.Key.Key_D and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
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
    self._suppress_rebuild = True
    set_widget_rect(
      self._layout,
      path,
      _snap_design(x),
      _snap_design(y),
      _snap_design(w),
      _snap_design(h),
    )
    self._suppress_rebuild = False
    self.layout_changed.emit(clone_layout(self._layout))
    self.values_changed.emit()
