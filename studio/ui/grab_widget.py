"""ADB 抓抓：截图、取色、存模板、识字/YOLO 测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from studio.ui.app_theme import set_button_role
from studio.ui.layout_preview_widget import LayoutPreviewWidget
from studio.ui.page_shell import (
    card_frame,
    hint_label,
    main_column,
    page_root,
    section_title,
    side_column,
    three_columns,
    tool_button_row,
)
from studio.services.adb_service import AdbService
from studio.services import lua_snippets
from studio.services import vision_pc
from studio.services.layout_defaults import load_layout
from studio.services.layout_preview import paint_layout_overlay
from studio.services.canvas_overlay import paint_crosshair, paint_ocr_hits


class ScreenshotLabel(QLabel):
    clicked = Signal(int, int)
    selected = Signal(int, int, int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ScreenshotCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._origin: Optional[np.ndarray] = None
        self._scale = 1.0
        self._drag_start: Optional[QPoint] = None
        self._drag_end: Optional[QPoint] = None
        self._selection: Optional[Tuple[int, int, int, int]] = None
        self._layout: Optional[dict[str, Any]] = None
        self._show_panel_overlay = False
        self._ocr_hits: list[Any] = []
        self._highlight_xy: Optional[Tuple[int, int]] = None

    def set_highlight_xy(self, xy: Optional[Tuple[int, int]]) -> None:
        self._highlight_xy = xy
        self._refresh()

    def set_ocr_hits(self, hits: list[Any]) -> None:
        self._ocr_hits = hits or []
        self._refresh()

    def set_layout_overlay(self, layout: Optional[dict[str, Any]], enabled: bool = True) -> None:
        self._layout = layout
        self._show_panel_overlay = enabled and layout is not None and layout.get("enabled", True)
        self._refresh()

    def show_panel_overlay(self) -> bool:
        return self._show_panel_overlay

    def set_image(self, bgr: np.ndarray) -> None:
        self._origin = bgr.copy()
        self._selection = None
        self._drag_start = None
        self._drag_end = None
        self._ocr_hits = []
        self._refresh()

    def image(self) -> Optional[np.ndarray]:
        return None if self._origin is None else self._origin.copy()

    def selection(self) -> Optional[Tuple[int, int, int, int]]:
        return self._selection

    def _refresh(self) -> None:
        if self._origin is None:
            self.setText("点击左侧「ADB 截图」获取画面")
            self.setPixmap(QPixmap())
            return
        rgb = cv2.cvtColor(self._origin, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg.copy())

        max_w = max(280, self.width() - 24)
        max_h = max(240, self.height() - 24)
        scale = 1.0
        if pix.width() > max_w:
            scale = min(scale, max_w / pix.width())
        if pix.height() > max_h:
            scale = min(scale, max_h / pix.height())
        self._scale = scale
        if scale < 1.0:
            pix = pix.scaled(
                int(pix.width() * scale),
                int(pix.height() * scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._selection:
            pen = QPen(Qt.GlobalColor.red, 2)
            painter.setPen(pen)
            x, y, rw, rh = self._selection
            painter.drawRect(
                int(x * self._scale),
                int(y * self._scale),
                int(rw * self._scale),
                int(rh * self._scale),
            )
        if self._ocr_hits:
            paint_ocr_hits(painter, self._ocr_hits, self._scale)
        if self._highlight_xy:
            paint_crosshair(painter, self._highlight_xy[0], self._highlight_xy[1], self._scale)
        if self._show_panel_overlay and self._layout and self._origin is not None:
            ih, iw = self._origin.shape[:2]
            paint_layout_overlay(painter, self._layout, iw, ih, self._scale)
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
        if event.button() == Qt.MouseButton.LeftButton:
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
    panel_position_picked = Signal(int, int)
    button_coords_picked = Signal(int, int, str)

    def __init__(self, project_dir_getter) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self._adb = AdbService()
        self._screen: Optional[np.ndarray] = None
        self._last_xy: Tuple[int, int] = (0, 0)

        root = page_root(self)
        root.addWidget(
            hint_label(
                "左：设备与工具 · 中：截图主区（可叠加面板） · 右：浮动面板预览（与浮动面板页同步）"
            )
        )

        left, left_lay = side_column(240, 300)
        left_lay.addWidget(section_title("设备"))
        dev_row = QHBoxLayout()
        self.device_combo = QComboBox()
        dev_row.addWidget(self.device_combo, 1)
        refresh_btn = QPushButton("刷新")
        set_button_role(refresh_btn, "ghost")
        refresh_btn.clicked.connect(self.refresh_devices)
        dev_row.addWidget(refresh_btn)
        left_lay.addLayout(dev_row)

        shot_btn = QPushButton("ADB 截图")
        set_button_role(shot_btn, "primary")
        shot_btn.clicked.connect(self.capture)
        left_lay.addWidget(shot_btn)

        self.overlay_cb = QCheckBox("截图叠加面板")
        self.overlay_cb.setChecked(True)
        self.overlay_cb.toggled.connect(self._on_overlay_toggled)
        left_lay.addWidget(self.overlay_cb)
        self.side_preview_cb = QCheckBox("显示右侧预览")
        self.side_preview_cb.setChecked(True)
        self.side_preview_cb.toggled.connect(self._on_side_preview_toggled)
        left_lay.addWidget(self.side_preview_cb)

        left_lay.addWidget(section_title("取点"))
        for text, slot in [
            ("面板位置", self._toggle_panel_pick),
            ("点击坐标", lambda: self._toggle_pick("tap")),
            ("滑动起点", lambda: self._toggle_pick("swipe1")),
            ("滑动终点", lambda: self._toggle_pick("swipe2")),
        ]:
            b = QPushButton(text)
            set_button_role(b, "ghost")
            b.clicked.connect(slot)
            left_lay.addWidget(b)
        self.pick_panel_btn = QPushButton()
        self.pick_panel_btn.hide()
        self.pick_tap_btn = QPushButton()
        self.pick_tap_btn.hide()
        self.pick_swipe1_btn = QPushButton()
        self.pick_swipe1_btn.hide()
        self.pick_swipe2_btn = QPushButton()
        self.pick_swipe2_btn.hide()

        left_lay.addWidget(section_title("插入 Lua"))
        tool_button_row(
            left_lay,
            [
                ("点击", self.insert_tap_lua, "accent"),
                ("找色", self.insert_color_lua, "ghost"),
                ("找图", self.insert_template_lua, "ghost"),
                ("识字", self.insert_text_lua, "ghost"),
                ("命中", self.insert_ocr_hit_lua, "ghost"),
                ("复制", self.copy_lua, "ghost"),
            ],
            columns=2,
        )

        left_lay.addWidget(section_title("测试"))
        tool_button_row(
            left_lay,
            [
                ("复制BGR", self.copy_bgr, "ghost"),
                ("ADB点", self.adb_tap_test, "ghost"),
                ("存截图", self.save_screenshot, "ghost"),
                ("存模板", self.save_template, "ghost"),
                ("找色", self.test_color, "ghost"),
                ("找图", self.test_template, "ghost"),
                ("识字", self.test_ocr, "ghost"),
                ("YOLO", self.test_yolo, "ghost"),
            ],
            columns=2,
        )
        left_lay.addStretch()

        center, center_lay = main_column()
        center_lay.addWidget(section_title("截图"))
        self.info = QLabel("坐标: —  |  BGR: —  |  选区: —")
        self.info.setObjectName("InfoBar")
        self.info.setWordWrap(True)
        center_lay.addWidget(self.info)

        canvas_wrap = QFrame()
        canvas_wrap.setObjectName("CanvasWrap")
        canvas_lay = QVBoxLayout(canvas_wrap)
        canvas_lay.setContentsMargins(0, 0, 0, 0)
        self.canvas = ScreenshotLabel()
        self.canvas.clicked.connect(self._on_pixel)
        self.canvas.selected.connect(self._on_selected)
        canvas_lay.addWidget(self.canvas, 1, Qt.AlignmentFlag.AlignCenter)
        center_lay.addWidget(canvas_wrap, 1)

        right, right_lay = side_column(280, None)
        right_lay.addWidget(section_title("面板预览"))
        right_lay.addWidget(
            hint_label("居中显示 APK 浮窗效果；填表值与浮动面板页、Lua 运行共享")
        )
        self.panel_preview = LayoutPreviewWidget()
        self.panel_preview.setMinimumHeight(360)
        self.panel_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_lay.addWidget(self.panel_preview, 1)

        root.addLayout(three_columns(left, center, right), 1)

        self._picked_bgr: Optional[Tuple[int, int, int]] = None
        self._last_lua_snippet: str = ""
        self._layout_cache: Optional[dict[str, Any]] = None
        self._pick_panel_pos = False
        self._pick_mode: str = ""
        self.refresh_devices()

    def _toggle_panel_pick(self) -> None:
        self._on_pick_panel_toggled(not self._pick_panel_pos)

    def _toggle_pick(self, mode: str) -> None:
        self._on_pick_mode_toggled(mode, self._pick_mode != mode)

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

    def _load_layout(self) -> Optional[dict[str, Any]]:
        project = self._project_dir_getter()
        if not project:
            return None
        try:
            return load_layout(project)
        except Exception:
            return None

    def refresh_layout_overlay(self, layout: Optional[dict[str, Any]] = None) -> None:
        if layout is not None:
            self._layout_cache = layout
        elif self._layout_cache is None:
            self._layout_cache = self._load_layout()
        self.canvas.set_layout_overlay(
            self._layout_cache,
            enabled=self.overlay_cb.isChecked(),
        )

    def _on_overlay_toggled(self, checked: bool) -> None:
        self.refresh_layout_overlay()
        if checked:
            self.log_message.emit("已开启浮动面板叠加预览")

    def _on_side_preview_toggled(self, checked: bool) -> None:
        self.panel_preview.setVisible(checked)
        if checked and self._layout_cache:
            self.panel_preview.set_layout(self._layout_cache)

    def refresh_panel_preview(self, layout: Optional[dict[str, Any]] = None) -> None:
        if layout is not None:
            self._layout_cache = layout
        if self._layout_cache and self.side_preview_cb.isChecked():
            self.panel_preview.set_layout(self._layout_cache)

    def _clear_pick_modes(self) -> None:
        self._pick_panel_pos = False
        self._pick_mode = ""

    def _on_pick_panel_toggled(self, checked: bool) -> None:
        if checked:
            self._clear_pick_modes()
            self._pick_panel_pos = True
            self.log_message.emit("点击截图设置面板左上角 (start_x, start_y)")
        else:
            self._pick_panel_pos = False

    def _on_pick_mode_toggled(self, mode: str, checked: bool) -> None:
        if checked:
            self._clear_pick_modes()
            self._pick_mode = mode
            tips = {
                "tap": "点击截图设置当前按钮的 X/Y",
                "swipe1": "点击截图设置滑动起点 (x1,y1)",
                "swipe2": "点击截图设置滑动终点 (x2,y2)",
            }
            self.log_message.emit(tips.get(mode, ""))
        elif self._pick_mode == mode:
            self._pick_mode = ""

    def enter_pick_mode(self, mode: str) -> None:
        mapping = {
            "panel": lambda: self._on_pick_panel_toggled(True),
            "tap": lambda: self._on_pick_mode_toggled("tap", True),
            "swipe1": lambda: self._on_pick_mode_toggled("swipe1", True),
            "swipe2": lambda: self._on_pick_mode_toggled("swipe2", True),
        }
        if mode in mapping:
            mapping[mode]()

    def apply_layout_from_editor(self, layout: dict[str, Any]) -> None:
        self._layout_cache = layout
        if self.overlay_cb.isChecked() and self._screen is not None:
            self.canvas.set_layout_overlay(layout, enabled=True)
        self.refresh_panel_preview(layout)

    def on_project_opened(self) -> None:
        self._layout_cache = self._load_layout()
        self.refresh_layout_overlay()
        self.refresh_panel_preview()

    def capture(self) -> None:
        try:
            png = self._adb.capture_png(self._serial() or None)
            self._screen = vision_pc.decode_png(png)
            self.canvas.set_image(self._screen)
            self.refresh_layout_overlay()
            self.refresh_panel_preview()
            self.log_message.emit(f"截图成功 {self._screen.shape[1]}x{self._screen.shape[0]}")
        except Exception as exc:
            QMessageBox.warning(self, "截图失败", str(exc))

    def _on_pixel(self, x: int, y: int) -> None:
        if self._screen is None:
            return
        self._last_xy = (x, y)
        self.canvas.set_highlight_xy((x, y))
        if self._pick_panel_pos and self._layout_cache is not None:
            panel = self._layout_cache.setdefault("panel", {})
            panel["start_x"] = x
            panel["start_y"] = y
            self.refresh_layout_overlay()
            self.panel_position_picked.emit(x, y)
            self.log_message.emit(f"面板位置 ({x}, {y})")
            self._clear_pick_modes()
            return
        if self._pick_mode:
            self.button_coords_picked.emit(x, y, self._pick_mode)
            self.log_message.emit(f"已拾取 {self._pick_mode}: ({x}, {y})")
            self._clear_pick_modes()
            return
        b, g, r = [int(v) for v in self._screen[y, x]]
        self._picked_bgr = (b, g, r)
        sel = self.canvas.selection()
        sel_txt = str(sel) if sel else "-"
        self.info.setText(f"坐标: ({x}, {y}) | BGR: [{b}, {g}, {r}] | 选区: {sel_txt}")

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

    def insert_tap_lua(self) -> None:
        x, y = self._last_xy
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先截图")
            return
        snippet = lua_snippets.tap(x, y)
        self._emit_lua(snippet, f"已生成点击 Lua ({x}, {y})")

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
            self.log_message.emit(f"识字 {len(hits)} 条（绿框已标在截图上）")
            self._last_ocr_hits = hits
            self.canvas.set_ocr_hits(hits)
            for h in hits[:15]:
                self.log_message.emit(f"  [{h.confidence:.2f}] {h.text} @ ({h.center_x},{h.center_y})")
        except Exception as exc:
            QMessageBox.warning(self, "识字", str(exc))

    def insert_ocr_hit_lua(self) -> None:
        hits = getattr(self, "_last_ocr_hits", None) or []
        if not hits:
            QMessageBox.warning(self, "提示", "请先「测试识字」获取结果")
            return
        labels = [f"{h.text} ({h.center_x},{h.center_y})" for h in hits[:20]]
        choice, ok = QInputDialog.getItem(self, "插入识字 Lua", "选择命中文字:", labels, 0, False)
        if not ok:
            return
        idx = labels.index(choice)
        target = hits[idx].text
        snippet = lua_snippets.find_text(target)
        self._emit_lua(snippet, f"已插入识字 Lua: {target}")

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
