"""ADB 抓抓：截图、取色、存模板、识字/YOLO 测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from studio.services.adb_service import AdbService
from studio.services import lua_snippets
from studio.services import vision_pc


class ScreenshotLabel(QLabel):
  clicked = Signal(int, int)
  selected = Signal(int, int, int, int)

  def __init__(self) -> None:
    super().__init__()
    self.setAlignment(Qt.AlignCenter)
    self.setMinimumHeight(360)
    self.setStyleSheet("background:#222; color:#ccc;")
    self._origin: Optional[np.ndarray] = None
    self._scale = 1.0
    self._drag_start: Optional[QPoint] = None
    self._drag_end: Optional[QPoint] = None
    self._selection: Optional[Tuple[int, int, int, int]] = None

  def set_image(self, bgr: np.ndarray) -> None:
    self._origin = bgr.copy()
    self._selection = None
    self._drag_start = None
    self._drag_end = None
    self._refresh()

  def image(self) -> Optional[np.ndarray]:
    return None if self._origin is None else self._origin.copy()

  def selection(self) -> Optional[Tuple[int, int, int, int]]:
    return self._selection

  def _refresh(self) -> None:
    if self._origin is None:
      self.setText("点击「ADB 截图」获取画面")
      return
    rgb = cv2.cvtColor(self._origin, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    pix = QPixmap.fromImage(qimg.copy())
    max_w = max(400, self.width() - 20)
    if pix.width() > max_w:
      self._scale = max_w / pix.width()
      pix = pix.scaledToWidth(int(max_w), Qt.SmoothTransformation)
    else:
      self._scale = 1.0
    if self._selection:
      painter = QPainter(pix)
      pen = QPen(Qt.red, 2)
      painter.setPen(pen)
      x, y, rw, rh = self._selection
      painter.drawRect(
        int(x * self._scale),
        int(y * self._scale),
        int(rw * self._scale),
        int(rh * self._scale),
      )
      painter.end()
    self.setPixmap(pix)

  def resizeEvent(self, event) -> None:  # noqa: N802
    super().resizeEvent(event)
    self._refresh()

  def _to_image_xy(self, pos: QPoint) -> Tuple[int, int]:
    if self._origin is None or self.pixmap() is None:
      return 0, 0
    px = self.pixmap()
    offset_x = (self.width() - px.width()) // 2
    offset_y = (self.height() - px.height()) // 2
    x = int((pos.x() - offset_x) / self._scale)
    y = int((pos.y() - offset_y) / self._scale)
    x = max(0, min(self._origin.shape[1] - 1, x))
    y = max(0, min(self._origin.shape[0] - 1, y))
    return x, y

  def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if self._origin is None:
      return
    if event.button() == Qt.LeftButton:
      self._drag_start = event.position().toPoint()
      self._drag_end = self._drag_start
    super().mousePressEvent(event)

  def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if self._origin is None:
      return
    x, y = self._to_image_xy(event.position().toPoint())
    self.clicked.emit(x, y)
    if self._drag_start is not None:
      self._drag_end = event.position().toPoint()
      x1, y1 = self._to_image_xy(self._drag_start)
      x2, y2 = x, y
      self._selection = (min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
      self._refresh()
    super().mouseMoveEvent(event)

  def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
    if self._selection and self._selection[2] > 2 and self._selection[3] > 2:
      self.selected.emit(*self._selection)
    self._drag_start = None
    super().mouseReleaseEvent(event)


class GrabWidget(QWidget):
  log_message = Signal(str)
  insert_lua = Signal(str)
  insert_yaml = insert_lua

  def __init__(self, project_dir_getter) -> None:
    super().__init__()
    self._project_dir_getter = project_dir_getter
    self._adb = AdbService()
    self._screen: Optional[np.ndarray] = None
    self._last_xy: Tuple[int, int] = (0, 0)

    layout = QVBoxLayout(self)
    row = QHBoxLayout()
    self.device_combo = QComboBox()
    row.addWidget(QLabel("设备"))
    row.addWidget(self.device_combo, 1)
    refresh_btn = QPushButton("刷新设备")
    refresh_btn.clicked.connect(self.refresh_devices)
    row.addWidget(refresh_btn)
    shot_btn = QPushButton("ADB 截图")
    shot_btn.clicked.connect(self.capture)
    row.addWidget(shot_btn)
    layout.addLayout(row)

    self.canvas = ScreenshotLabel()
    self.canvas.clicked.connect(self._on_pixel)
    self.canvas.selected.connect(self._on_selected)
    layout.addWidget(self.canvas, 1)

    self.info = QLabel("BGR: - | 选区: -")
    layout.addWidget(self.info)

    btn_row = QHBoxLayout()
    for text, slot in [
      ("复制BGR", self.copy_bgr),
      ("插入找色 Lua", self.insert_color_lua),
      ("插入找图 Lua", self.insert_template_lua),
      ("插入识字 Lua", self.insert_text_lua),
      ("复制 Lua 代码", self.copy_lua),
      ("ADB点击测试", self.adb_tap_test),
      ("保存截图", self.save_screenshot),
      ("保存选区为模板", self.save_template),
      ("测试找色", self.test_color),
      ("测试找图", self.test_template),
      ("测试识字", self.test_ocr),
      ("测试 YOLO", self.test_yolo),
    ]:
      b = QPushButton(text)
      b.clicked.connect(slot)
      btn_row.addWidget(b)
    layout.addLayout(btn_row)

    self._picked_bgr: Optional[Tuple[int, int, int]] = None
    self._last_lua_snippet: str = ""
    self.refresh_devices()

  def refresh_devices(self) -> None:
    self.device_combo.clear()
    try:
      devs = self._adb.list_devices()
    except Exception as exc:
      self.log_message.emit(f"ADB 错误: {exc}")
      return
    if not devs:
      self.device_combo.addItem("(无设备)", "")
      return
    emu_idx = 0
    for i, d in enumerate(devs):
      self.device_combo.addItem(d.label, d.serial)
      if d.is_emulator and emu_idx == 0:
        emu_idx = i
    self.device_combo.setCurrentIndex(emu_idx)

  def _serial(self) -> str:
    return str(self.device_combo.currentData() or "")

  def capture(self) -> None:
    try:
      png = self._adb.capture_png(self._serial() or None)
      self._screen = vision_pc.decode_png(png)
      self.canvas.set_image(self._screen)
      self.log_message.emit(f"截图成功 {self._screen.shape[1]}x{self._screen.shape[0]}")
    except Exception as exc:
      QMessageBox.warning(self, "截图失败", str(exc))

  def _on_pixel(self, x: int, y: int) -> None:
    if self._screen is None:
      return
    self._last_xy = (x, y)
    b, g, r = [int(v) for v in self._screen[y, x]]
    self._picked_bgr = (b, g, r)
    sel = self.canvas.selection()
    sel_txt = str(sel) if sel else "-"
    self.info.setText(f"BGR: [{b}, {g}, {r}] | 选区: {sel_txt}")

  def _on_selected(self, x: int, y: int, w: int, h: int) -> None:
    self.info.setText(self.info.text().split("|")[0] + f" | 选区: ({x},{y},{w},{h})")

  def copy_bgr(self) -> None:
    if self._picked_bgr is None:
      QMessageBox.warning(self, "提示", "请先截图并移动鼠标取色")
      return
    b, g, r = self._picked_bgr
    QGuiApplication.clipboard().setText(f"[{b}, {g}, {r}]")
    self.log_message.emit(f"已复制 BGR: [{b}, {g}, {r}]")

  def _emit_lua(self, snippet: str, label: str) -> None:
    self._last_lua_snippet = snippet.strip()
    self.insert_lua.emit(self._last_lua_snippet)
    self.log_message.emit(label)

  def copy_lua(self) -> None:
    if not self._last_lua_snippet:
      QMessageBox.warning(self, "提示", "请先生成或插入一段 Lua 代码")
      return
    QGuiApplication.clipboard().setText(self._last_lua_snippet)
    self.log_message.emit("已复制 Lua 代码到剪贴板")

  def insert_color_lua(self) -> None:
    if self._picked_bgr is None:
      QMessageBox.warning(self, "提示", "请先截图并移动鼠标取色")
      return
    roi = self.canvas.selection()
    snippet = lua_snippets.find_color(self._picked_bgr, roi=roi)
    self._emit_lua(snippet, "已生成找色 Lua 片段")

  def insert_template_lua(self) -> None:
    project = self._project_dir_getter()
    if not project:
      QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
      return
    imgs = sorted((Path(project) / "image").glob("*.png"))
    if not imgs:
      QMessageBox.warning(self, "提示", "请先保存模板到 image/ 目录")
      return
    rel = f"image/{imgs[-1].name}"
    roi = self.canvas.selection()
    snippet = lua_snippets.find_image(rel, roi=roi)
    self._emit_lua(snippet, f"已生成找图 Lua 片段: {rel}")

  def insert_text_lua(self) -> None:
    target, ok = QInputDialog.getText(self, "识字目标", "要查找的文字（如：确定）:")
    if not ok or not target.strip():
      return
    snippet = lua_snippets.find_text(target.strip())
    self._emit_lua(snippet, f"已生成识字 Lua: {target.strip()}")

  def adb_tap_test(self) -> None:
    x, y = self._last_xy
    try:
      self._adb.tap(self._serial() or None, x, y)
      self.log_message.emit(f"ADB 点击 ({x}, {y})")
    except Exception as exc:
      QMessageBox.warning(self, "ADB 点击", str(exc))

  def save_screenshot(self) -> None:
    project = self._project_dir_getter()
    if not project or self._screen is None:
      QMessageBox.warning(self, "提示", "请先打开工程并截图")
      return
    img_dir = Path(project) / "image"
    img_dir.mkdir(parents=True, exist_ok=True)
    name = f"screen_{len(list(img_dir.glob('*.png')))}.png"
    out = img_dir / name
    cv2.imwrite(str(out), self._screen)
    self.log_message.emit(f"已保存截图: image/{name}")

  def save_template(self) -> None:
    project = self._project_dir_getter()
    if not project:
      QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
      return
    sel = self.canvas.selection()
    if self._screen is None or not sel or sel[2] < 2 or sel[3] < 2:
      QMessageBox.warning(self, "提示", "请先截图并框选模板区域")
      return
    default = f"tpl_{len(list((Path(project) / 'image').glob('*.png')))}"
    name, ok = QInputDialog.getText(self, "模板名称", "文件名（不含扩展名）:", text=default)
    if not ok or not name.strip():
      return
    name = name.strip()
    if not name.lower().endswith(".png"):
      name += ".png"
    x, y, w, h = sel
    crop = self._screen[y : y + h, x : x + w]
    img_dir = Path(project) / "image"
    img_dir.mkdir(parents=True, exist_ok=True)
    out = img_dir / name
    cv2.imwrite(str(out), crop)
    self.log_message.emit(f"已保存模板: image/{name}")
    QMessageBox.information(self, "完成", f"已保存到 image/{name}")

  def test_color(self) -> None:
    if self._screen is None or self._picked_bgr is None:
      QMessageBox.warning(self, "提示", "请先截图并移动鼠标取色")
      return
    pt = vision_pc.find_color(self._screen, self._picked_bgr, tol=15, roi=self.canvas.selection())
    if pt:
      self.log_message.emit(f"找色命中: {pt}")
    else:
      self.log_message.emit("找色未命中")

  def test_template(self) -> None:
    project = self._project_dir_getter()
    if not project or self._screen is None:
      QMessageBox.warning(self, "提示", "请先打开工程并截图")
      return
    imgs = sorted((Path(project) / "image").glob("*.png"))
    if not imgs:
      QMessageBox.warning(self, "提示", "工程 image/ 下没有模板图")
      return
    tpl = cv2.imread(str(imgs[-1]))
    if tpl is None:
      return
    m = vision_pc.match_template(self._screen, tpl, threshold=0.85, roi=self.canvas.selection())
    if m:
      self.log_message.emit(f"找图命中 {imgs[-1].name} score={m.score:.3f} @ ({m.center_x},{m.center_y})")
    else:
      self.log_message.emit(f"找图未命中: {imgs[-1].name}")

  def test_ocr(self) -> None:
    if self._screen is None:
      return
    try:
      hits = vision_pc.recognize_text(self._screen, roi=self.canvas.selection())
      self.log_message.emit(f"识字 {len(hits)} 条")
      for h in hits[:15]:
        self.log_message.emit(f"  [{h.confidence:.2f}] {h.text} @ ({h.center_x},{h.center_y})")
    except Exception as exc:
      QMessageBox.warning(self, "识字", str(exc))

  def test_yolo(self) -> None:
    project = self._project_dir_getter()
    if not project or self._screen is None:
      return
    models = list(Path(project).glob("models/**/*.pt")) + list(Path(project).glob("models/**/*.onnx"))
    if not models:
      QMessageBox.warning(self, "提示", "工程 models/ 下没有 .pt 或 .onnx 模型")
      return
    try:
      dets = vision_pc.yolo_detect(
        self._screen,
        str(models[0]),
        conf=0.35,
        roi=self.canvas.selection(),
      )
      self.log_message.emit(f"YOLO {models[0].name} 检出 {len(dets)} 个")
      for d in dets[:10]:
        self.log_message.emit(
          f"  {d['class_name']} {d['confidence']:.2f} @ ({d['center_x']},{d['center_y']})"
        )
    except Exception as exc:
      QMessageBox.warning(self, "YOLO", str(exc))
