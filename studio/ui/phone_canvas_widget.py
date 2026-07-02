"""720×1280 手机画布 — 全局标签页 + 可滚动界面 + 自由拖动缩放。"""

from __future__ import annotations

import json
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
  migrate_layout,
  path_for_chrome,
  path_for_screen,
  screens,
  set_widget_rect,
)
from studio.services.free_layout import panel_design_size

TITLE_DP = 48
TAB_BAR_DP = 44
CHROME_DP = 64
SNAP_GRID = 8
DRAG_THRESHOLD = 5

CHROME_ICONS: dict[str, str] = {
  "start_script": "▶",
  "stop_script": "■",
  "collapse": "▼",
  "tap": "⌖",
  "lua": "{}",
}


def _snap_design(v: int) -> int:
    g = SNAP_GRID
    return int(round(v / g) * g)


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
    self._on_values_changed = on_values_changed
    wtype = spec.get("type", "")
    self._form_like = wtype in FORM_PREVIEW_TYPES

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
    preview = None
    if interactive and wtype in INTERACTIVE_TYPES:
      preview = build_interactive_widget(spec, on_values_changed)
    elif wtype in FORM_PREVIEW_TYPES:
      preview = build_design_preview(spec)
    if preview is not None:
      lay = QVBoxLayout(self._content_host)
      lay.setContentsMargins(0, 0, 0, 0)
      lay.setSpacing(0)
      preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
      lay.addWidget(preview, 1)
      self._label = None
    else:
      self._label = QLabel(title_line if icon_only and icon else display, self._content_host)
      self._label.setObjectName("FreeDesignTitle")
      self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
      self._label.setWordWrap(not (icon_only and icon))
      if icon_only and icon:
        self._label.setStyleSheet("font-size: 22px; font-weight: 600;")
      self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    self._relayout_content()
    self._update_style()

  def path(self) -> tuple[int, ...]:
    return self._path

  def set_selected(self, on: bool) -> None:
    self._selected = on
    self._update_style()

  def _relayout_content(self) -> None:
    strip_h = 0
    if self._interactive and not self._form_like:
      strip_h = self.DRAG_STRIP
      self._drag_strip.setGeometry(0, 0, self.width(), strip_h)
      self._drag_strip.show()
    elif not self._form_like:
      self._drag_strip.setGeometry(0, 0, self.width(), 0)
    self._content_host.setGeometry(0, strip_h, self.width(), max(20, self.height() - strip_h))
    if self._label is not None:
      self._label.setGeometry(4, 4, max(40, self._content_host.width() - 8), max(24, self._content_host.height() - 8))

  def resizeEvent(self, event) -> None:  # noqa: N802
    super().resizeEvent(event)
    self._relayout_content()

  def _update_style(self) -> None:
    if self._form_like:
      border = "#2563EB" if self._selected else "#E2E8F0"
      bg = "rgba(239,246,255,0.35)" if self._selected else "transparent"
      radius = 6
    else:
      border = "#2563EB" if self._selected else "#94A3B8"
      bg = "rgba(239,246,255,0.96)" if self._selected else "rgba(248,250,252,0.96)"
      radius = 8
    strip_bg = "rgba(37,99,235,0.12)" if self._interactive and not self._form_like else "transparent"
    self.setStyleSheet(
      f"QFrame#FreeDesignItem {{ background: {bg}; border: 1px solid {border}; border-radius: {radius}px; }}"
      f"QLabel#FreeDesignDragStrip {{ background: {strip_bg}; color: #1E293B; font-size: 10px; }}"
      "QLabel#FreeDesignTitle { color: #1E293B; font-size: 11px; background: transparent; }"
    )

  def _in_grip(self, pos: QPoint) -> bool:
    return pos.x() >= self.width() - self.GRIP and pos.y() >= self.height() - self.GRIP

  def _in_drag_strip(self, pos: QPoint) -> bool:
    if not self._interactive:
      return True
    if self._form_like:
      return pos.x() <= self.FORM_DRAG_GUTTER or self._in_grip(pos)
    return pos.y() <= self.DRAG_STRIP

  def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
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
      self.grabMouse()
    if not self._mode:
      return super().mouseMoveEvent(event)
    delta = event.globalPosition().toPoint() - self._press_global
    g = QRect(self._start_geom)
    if self._mode == "move":
      g.translate(delta)
    else:
      g.setWidth(max(48, self._start_geom.width() + delta.x()))
      g.setHeight(max(28, self._start_geom.height() + delta.y()))
    self.setGeometry(g)
    event.accept()

  def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if self._mode and event.button() == Qt.MouseButton.LeftButton:
      if self.mouseGrabber() is self:
        self.releaseMouse()
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
    self._suppress_rebuild = False
    self._rebuilding = False
    self._suppress_layout_emit = False
    self._interactive_preview = False
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

  def interactive_preview(self) -> bool:
    return self._interactive_preview

  def set_layout(self, layout: dict[str, Any], *, selected_path: tuple[int, ...] | None = None) -> None:
    old = PanelState.all()
    self._suppress_layout_emit = True
    try:
      self._layout = migrate_layout(json.loads(json.dumps(layout or {})))
      PanelState.seed_from_layout(self._layout)
      if old:
        merged = dict(PanelState.all())
        merged.update({k: v for k, v in old.items() if k in merged})
        PanelState.reset(merged)
      if selected_path is not None:
        self._selected_path = selected_path
      self._rebuild(full=True)
      self.values_changed.emit()
    finally:
      self._suppress_layout_emit = False

  def set_selected_path(self, path: tuple[int, ...]) -> None:
    self._selected_path = path
    for it in self._items:
      it.set_selected(it.path() == path)

  def set_active_screen(self, idx: int) -> None:
    self._layout.setdefault("panel", {})["active_screen"] = idx
    self._rebuild(full=True)
    self.screen_changed.emit(idx)

  def _effective_scale(self, design_w: int) -> float:
    # 预留滚动条槽位，避免滚动条显隐导致 viewport 宽度来回变化
    gutter = 20
    available = max(280, self.viewport().width() - 48 - gutter)
    return max(0.35, min(1.0, available / max(1, design_w)))

  def resizeEvent(self, event) -> None:  # noqa: N802
    super().resizeEvent(event)
    if not self._layout or self._suppress_rebuild or self._rebuilding:
      return
    panel = self._layout.get("panel", {})
    dw, _ = panel_design_size(panel)
    new_scale = self._effective_scale(dw)
    if self._last_scale > 0 and abs(new_scale - self._last_scale) < 0.01:
      return
    self._rebuild(full=True)

  def _rebuild(self, *, full: bool = True) -> None:
    if self._suppress_rebuild or self._rebuilding:
      return
    self._rebuilding = True
    self._viewport.setUpdatesEnabled(False)
    try:
      while self._root.count():
        item = self._root.takeAt(0)
        w = item.widget()
        if w is not None:
          w.setParent(None)
          w.deleteLater()
      self._items = []
      self._interface_canvas = None
      self._chrome_host = None

      panel = self._layout.get("panel", {})
      dw, dh = panel_design_size(panel)
      self._scale = self._effective_scale(dw)
      self._last_scale = self._scale
      sw = int(dw * self._scale)
      active = active_screen_index(self._layout)
      sc_list = screens(self._layout)

      row = QHBoxLayout()
      row.setContentsMargins(0, 0, 0, 0)
      row.addStretch(1)

      phone = QFrame()
      phone.setObjectName("PhoneFrame")
      phone.setFixedWidth(sw + 16)
      phone_lay = QVBoxLayout(phone)
      phone_lay.setContentsMargins(8, 8, 8, 8)
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
        "background:#2563EB;color:white;padding-left:10px;font-weight:600;font-size:13px;"
      )
      title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
      inner_lay.addWidget(title)

      tab_h = int(TAB_BAR_DP * self._scale)
      tab_bar = QWidget()
      tab_bar.setFixedHeight(tab_h)
      tab_bar.setStyleSheet("background:#F1F5F9;border-bottom:1px solid #CBD5E1;")
      tab_lay = QHBoxLayout(tab_bar)
      tab_lay.setContentsMargins(4, 4, 4, 4)
      tab_lay.setSpacing(4)
      for i, sc in enumerate(sc_list):
        tb = QPushButton(sc.get("title", f"界面{i + 1}"))
        tb.setCheckable(True)
        tb.blockSignals(True)
        tb.setChecked(i == active)
        tb.blockSignals(False)
        tb.setMinimumHeight(int(32 * self._scale))
        tb.clicked.connect(lambda _c=False, idx=i: self._on_tab_clicked(idx))
        tab_lay.addWidget(tb)
      tab_lay.addStretch()
      inner_lay.addWidget(tab_bar)

      content_h_design = content_height(self._layout, active)
      view_h = int((dh - TITLE_DP - TAB_BAR_DP - CHROME_DP) * self._scale)
      scroll = QScrollArea()
      scroll.setWidgetResizable(True)
      scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
      scroll.setFixedHeight(max(200, view_h))
      scroll.setStyleSheet("QScrollArea { border: none; background: #FFFFFF; }")

      canvas = InterfaceCanvas()
      canvas_h = int(content_h_design * self._scale)
      canvas.setFixedSize(sw, max(canvas_h, view_h))
      self._interface_canvas = canvas
      canvas.context_menu_requested.connect(self.context_menu_requested.emit)
      scroll.setWidget(canvas)
      inner_lay.addWidget(scroll, 1)

      chrome_h = int(CHROME_DP * self._scale)
      chrome_host = QWidget()
      chrome_host.setFixedHeight(chrome_h)
      chrome_host.setStyleSheet("background:#F8FAFC;border-top:1px solid #E2E8F0;")
      chrome_host.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
      chrome_host.customContextMenuRequested.connect(
        lambda pos, host=chrome_host: self.context_menu_requested.emit(host.mapToGlobal(pos))
      )
      self._chrome_host = chrome_host
      inner_lay.addWidget(chrome_host)

      phone_h = title_h + tab_h + scroll.height() + chrome_h
      inner.setFixedHeight(phone_h)
      phone.setFixedHeight(phone_h + 16)

      self._place_widgets(
        canvas,
        sc_list[active].get("widgets") or [] if sc_list else [],
        active,
        self._scale,
      )
      self._place_widgets(chrome_host, chrome_widgets(self._layout), CHROME_PATH_TAG, self._scale)

      phone_lay.addWidget(inner)
      row.addWidget(phone)
      row.addStretch(1)
      wrap = QWidget()
      wrap.setLayout(row)
      wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

      hint_text = (
        f"设计 {dw}×{dh}  ·  点击标签切换界面  ·  拖动移动控件  ·  右下角缩放  ·  界面可上下滚动"
      )
      if self._interactive_preview:
        hint_text += "  ·  交互预览：顶部色条拖动，控件区内可操作"
      hint = QLabel(hint_text)
      hint.setObjectName("HintLabel")
      hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
      hint.setWordWrap(True)

      self._root.addWidget(wrap, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
      self._root.addWidget(hint, 0, Qt.AlignmentFlag.AlignHCenter)
      self._root.addStretch(1)

      total_h = phone_h + 16 + hint.sizeHint().height() + 24
      self._viewport.setMinimumHeight(total_h)
    finally:
      self._viewport.setUpdatesEnabled(True)
      self._rebuilding = False

  def _place_widgets(
    self,
    parent: QWidget,
    widgets: list,
    screen_idx: int,
    scale: float,
  ) -> None:
    for idx, spec in enumerate(widgets):
      if screen_idx == CHROME_PATH_TAG:
        path = path_for_chrome(idx)
      else:
        path = path_for_screen(screen_idx, idx)
      x = int(spec.get("layout_x", 24) * scale)
      y = int(spec.get("layout_y", 40) * scale)
      w = int(spec.get("layout_w", 200) * scale)
      h = int(spec.get("layout_h", 48) * scale)
      item = FreeDesignItem(
        path,
        spec,
        scale,
        parent,
        interactive=self._interactive_preview,
        on_values_changed=self.values_changed.emit,
        icon_only=screen_idx == CHROME_PATH_TAG and spec.get("type") in CHROME_ICONS,
      )
      item.setGeometry(x, y, w, h)
      item.rect_changed.connect(self._on_rect_changed)
      item.clicked.connect(self._on_item_clicked)
      item.set_selected(path == self._selected_path)
      item.show()
      item.raise_()
      self._items.append(item)

  def _on_tab_clicked(self, idx: int) -> None:
    if self._rebuilding or self._suppress_layout_emit:
      return
    cur = active_screen_index(self._layout)
    if idx == cur:
      return
    self._layout.setdefault("panel", {})["active_screen"] = idx
    self._selected_path = ()
    self._rebuild(full=True)
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
      max(SNAP_GRID * 6, _snap_design(w)),
      max(SNAP_GRID * 4, _snap_design(h)),
    )
    self._suppress_rebuild = False
    self.layout_changed.emit(json.loads(json.dumps(self._layout)))
    self.values_changed.emit()
