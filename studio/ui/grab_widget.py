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
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QLineEdit,
)

from studio.ui.app_theme import set_button_role
from studio.ui.page_shell import (
    main_column,
    page_root,
    section_title,
)
from studio.ui.grab_side_panel import GrabSidePanel
from studio.services.adb_service import AdbService
from studio.services import lua_snippets
from studio.services import vision_pc
from studio.services.layout_defaults import load_layout
from studio.services.canvas_overlay import (
    paint_crosshair,
    paint_match_boxes,
    paint_ocr_hits,
    paint_point_markers,
)
from studio.services.project_images import (
    image_rel_path,
    list_images,
    load_image_settings,
    next_capture_filename,
    resolve_image_dir,
    save_bgr_image,
    save_image_settings,
)
from studio.services.yolo_models import (
    default_model_path,
    list_yolo_models,
    load_class_names,
    merge_class_names_from_detections,
    model_rel_path as yolo_model_rel_path,
)


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
        self._ocr_hits: list[Any] = []
        self._match_boxes: list[dict[str, Any]] = []
        self._point_markers: list[dict[str, Any]] = []
        self._highlight_xy: Optional[Tuple[int, int]] = None
        self._overlay_layout: Optional[dict[str, Any]] = None
        self._overlay_enabled = False

    def set_overlay_layout(self, layout: Optional[dict[str, Any]], enabled: bool) -> None:
        self._overlay_layout = layout
        self._overlay_enabled = enabled
        self._refresh()

    def set_highlight_xy(self, xy: Optional[Tuple[int, int]]) -> None:
        self._highlight_xy = xy
        self._refresh()

    def set_ocr_hits(self, hits: list[Any]) -> None:
        self._ocr_hits = hits or []
        self._refresh()

    def set_match_boxes(self, boxes: list[dict[str, Any]]) -> None:
        self._match_boxes = boxes or []
        self._refresh()

    def set_point_markers(self, markers: list[dict[str, Any]]) -> None:
        self._point_markers = markers or []
        self._refresh()

    def clear_test_overlays(self) -> None:
        self._ocr_hits = []
        self._match_boxes = []
        self._point_markers = []
        self._refresh()

    def set_image(self, bgr: np.ndarray) -> None:
        self._origin = bgr.copy()
        self._selection = None
        self._drag_start = None
        self._drag_end = None
        self.clear_test_overlays()

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
        if self._match_boxes:
            paint_match_boxes(painter, self._match_boxes, self._scale)
        if self._ocr_hits:
            paint_ocr_hits(painter, self._ocr_hits, self._scale)
        if self._point_markers:
            paint_point_markers(painter, self._point_markers, self._scale)
        if self._highlight_xy:
            paint_crosshair(painter, self._highlight_xy[0], self._highlight_xy[1], self._scale)
        if (
            self._overlay_enabled
            and self._overlay_layout
            and self._overlay_layout.get("enabled", True)
        ):
            from studio.services.layout_preview import paint_layout_overlay

            paint_layout_overlay(painter, self._overlay_layout, w, h, scale=self._scale)
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
    panel_position_picked = Signal(int, int)
    button_coords_picked = Signal(int, int, str)
    images_changed = Signal()

    def __init__(self, project_dir_getter) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self._adb = AdbService()
        self._screen: Optional[np.ndarray] = None
        self._last_xy: Tuple[int, int] = (0, 0)
        self._picked_bgr: Optional[Tuple[int, int, int]] = None
        self._last_lua_snippet: str = ""
        self._layout_cache: Optional[dict[str, Any]] = None
        self._pick_panel_pos = False
        self._pick_mode: str = ""
        self._imported_template_path: Optional[Path] = None
        self._last_ocr_hits: list[Any] = []
        self._color_records: list[dict[str, Any]] = []
        self._color_record_seq = 0
        self._last_yolo_dets: list[dict[str, Any]] = []
        self.pick_panel_btn = QPushButton()
        self.pick_panel_btn.hide()
        self.pick_tap_btn = QPushButton()
        self.pick_tap_btn.hide()
        self.pick_swipe1_btn = QPushButton()
        self.pick_swipe1_btn.hide()
        self.pick_swipe2_btn = QPushButton()
        self.pick_swipe2_btn.hide()
        self._build_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        root = page_root(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("GrabMainSplit")

        # —— 左侧工具条 ——
        tool_strip = QFrame()
        tool_strip.setObjectName("GrabToolStrip")
        tool_strip.setFixedWidth(76)
        strip_lay = QVBoxLayout(tool_strip)
        strip_lay.setContentsMargins(6, 8, 6, 8)
        strip_lay.setSpacing(8)
        for text, tip, slot in [
            ("截屏", "ADB 截图", self.capture),
            ("加载", "导入本地图片", self.import_screenshot),
            ("保存", "保存图片到文件", self.save_image_file),
            ("清标", "清除测试标记", self.clear_test_marks),
        ]:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setMinimumHeight(40)
            b.setMinimumWidth(64)
            b.setMaximumWidth(64)
            set_button_role(b, "ghost")
            b.clicked.connect(slot)
            strip_lay.addWidget(b)
        strip_lay.addStretch()
        split.addWidget(tool_strip)

        # —— 中间画布 ——
        center, center_lay = main_column()
        top_bar = QHBoxLayout()
        top_bar.addWidget(section_title("手机抓抓"))
        refresh_btn = QPushButton("刷新设备")
        set_button_role(refresh_btn, "ghost")
        refresh_btn.clicked.connect(self.refresh_devices)
        top_bar.addStretch()
        top_bar.addWidget(refresh_btn)
        center_lay.addLayout(top_bar)
        self.info = QLabel("坐标: —  |  BGR: —  |  选区: —  |  拖拽框选 ROI")
        self.info.setObjectName("InfoBar")
        self.info.setWordWrap(True)
        center_lay.addWidget(self.info)
        canvas_wrap = QFrame()
        canvas_wrap.setObjectName("CanvasWrap")
        canvas_wrap.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas_lay = QVBoxLayout(canvas_wrap)
        canvas_lay.setContentsMargins(0, 0, 0, 0)
        self.canvas = ScreenshotLabel()
        self.canvas.clicked.connect(self._on_pixel)
        self.canvas.selected.connect(self._on_selected)
        canvas_lay.addWidget(self.canvas, 1)
        center_lay.addWidget(canvas_wrap, 1)
        self.local_log = QTextEdit()
        self.local_log.setObjectName("GrabLocalLog")
        self.local_log.setReadOnly(True)
        self.local_log.setMaximumHeight(96)
        self.local_log.setPlaceholderText("测试输出…")
        center_lay.addWidget(self.local_log)
        split.addWidget(center)

        # —— 右侧分栏 ——
        self._panel = GrabSidePanel()
        self._wire_side_panel()
        split.addWidget(self._panel)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([76, 700, 360])
        root.addWidget(split, 1)

        # 兼容旧逻辑的属性别名
        self.device_combo = self._panel.device_combo
        self.image_dir_edit = self._panel.image_dir_edit
        self.image_dir_hint = self._panel.image_dir_hint
        self.show_panel_overlay_cb = self._panel.show_panel_overlay_cb
        self.ocr_target_edit = self._panel.ocr_target_edit
        self.ocr_mode_combo = self._panel.ocr_mode_combo
        self.template_combo = self._panel.template_combo
        self.threshold_edit = self._panel.threshold_edit
        self.tol_edit = self._panel.tol_edit
        self.yolo_model_combo = self._panel.yolo_model_combo
        self.yolo_model_combo.currentIndexChanged.connect(self._on_yolo_model_changed)
        self.device_combo.currentIndexChanged.connect(self._sync_device_tooltip)

    def _wire_side_panel(self) -> None:
        p = self._panel
        p.run_find_color.connect(self.test_color)
        p.run_find_image.connect(self.test_template)
        p.run_find_text.connect(self.test_ocr)
        p.run_adb_tap.connect(self.adb_tap_test)
        p.save_screenshot.connect(self.save_screenshot)
        p.save_template.connect(self.save_template)
        p.clear_marks.connect(self.clear_test_marks)
        p.copy_color_desc.connect(self.copy_color_desc)
        p.copy_roi.connect(self.copy_coords)
        p.copy_script.connect(self.copy_lua)
        p.insert_script.connect(self.insert_lua_to_editor)
        p.copy_color_script.connect(self.copy_color_script)
        p.copy_template_script.connect(self.copy_template_script)
        p.copy_text_script.connect(self.copy_text_script)
        p.copy_tap_script.connect(self.copy_tap_script)
        p.run_yolo_detect.connect(self.test_yolo)
        p.refresh_yolo_classes.connect(self.refresh_yolo_classes)
        p.copy_yolo_detect_script.connect(self.copy_yolo_detect_script)
        p.copy_find_yolo_script.connect(self.copy_find_yolo_script)
        p.copy_yolo_swipe_script.connect(self.copy_yolo_swipe_script)
        p.add_color_record.connect(self.add_color_record)
        p.delete_color_record.connect(self.delete_color_records)
        p.import_template.connect(self.import_template_file)
        p.pick_panel.connect(self._toggle_panel_pick)
        p.pick_tap.connect(lambda: self._toggle_pick("tap"))
        p.pick_swipe1.connect(lambda: self._toggle_pick("swipe1"))
        p.pick_swipe2.connect(lambda: self._toggle_pick("swipe2"))
        p.image_dir_edit.editingFinished.connect(self._on_image_settings_changed)
        p.show_panel_overlay_cb.toggled.connect(self._update_panel_overlay)
        p._pick_image_dir_btn.clicked.connect(self._pick_image_dir)

    def _sync_device_tooltip(self, index: int = -1) -> None:
        if index < 0:
            index = self.device_combo.currentIndex()
        if index < 0:
            return
        tip = self.device_combo.itemData(index, Qt.ItemDataRole.ToolTipRole)
        if tip:
            self.device_combo.setToolTip(str(tip))

    def save_image_file(self) -> None:
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先截图或加载图片")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存图片",
            "capture.png",
            "PNG 图片 (*.png);;JPEG (*.jpg)",
        )
        if not path:
            return
        if not cv2.imwrite(path, self._screen):
            QMessageBox.warning(self, "保存失败", path)
            return
        self._log(f"已保存图片: {path}")

    def refresh_image_assets(self) -> None:
        """附件增删后刷新抓抓页模板列表。"""
        self._refresh_template_combo()

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
            self.device_combo.addItem(d.combo_text, d.serial)
            row = self.device_combo.count() - 1
            self.device_combo.setItemData(row, d.label, Qt.ItemDataRole.ToolTipRole)
            if d.is_emulator and emu_idx == 0:
                emu_idx = i
        self.device_combo.setCurrentIndex(emu_idx)
        tip = devs[emu_idx].label if devs else ""
        self.device_combo.setToolTip(tip)

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

    def _update_panel_overlay(self) -> None:
        self.canvas.set_overlay_layout(
            self._layout_cache,
            self.show_panel_overlay_cb.isChecked(),
        )

    def apply_layout_from_editor(self, layout: dict[str, Any]) -> None:
        self._layout_cache = layout
        self._update_panel_overlay()

    def on_project_opened(self) -> None:
        self._layout_cache = self._load_layout()
        self._update_panel_overlay()
        self._load_image_settings_ui()
        self._refresh_template_combo()
        self.refresh_yolo_models()

    def refresh_yolo_models(self) -> None:
        self.yolo_model_combo.blockSignals(True)
        self.yolo_model_combo.clear()
        project = self._project_dir_getter()
        if not project:
            self.yolo_model_combo.blockSignals(False)
            return
        models = list_yolo_models(Path(project))
        for path in models:
            rel = yolo_model_rel_path(Path(project), path)
            self.yolo_model_combo.addItem(f"{path.name} ({rel})", str(path))
        default = default_model_path(Path(project))
        if default:
            idx = self.yolo_model_combo.findData(str(default))
            if idx >= 0:
                self.yolo_model_combo.setCurrentIndex(idx)
        self.yolo_model_combo.blockSignals(False)
        self.refresh_yolo_classes()

    def _on_yolo_model_changed(self, _index: int = 0) -> None:
        self.refresh_yolo_classes()

    def refresh_yolo_classes(self) -> None:
        path = self._current_yolo_model_path()
        known: list[str] = []
        if path and path.is_file():
            known = load_class_names(path)
        known = merge_class_names_from_detections(known, self._last_yolo_dets)
        self._panel.set_yolo_class_names(known)

    def _current_yolo_model_path(self) -> Path | None:
        raw = self._panel.yolo_model_path()
        if not raw:
            return None
        return Path(raw)

    def _yolo_script_context(self) -> tuple[str, str, dict, Optional[tuple[int, int, int, int]]] | None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return None
        path = self._current_yolo_model_path()
        if path is None or not path.is_file():
            QMessageBox.warning(self, "提示", "请在 YOLO Tab 选择 models/ 下的 .onnx 或 .pt")
            return None
        rel = yolo_model_rel_path(Path(project), path)
        class_name = self._panel.yolo_class_name()
        params = self._panel.yolo_params()
        roi = self.canvas.selection()
        return rel, class_name, params, roi

    def copy_yolo_detect_script(self) -> None:
        ctx = self._yolo_script_context()
        if ctx is None:
            return
        rel, class_name, params, roi = ctx
        snippet = lua_snippets.yolo_detect(
            rel,
            class_name=class_name,
            conf=params["conf"],
            roi=roi,
        )
        self._prepare_script(snippet, "已生成 yoloDetect 脚本")

    def copy_find_yolo_script(self) -> None:
        ctx = self._yolo_script_context()
        if ctx is None:
            return
        rel, class_name, params, roi = ctx
        if params.get("click") and not class_name:
            QMessageBox.warning(self, "提示", "勾选点击时请指定目标类别")
            return
        snippet = lua_snippets.find_yolo(
            rel,
            class_name=class_name,
            conf=params["conf"],
            pick=params["pick"],
            roi=roi,
            frac=params["frac"],
            tap_dx=params["tap_dx"] if params.get("click") else 0,
            tap_dy=params["tap_dy"] if params.get("click") else 0,
            delay_before_click=params["delay_before_click"] if params.get("click") else 0.0,
            click=bool(params.get("click")),
            optional=True,
        )
        tip = "已生成 findYolo（含点击）脚本" if params.get("click") else "已生成 findYolo 脚本"
        self._prepare_script(snippet, tip)

    def copy_yolo_swipe_script(self) -> None:
        ctx = self._yolo_script_context()
        if ctx is None:
            return
        rel, class_name, params, roi = ctx
        if not class_name:
            QMessageBox.warning(self, "提示", "请指定目标类别")
            return
        snippet = lua_snippets.yolo_swipe(
            rel,
            class_name=class_name,
            conf=params["conf"],
            pick=params["pick"],
            roi=roi,
            frac=params["frac"],
            direction=params["direction"],
            distance=params["distance"],
            duration_ms=params["duration_ms"],
        )
        self._prepare_script(snippet, f"已生成 yoloSwipe 脚本: {class_name}")

    def _log(self, msg: str) -> None:
        self.log_message.emit(msg)
        if hasattr(self, "local_log"):
            self.local_log.append(msg)
            sb = self.local_log.verticalScrollBar()
            if sb is not None:
                sb.setValue(sb.maximum())

    def _parse_float(self, text: str, default: float) -> float:
        try:
            return float(text.strip())
        except ValueError:
            return default

    def _parse_int(self, text: str, default: int) -> int:
        try:
            return int(text.strip())
        except ValueError:
            return default

    def _refresh_template_combo(self) -> None:
        self.template_combo.clear()
        self.template_combo.addItem("（框选后存模板）", "")
        project = self._project_dir_getter()
        if not project:
            return
        for path in list_images(Path(project)):
            rel = image_rel_path(Path(project), path)
            self.template_combo.addItem(path.name, str(path))
        if self._imported_template_path and self._imported_template_path.is_file():
            self.template_combo.insertItem(
                1,
                f"导入: {self._imported_template_path.name}",
                str(self._imported_template_path),
            )

    def import_template_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入模板图",
            "",
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        self._imported_template_path = Path(path)
        self._refresh_template_combo()
        self.template_combo.setCurrentIndex(1)
        self._log(f"已导入模板: {path}")

    def _current_template_bgr(self) -> tuple[np.ndarray, str] | None:
        raw = self.template_combo.currentData()
        if not raw:
            return None
        path = Path(str(raw))
        tpl = vision_pc.imread_bgr(path)
        if tpl is None:
            QMessageBox.warning(self, "模板无效", f"无法读取模板图:\n{path}")
            return None
        project = self._project_dir_getter()
        label = image_rel_path(Path(project), path) if project else path.name
        return tpl, label

    def clear_test_marks(self) -> None:
        self.canvas.clear_test_overlays()
        self._last_ocr_hits = []
        self._log("已清除找图/识字/找色标记")

    def copy_coords(self) -> None:
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先 ADB 截图")
            return
        x, y = self._last_xy
        sel = self.canvas.selection()
        if sel:
            text = f"{sel[0]},{sel[1]},{sel[2]},{sel[3]}"
        else:
            text = f"{x},{y}"
        QGuiApplication.clipboard().setText(text)
        self._log(f"已复制坐标: {text}")

    def _load_image_settings_ui(self) -> None:
        project = self._project_dir_getter()
        if not project:
            self.image_dir_edit.clear()
            self.image_dir_hint.setText("打开工程后可配置图片保存目录")
            return
        settings = load_image_settings(Path(project))
        self.image_dir_edit.blockSignals(True)
        self.image_dir_edit.setText(str(settings.get("image_dir") or "image"))
        self.image_dir_edit.blockSignals(False)
        resolved = resolve_image_dir(Path(project), settings)
        self.image_dir_hint.setText(f"保存到: {resolved}")

    def _on_image_settings_changed(self) -> None:
        project = self._project_dir_getter()
        if not project:
            return
        settings = {
            "image_dir": self.image_dir_edit.text().strip() or "image",
        }
        save_image_settings(Path(project), settings)
        resolved = resolve_image_dir(Path(project), settings)
        self.image_dir_hint.setText(f"保存到: {resolved}")

    def _pick_image_dir(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return
        start = resolve_image_dir(Path(project))
        start.mkdir(parents=True, exist_ok=True)
        dest = QFileDialog.getExistingDirectory(self, "选择图片保存目录", str(start))
        if not dest:
            return
        dest_path = Path(dest)
        project_path = Path(project).resolve()
        try:
            rel = dest_path.resolve().relative_to(project_path)
            self.image_dir_edit.setText(rel.as_posix())
        except ValueError:
            self.image_dir_edit.setText(str(dest_path))
        self._on_image_settings_changed()

    def _image_dir(self) -> Path | None:
        project = self._project_dir_getter()
        if not project:
            return None
        return resolve_image_dir(Path(project))

    def _clear_pick_modes(self) -> None:
        self._pick_panel_pos = False
        self._pick_mode = ""

    def capture(self) -> None:
        try:
            png = self._adb.capture_png(self._serial() or None)
            self._screen = vision_pc.decode_png(png)
            self.canvas.set_image(self._screen)
            msg = f"截图成功 {self._screen.shape[1]}x{self._screen.shape[0]}"
            self._log(msg)
        except Exception as exc:
            QMessageBox.warning(self, "截图失败", str(exc))

    def import_screenshot(self) -> None:
        project = self._project_dir_getter()
        start_dir = str(resolve_image_dir(Path(project))) if project else ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入截图",
            start_dir,
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        bgr = vision_pc.imread_bgr(path)
        if bgr is None:
            QMessageBox.warning(self, "导入失败", f"无法读取图片:\n{path}")
            return
        self._screen = bgr
        self.canvas.set_image(bgr)
        self._picked_bgr = None
        self._log(f"已导入截图: {Path(path).name} ({bgr.shape[1]}x{bgr.shape[0]})")
        QMessageBox.information(
            self,
            "导入成功",
            f"已加载: {Path(path).name}\n可框选 ROI 后测试找图/识字，或点「存截图」保存到工程",
        )

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

    def _on_pixel(self, x: int, y: int) -> None:
        if self._screen is None:
            return
        self._last_xy = (x, y)
        self.canvas.set_highlight_xy((x, y))
        if self._pick_panel_pos and self._layout_cache is not None:
            panel = self._layout_cache.setdefault("panel", {})
            panel["start_x"] = x
            panel["start_y"] = y
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
        self._update_color_ui(x, y, b, g, r)

    def _update_color_ui(self, x: int, y: int, b: int, g: int, r: int) -> None:
        tol = self._parse_int(self.tol_edit.text(), 15)
        roi = self.canvas.selection()
        desc = lua_snippets.find_color((b, g, r), tol=tol, roi=roi)
        self._panel.set_color_preview(x, y, b, g, r, desc)

    def _prepare_script(self, snippet: str, log_msg: str) -> None:
        self._last_lua_snippet = snippet.strip()
        self._panel.set_script(self._last_lua_snippet)
        self._log(log_msg)

    def _on_selected(self, x: int, y: int, w: int, h: int) -> None:
        parts = self.info.text().split("|")
        head = parts[0].strip() if parts else f"坐标: ({self._last_xy[0]}, {self._last_xy[1]})"
        bgr_part = ""
        for part in parts:
            if "BGR" in part:
                bgr_part = part.strip()
                break
        tail = f" | {bgr_part} |" if bgr_part else " |"
        self.info.setText(f"{head}{tail} 选区: ({x},{y},{w},{h})")
        self._panel.set_roi_fields(x, y, w, h)
        self._log(f"框选 ROI: x={x}, y={y}, w={w}, h={h}")
        if self._picked_bgr:
            self._update_color_ui(self._last_xy[0], self._last_xy[1], *self._picked_bgr)
        if self._panel.copy_roi_cb.isChecked():
            QGuiApplication.clipboard().setText(f"{x},{y},{w},{h}")
            self._log(f"已复制选区: {x},{y},{w},{h}")

    def copy_bgr(self) -> None:
        if self._picked_bgr is None:
            QMessageBox.warning(self, "提示", "请先截图并移动鼠标取色")
            return
        b, g, r = self._picked_bgr
        QGuiApplication.clipboard().setText(f"[{b}, {g}, {r}]")
        self._log(f"已复制 BGR: [{b}, {g}, {r}]")

    def copy_color_desc(self) -> None:
        text = self._panel.color_desc_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先在截图上移动鼠标取色")
            return
        QGuiApplication.clipboard().setText(text)
        self._log("已复制颜色描述到剪贴板")

    def add_color_record(self) -> None:
        if self._picked_bgr is None:
            QMessageBox.warning(self, "提示", "请先在截图上取色")
            return
        x, y = self._last_xy
        b, g, r = self._picked_bgr
        self._color_record_seq += 1
        self._color_records.append({"x": x, "y": y, "bgr": (b, g, r)})
        self._panel.append_color_record(self._color_record_seq, x, y, b, g, r)
        self._log(f"已记入颜色 #{self._color_record_seq}")

    def delete_color_records(self) -> None:
        rows = self._panel.remove_selected_color_records()
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._color_records):
                self._color_records.pop(row)
        self._log(f"已删除 {len(rows)} 条颜色记录")

    def copy_lua(self) -> None:
        text = self._panel.script_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先生成或测试一段 Lua 代码")
            return
        self._last_lua_snippet = text
        QGuiApplication.clipboard().setText(text)
        self._log("已复制完整脚本到剪贴板，请粘贴到 main.lua")

    def insert_lua_to_editor(self) -> None:
        text = self._panel.script_edit.toPlainText().strip()
        if not text:
            if self._last_lua_snippet:
                text = self._last_lua_snippet
            else:
                QMessageBox.warning(self, "提示", "请先生成或测试一段 Lua 代码")
                return
        self.insert_lua.emit(text)
        self._log("已请求插入到脚本页")

    def copy_color_script(self) -> None:
        if self._picked_bgr is None:
            QMessageBox.warning(self, "提示", "请先截图并移动鼠标取色")
            return
        roi = self.canvas.selection()
        tol = self._parse_int(self.tol_edit.text(), 15)
        snippet = lua_snippets.find_color(self._picked_bgr, tol=tol, roi=roi)
        self._prepare_script(snippet, "已生成找色脚本（请点复制完整脚本）")

    def copy_template_script(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return
        picked = self._current_template_bgr()
        if picked is None:
            QMessageBox.warning(self, "提示", "请先选择或导入模板图")
            return
        _, rel = picked
        roi = self.canvas.selection()
        threshold = self._parse_float(self.threshold_edit.text(), 0.9)
        snippet = lua_snippets.find_image(rel, threshold=threshold, roi=roi)
        self._prepare_script(snippet, f"已生成找图脚本: {rel}")

    def copy_text_script(self) -> None:
        target = self.ocr_target_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "提示", "请输入识字目标文字")
            return
        snippet = lua_snippets.find_text(target, match_mode=str(self.ocr_mode_combo.currentData() or "contains"))
        self._prepare_script(snippet, f"已生成识字脚本: {target}")

    def copy_tap_script(self) -> None:
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先截图")
            return
        x, y = self._last_xy
        self._prepare_script(lua_snippets.tap(x, y), f"已生成点击脚本 ({x}, {y})")

    def adb_tap_test(self) -> None:
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先 ADB 截图，再在画面上移动鼠标到目标位置")
            return
        x, y = self._last_xy
        serial = self._serial()
        if not serial:
            QMessageBox.warning(self, "提示", "未检测到 ADB 设备，请先刷新设备列表")
            return
        try:
            self._adb.tap(serial, x, y)
            self.canvas.set_point_markers([{"x": x, "y": y, "label": f"tap ({x},{y})"}])
            self._log(f"ADB 点击成功: ({x}, {y})")
            QMessageBox.information(self, "ADB 点击", f"已向设备发送点击 ({x}, {y})")
        except Exception as exc:
            QMessageBox.warning(self, "ADB 点击失败", str(exc))

    def save_screenshot(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先 ADB 截图")
            return
        default = next_capture_filename("screen").replace(".png", "")
        name, ok = QInputDialog.getText(self, "保存截图", "文件名（不含扩展名）:", text=default)
        if not ok or not name.strip():
            return
        name = name.strip()
        if not name.lower().endswith(".png"):
            name += ".png"
        out = save_bgr_image(Path(project), self._screen, name)
        rel = image_rel_path(Path(project), out)
        self.images_changed.emit()
        self._refresh_template_combo()
        self._log(f"已保存截图: {rel}")
        QMessageBox.information(self, "完成", f"截图已保存到:\n{rel}")

    def save_template(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先在「工程」页打开脚本工程")
            return
        sel = self.canvas.selection()
        if self._screen is None or not sel or sel[2] < 2 or sel[3] < 2:
            QMessageBox.warning(self, "提示", "请先截图并框选模板区域")
            return
        img_dir = self._image_dir()
        default = f"tpl_{len(list_images(Path(project)))}"
        name, ok = QInputDialog.getText(self, "模板名称", "文件名（不含扩展名）:", text=default)
        if not ok or not name.strip():
            return
        name = name.strip()
        if not name.lower().endswith(".png"):
            name += ".png"
        x, y, w, h = sel
        crop = self._screen[y : y + h, x : x + w]
        out = save_bgr_image(Path(project), crop, name)
        rel = image_rel_path(Path(project), out)
        self.images_changed.emit()
        self._refresh_template_combo()
        idx = self.template_combo.findData(str(out))
        if idx >= 0:
            self.template_combo.setCurrentIndex(idx)
        self._log(f"已保存模板: {rel}")
        QMessageBox.information(self, "完成", f"模板已保存到:\n{rel}")

    def test_color(self) -> None:
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先 ADB 截图")
            return
        if self._picked_bgr is None:
            QMessageBox.warning(self, "提示", "请在截图上移动鼠标到目标颜色位置（或先取色）")
            return
        tol = self._parse_int(self.tol_edit.text(), 15)
        roi = self.canvas.selection()
        pt = vision_pc.find_color(self._screen, self._picked_bgr, tol=tol, roi=roi)
        if pt:
            b, g, r = self._picked_bgr
            self.canvas.set_point_markers(
                [{"x": pt[0], "y": pt[1], "label": f"找色 ({pt[0]},{pt[1]})"}]
            )
            self._log(f"找色命中 BGR[{b},{g},{r}] → ({pt[0]}, {pt[1]})，容差={tol}")
            if roi:
                self._log(f"  搜索范围 ROI={roi}")
            snippet = lua_snippets.find_color(self._picked_bgr, tol=tol, roi=roi)
            self._prepare_script(snippet, "找色命中，已生成脚本（点复制完整脚本）")
            QMessageBox.information(self, "找色命中", f"坐标: ({pt[0]}, {pt[1]})")
        else:
            self.canvas.set_point_markers([])
            self._log("找色未命中，可增大容差或调整 ROI")
            QMessageBox.information(self, "找色未命中", "当前截图/ROI 内未找到该颜色")

    def test_template(self) -> None:
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先 ADB 截图")
            return
        picked = self._current_template_bgr()
        if picked is None:
            QMessageBox.warning(
                self,
                "提示",
                "请选择模板图：\n· 下拉框选工程内图片\n· 或点「导入」选本地文件\n· 或框选区域后「存模板」",
            )
            return
        tpl, label = picked
        threshold = self._parse_float(self.threshold_edit.text(), 0.85)
        roi = self.canvas.selection()
        m = vision_pc.match_template(self._screen, tpl, threshold=threshold, roi=roi)
        if m:
            self.canvas.set_match_boxes(
                [
                    {
                        "x": m.x,
                        "y": m.y,
                        "w": m.w,
                        "h": m.h,
                        "label": f"{label} {m.score:.2f}",
                    }
                ]
            )
            self.canvas.set_point_markers(
                [{"x": m.center_x, "y": m.center_y, "label": f"中心 ({m.center_x},{m.center_y})"}]
            )
            self._log(f"找图命中: {label} score={m.score:.3f} @ ({m.center_x},{m.center_y})")
            if roi:
                self._log(f"  搜索范围 ROI={roi}")
            snippet = lua_snippets.find_image(label, threshold=threshold, roi=roi)
            self._prepare_script(snippet, f"找图命中，已生成脚本: {label}")
            QMessageBox.information(
                self,
                "找图命中",
                f"模板: {label}\n相似度: {m.score:.3f}\n中心: ({m.center_x}, {m.center_y})",
            )
        else:
            self.canvas.set_match_boxes([])
            self.canvas.set_point_markers([])
            self._log(f"找图未命中: {label}（阈值 {threshold}）")
            QMessageBox.information(
                self,
                "找图未命中",
                f"未在截图中找到模板 {label}\n可尝试降低阈值或调整 ROI",
            )

    def test_ocr(self) -> None:
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先 ADB 截图")
            return
        target = self.ocr_target_edit.text().strip()
        match_mode = str(self.ocr_mode_combo.currentData() or "contains")
        roi = self.canvas.selection()
        try:
            if target:
                hits = vision_pc.find_text(
                    self._screen,
                    target,
                    match_mode=match_mode,
                    roi=roi,
                )
            else:
                hits = vision_pc.recognize_text(self._screen, roi=roi)
        except Exception as exc:
            QMessageBox.warning(self, "识字失败", str(exc))
            self._log(f"识字失败: {exc}")
            return
        self._last_ocr_hits = hits
        self.canvas.set_ocr_hits(hits)
        if target:
            self._log(f"识字「{target}」({match_mode}) 命中 {len(hits)} 处")
        else:
            self._log(f"全量识字 {len(hits)} 条（可在上方输入目标文字后重试）")
        if roi:
            self._log(f"  识别范围 ROI={roi}")
        if not hits:
            QMessageBox.information(
                self,
                "识字无结果",
                "未识别到文字。\n可框选更小区域、提高截图对比度，或安装 PaddleOCR。",
            )
            return
        for h in hits[:15]:
            self._log(f"  [{h.confidence:.2f}] {h.text} @ ({h.center_x},{h.center_y})")
        if len(hits) > 15:
            self._log(f"  … 另有 {len(hits) - 15} 条")
        if target:
            snippet = lua_snippets.find_text(target, match_mode=match_mode)
            self._prepare_script(snippet, f"识字命中，已生成脚本: {target}")
        elif hits:
            snippet = lua_snippets.find_text(hits[0].text, match_mode="contains")
            self._prepare_script(snippet, f"已按首条命中生成脚本: {hits[0].text}")
        QMessageBox.information(self, "识字完成", f"共 {len(hits)} 处命中，绿框已标在截图上")

    def copy_ocr_hit_script(self) -> None:
        hits = self._last_ocr_hits
        if not hits:
            QMessageBox.warning(self, "提示", "请先「识字测试」获取结果")
            return
        labels = [f"{h.text} ({h.center_x},{h.center_y})" for h in hits[:20]]
        choice, ok = QInputDialog.getItem(self, "生成识字脚本", "选择命中文字:", labels, 0, False)
        if not ok:
            return
        idx = labels.index(choice)
        target = hits[idx].text
        match_mode = str(self.ocr_mode_combo.currentData() or "contains")
        snippet = lua_snippets.find_text(target, match_mode=match_mode)
        self._prepare_script(snippet, f"已生成识字脚本: {target}")

    def test_yolo(self) -> None:
        project = self._project_dir_getter()
        if not project:
            QMessageBox.warning(self, "提示", "请先打开工程")
            return
        if self._screen is None:
            QMessageBox.warning(self, "提示", "请先 ADB 截图")
            return
        path = self._current_yolo_model_path()
        if path is None or not path.is_file():
            QMessageBox.warning(self, "提示", "工程 models/ 下没有可用模型，或请在 YOLO Tab 选择模型")
            return
        class_name = self._panel.yolo_class_name()
        params = self._panel.yolo_params()
        roi = self.canvas.selection()
        try:
            dets = vision_pc.yolo_detect(
                self._screen,
                str(path),
                conf=params["conf"],
                class_name=class_name,
                roi=roi,
            )
        except Exception as exc:
            QMessageBox.warning(self, "YOLO", str(exc))
            self._log(f"YOLO 失败: {exc}")
            return
        self._last_yolo_dets = dets
        self.refresh_yolo_classes()
        markers = [
            {"x": d["center_x"], "y": d["center_y"], "label": f"{d['class_name']} {d['confidence']:.2f}"}
            for d in dets[:20]
        ]
        boxes = [
            {"x": d["x"], "y": d["y"], "w": d["w"], "h": d["h"], "label": d["class_name"]}
            for d in dets[:20]
        ]
        self.canvas.set_match_boxes(boxes)
        self.canvas.set_point_markers(markers)
        rel = yolo_model_rel_path(Path(project), path)
        self._log(f"YOLO {path.name} 检出 {len(dets)} 个（class={class_name or '全部'}）")
        for d in dets[:12]:
            self._log(
                f"  {d['class_name']} {d['confidence']:.2f} @ ({d['center_x']},{d['center_y']})"
            )
        if dets:
            snippet = lua_snippets.yolo_detect(rel, class_name=class_name, conf=params["conf"], roi=roi)
            self._prepare_script(snippet, "检测完成，已生成 yoloDetect 脚本")
        if not dets:
            QMessageBox.information(self, "YOLO", "未检出目标，可降低置信度或调整 ROI")
            return
        QMessageBox.information(self, "YOLO", f"检出 {len(dets)} 个目标，类别已刷新到下拉框")
