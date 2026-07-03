"""抓抓右侧分栏：颜色 / 找图识字 / 坐标取点（对齐按键精灵手机抓抓交互）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from studio.ui.app_theme import set_button_role
from studio.ui.page_shell import hint_label, section_title, configure_elide_combo


def _scroll_tab(content: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    return scroll


class GrabSidePanel(QWidget):
    """右侧操作面板。"""

    run_find_color = Signal()
    run_find_image = Signal()
    run_find_text = Signal()
    run_adb_tap = Signal()
    save_screenshot = Signal()
    save_template = Signal()
    clear_marks = Signal()
    copy_color_desc = Signal()
    copy_roi = Signal()
    copy_script = Signal()
    copy_color_script = Signal()
    copy_template_script = Signal()
    copy_text_script = Signal()
    copy_tap_script = Signal()
    add_color_record = Signal()
    delete_color_record = Signal()
    import_template = Signal()
    pick_panel = Signal()
    pick_tap = Signal()
    pick_swipe1 = Signal()
    pick_swipe2 = Signal()
    run_yolo_detect = Signal()
    refresh_yolo_classes = Signal()
    copy_yolo_detect_script = Signal()
    copy_find_yolo_script = Signal()
    copy_yolo_swipe_script = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(280)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("GrabSideTabs")
        self.tabs.addTab(_scroll_tab(self._build_color_tab()), "颜色")
        self.tabs.addTab(_scroll_tab(self._build_vision_tab()), "找图识字")
        self.tabs.addTab(_scroll_tab(self._build_yolo_tab()), "YOLO")
        self.tabs.addTab(_scroll_tab(self._build_coord_tab()), "坐标取点")
        root.addWidget(self.tabs, 1)

    def _action_btn(self, text: str, slot, role: str = "ghost") -> QPushButton:
        b = QPushButton(text)
        set_button_role(b, role)
        b.clicked.connect(slot)
        b.setMinimumHeight(34)
        b.setSizePolicy(
            b.sizePolicy().horizontalPolicy(),
            b.sizePolicy().verticalPolicy(),
        )
        return b

    def _stack_buttons(self, parent_lay: QVBoxLayout, specs: list[tuple[str, object, str]]) -> None:
        for text, slot, role in specs:
            parent_lay.addWidget(self._action_btn(text, slot, role))

    def _build_color_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 12)
        lay.setSpacing(8)

        preview_row = QHBoxLayout()
        self.color_swatch = QFrame()
        self.color_swatch.setFixedSize(56, 56)
        self.color_swatch.setObjectName("ColorSwatch")
        self.color_swatch.setStyleSheet("background:#E2E8F0;border:1px solid #CBD5E1;border-radius:6px;")
        preview_row.addWidget(self.color_swatch)
        meta_col = QVBoxLayout()
        self.color_bgr_label = QLabel("BGR: —")
        self.color_bgr_label.setObjectName("InfoBar")
        self.color_hex_label = QLabel("HEX: —")
        self.color_hex_label.setObjectName("InfoBar")
        self.color_xy_label = QLabel("坐标: —")
        self.color_xy_label.setObjectName("InfoBar")
        meta_col.addWidget(self.color_bgr_label)
        meta_col.addWidget(self.color_hex_label)
        meta_col.addWidget(self.color_xy_label)
        preview_row.addLayout(meta_col, 1)
        lay.addLayout(preview_row)

        lay.addWidget(section_title("颜色描述"))
        desc_row = QHBoxLayout()
        self.color_desc_edit = QLineEdit()
        self.color_desc_edit.setPlaceholderText("取色后自动生成 bot.findColor(...)")
        self.color_desc_edit.setReadOnly(True)
        copy_desc_btn = QPushButton("复制")
        set_button_role(copy_desc_btn, "ghost")
        copy_desc_btn.clicked.connect(self.copy_color_desc.emit)
        desc_row.addWidget(self.color_desc_edit, 1)
        desc_row.addWidget(copy_desc_btn)
        lay.addLayout(desc_row)

        lay.addWidget(section_title("选取范围 ROI"))
        self.roi_x1 = QLineEdit()
        self.roi_y1 = QLineEdit()
        self.roi_x2 = QLineEdit()
        self.roi_y2 = QLineEdit()
        for e in (self.roi_x1, self.roi_y1, self.roi_x2, self.roi_y2):
            e.setReadOnly(True)
            e.setPlaceholderText("0")
        roi_form = QFormLayout()
        roi_form.addRow("左上 X", self.roi_x1)
        roi_form.addRow("左上 Y", self.roi_y1)
        roi_form.addRow("右下 X", self.roi_x2)
        roi_form.addRow("右下 Y", self.roi_y2)
        roi_wrap = QWidget()
        roi_wrap.setLayout(roi_form)
        lay.addWidget(roi_wrap)
        self.copy_roi_cb = QCheckBox("框选后复制坐标")
        lay.addWidget(self.copy_roi_cb)
        lay.addWidget(self._action_btn("复制选区", self.copy_roi.emit))

        lay.addWidget(section_title("颜色记录"))
        lay.addWidget(hint_label("移动鼠标取色后点「记入列表」"))
        self.color_table = QTableWidget(0, 4)
        self.color_table.setHorizontalHeaderLabels(["序号", "坐标", "BGR", "HEX"])
        self.color_table.horizontalHeader().setStretchLastSection(True)
        self.color_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.color_table.setMinimumHeight(100)
        self.color_table.setMaximumHeight(160)
        lay.addWidget(self.color_table)
        rec_row = QHBoxLayout()
        rec_row.addWidget(self._action_btn("记入列表", self.add_color_record.emit, "accent"))
        rec_row.addWidget(self._action_btn("删除", self.delete_color_record.emit))
        lay.addLayout(rec_row)

        lay.addWidget(section_title("找色脚本"))
        self._stack_buttons(
            lay,
            [
                ("生成找色脚本", self.copy_color_script.emit, "accent"),
                ("测试区域找色", self.run_find_color.emit, "ghost"),
            ],
        )
        return w

    def _build_vision_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 12)
        lay.setSpacing(8)

        lay.addWidget(section_title("找图模板"))
        self.template_combo = QComboBox()
        lay.addWidget(self.template_combo)
        lay.addWidget(self._action_btn("导入模板图", self.import_template.emit))

        lay.addWidget(section_title("参数"))
        param_form = QFormLayout()
        self.threshold_edit = QLineEdit("0.90")
        self.tol_edit = QLineEdit("15")
        param_form.addRow("相似度", self.threshold_edit)
        param_form.addRow("找色容差", self.tol_edit)
        param_wrap = QWidget()
        param_wrap.setLayout(param_form)
        lay.addWidget(param_wrap)

        lay.addWidget(section_title("识字"))
        self.ocr_target_edit = QLineEdit()
        self.ocr_target_edit.setPlaceholderText("目标文字，留空=识别全部")
        lay.addWidget(self.ocr_target_edit)
        self.ocr_mode_combo = QComboBox()
        self.ocr_mode_combo.addItem("包含匹配", "contains")
        self.ocr_mode_combo.addItem("完全匹配", "exact")
        lay.addWidget(self.ocr_mode_combo)

        lay.addWidget(section_title("测试"))
        self._stack_buttons(
            lay,
            [
                ("区域找色", self.run_find_color.emit, "ghost"),
                ("区域找图", self.run_find_image.emit, "accent"),
                ("识字测试", self.run_find_text.emit, "accent"),
            ],
        )

        lay.addWidget(section_title("素材"))
        self._stack_buttons(
            lay,
            [
                ("存截图到工程", self.save_screenshot.emit, "ghost"),
                ("存框选为模板", self.save_template.emit, "ghost"),
                ("清除测试标记", self.clear_marks.emit, "ghost"),
            ],
        )

        lay.addWidget(section_title("生成脚本"))
        self._stack_buttons(
            lay,
            [
                ("生成找色脚本", self.copy_color_script.emit, "ghost"),
                ("生成找图脚本", self.copy_template_script.emit, "ghost"),
                ("生成识字脚本", self.copy_text_script.emit, "ghost"),
            ],
        )

        self.script_edit = QTextEdit()
        self.script_edit.setObjectName("GrabScriptEdit")
        self.script_edit.setPlaceholderText("测试或取色后，Lua 代码将显示在这里…")
        self.script_edit.setMinimumHeight(100)
        lay.addWidget(self.script_edit)
        lay.addWidget(self._action_btn("复制完整脚本", self.copy_script.emit, "primary"))
        return w

    def _build_yolo_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 12)
        lay.setSpacing(8)

        lay.addWidget(section_title("模型"))
        self.yolo_model_combo = QComboBox()
        self.yolo_model_combo.setPlaceholderText("工程 models/ 下 .onnx / .pt")
        lay.addWidget(self.yolo_model_combo)
        lay.addWidget(self._action_btn("刷新模型与类别", self.refresh_yolo_classes.emit))

        lay.addWidget(section_title("目标类别"))
        self.yolo_class_combo = QComboBox()
        self.yolo_class_combo.setEditable(True)
        self.yolo_class_combo.setPlaceholderText("留空=全部类别")
        lay.addWidget(self.yolo_class_combo)
        lay.addWidget(hint_label("需 models/*.labels 或 .pt；可先点「YOLO 检测」从截图识别类别"))

        lay.addWidget(section_title("检测参数"))
        yolo_form = QFormLayout()
        self.yolo_conf_edit = QLineEdit("0.35")
        self.yolo_pick_combo = QComboBox()
        self.yolo_pick_combo.addItem("最高置信度", "best_conf")
        self.yolo_pick_combo.addItem("最大框", "largest")
        self.yolo_pick_combo.addItem("首个", "nearest")
        self.yolo_frac_x = QLineEdit("0.5")
        self.yolo_frac_y = QLineEdit("0.5")
        yolo_form.addRow("置信度", self.yolo_conf_edit)
        yolo_form.addRow("选取策略", self.yolo_pick_combo)
        yolo_form.addRow("点击位置 X%", self.yolo_frac_x)
        yolo_form.addRow("点击位置 Y%", self.yolo_frac_y)
        yolo_wrap = QWidget()
        yolo_wrap.setLayout(yolo_form)
        lay.addWidget(yolo_wrap)

        lay.addWidget(section_title("点击偏移 / 延迟"))
        self.yolo_click_cb = QCheckBox("找到后点击")
        lay.addWidget(self.yolo_click_cb)
        click_form = QFormLayout()
        self.yolo_tap_dx = QLineEdit("0")
        self.yolo_tap_dy = QLineEdit("0")
        self.yolo_delay_edit = QLineEdit("0")
        self.yolo_delay_edit.setPlaceholderText("秒，点击前等待")
        click_form.addRow("偏移 dx", self.yolo_tap_dx)
        click_form.addRow("偏移 dy", self.yolo_tap_dy)
        click_form.addRow("延迟点击", self.yolo_delay_edit)
        click_wrap = QWidget()
        click_wrap.setLayout(click_form)
        lay.addWidget(click_wrap)
        lay.addWidget(hint_label("勾选「找到后点击」时偏移/延迟生效"))

        lay.addWidget(section_title("滑动（yoloSwipe）"))
        swipe_form = QFormLayout()
        self.yolo_swipe_dir = QComboBox()
        self.yolo_swipe_dir.addItem("向上", "up")
        self.yolo_swipe_dir.addItem("向下", "down")
        self.yolo_swipe_dir.addItem("向左", "left")
        self.yolo_swipe_dir.addItem("向右", "right")
        self.yolo_swipe_dist = QLineEdit("400")
        self.yolo_swipe_ms = QLineEdit("350")
        swipe_form.addRow("方向", self.yolo_swipe_dir)
        swipe_form.addRow("距离 px", self.yolo_swipe_dist)
        swipe_form.addRow("时长 ms", self.yolo_swipe_ms)
        swipe_wrap = QWidget()
        swipe_wrap.setLayout(swipe_form)
        lay.addWidget(swipe_wrap)

        lay.addWidget(section_title("测试与脚本"))
        self._stack_buttons(
            lay,
            [
                ("YOLO 检测", self.run_yolo_detect.emit, "accent"),
                ("生成检测脚本", self.copy_yolo_detect_script.emit, "ghost"),
                ("生成 findYolo 脚本", self.copy_find_yolo_script.emit, "accent"),
                ("生成找类并滑动", self.copy_yolo_swipe_script.emit, "ghost"),
            ],
        )
        lay.addWidget(hint_label("脚本输出在「找图识字」Tab 底部，点复制完整脚本"))
        return w

    def _build_coord_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 12)
        lay.setSpacing(8)

        lay.addWidget(section_title("设备"))
        self.device_combo = QComboBox()
        configure_elide_combo(self.device_combo)
        lay.addWidget(self.device_combo)

        lay.addWidget(section_title("浮动面板取点"))
        lay.addWidget(self._action_btn("拾取面板位置", self.pick_panel.emit))

        lay.addWidget(section_title("按钮坐标"))
        self._stack_buttons(
            lay,
            [
                ("拾取点击坐标", self.pick_tap.emit, "ghost"),
                ("拾取滑动起点", self.pick_swipe1.emit, "ghost"),
                ("拾取滑动终点", self.pick_swipe2.emit, "ghost"),
            ],
        )

        lay.addWidget(section_title("点击测试"))
        self._stack_buttons(
            lay,
            [
                ("ADB 点击测试", self.run_adb_tap.emit, "accent"),
                ("生成点击脚本", self.copy_tap_script.emit, "ghost"),
            ],
        )

        lay.addWidget(section_title("附件目录"))
        dir_row = QHBoxLayout()
        self.image_dir_edit = QLineEdit()
        self.image_dir_edit.setPlaceholderText("image")
        dir_row.addWidget(self.image_dir_edit, 1)
        self._pick_image_dir_btn = QPushButton("…")
        set_button_role(self._pick_image_dir_btn, "ghost")
        self._pick_image_dir_btn.setFixedWidth(32)
        dir_row.addWidget(self._pick_image_dir_btn)
        lay.addLayout(dir_row)
        self.image_dir_hint = QLabel()
        self.image_dir_hint.setObjectName("InfoBar")
        self.image_dir_hint.setWordWrap(True)
        lay.addWidget(self.image_dir_hint)
        self.show_panel_overlay_cb = QCheckBox("显示面板位置预览（虚线）")
        self.show_panel_overlay_cb.setChecked(False)
        lay.addWidget(self.show_panel_overlay_cb)
        return w

    def set_color_preview(self, x: int, y: int, b: int, g: int, r: int, desc: str) -> None:
        self.color_swatch.setStyleSheet(
            f"background: rgb({r},{g},{b});border:1px solid #94A3B8;border-radius:6px;"
        )
        self.color_bgr_label.setText(f"BGR: [{b}, {g}, {r}]")
        self.color_hex_label.setText(f"HEX: #{r:02X}{g:02X}{b:02X}")
        self.color_xy_label.setText(f"坐标: ({x}, {y})")
        self.color_desc_edit.setText(desc)

    def set_roi_fields(self, x: int, y: int, w: int, h: int) -> None:
        self.roi_x1.setText(str(x))
        self.roi_y1.setText(str(y))
        self.roi_x2.setText(str(x + w))
        self.roi_y2.setText(str(y + h))

    def clear_roi_fields(self) -> None:
        for e in (self.roi_x1, self.roi_y1, self.roi_x2, self.roi_y2):
            e.clear()

    def set_yolo_class_names(self, names: list[str]) -> None:
        current = self.yolo_class_combo.currentText()
        self.yolo_class_combo.clear()
        self.yolo_class_combo.addItem("（全部类别）", "")
        for name in names:
            self.yolo_class_combo.addItem(name, name)
        idx = self.yolo_class_combo.findText(current)
        if idx >= 0:
            self.yolo_class_combo.setCurrentIndex(idx)

    def yolo_model_path(self) -> str:
        raw = self.yolo_model_combo.currentData() or self.yolo_model_combo.currentText()
        return str(raw or "").strip()

    def yolo_class_name(self) -> str:
        raw = self.yolo_class_combo.currentData()
        if raw is not None and str(raw) == "":
            return ""
        text = self.yolo_class_combo.currentText().strip()
        if text in ("（全部类别）", ""):
            return ""
        return text

    def yolo_params(self) -> dict:
        return {
            "conf": self._parse_float(self.yolo_conf_edit.text(), 0.35),
            "pick": str(self.yolo_pick_combo.currentData() or "best_conf"),
            "frac": (
                self._parse_float(self.yolo_frac_x.text(), 0.5),
                self._parse_float(self.yolo_frac_y.text(), 0.5),
            ),
            "tap_dx": self._parse_int(self.yolo_tap_dx.text(), 0),
            "tap_dy": self._parse_int(self.yolo_tap_dy.text(), 0),
            "delay_before_click": self._parse_float(self.yolo_delay_edit.text(), 0.0),
            "click": self.yolo_click_cb.isChecked(),
            "direction": str(self.yolo_swipe_dir.currentData() or "up"),
            "distance": self._parse_int(self.yolo_swipe_dist.text(), 400),
            "duration_ms": self._parse_int(self.yolo_swipe_ms.text(), 350),
        }

    @staticmethod
    def _parse_int(text: str, default: int) -> int:
        try:
            return int(text.strip())
        except ValueError:
            return default

    @staticmethod
    def _parse_float(text: str, default: float) -> float:
        try:
            return float(text.strip().replace(",", "."))
        except ValueError:
            return default

    def set_script(self, text: str) -> None:
        self.script_edit.setPlainText(text.strip())

    def append_color_record(self, index: int, x: int, y: int, b: int, g: int, r: int) -> None:
        row = self.color_table.rowCount()
        self.color_table.insertRow(row)
        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        for col, val in enumerate([str(index), f"({x},{y})", f"[{b},{g},{r}]", hex_color]):
            self.color_table.setItem(row, col, QTableWidgetItem(val))

    def clear_color_records(self) -> None:
        self.color_table.setRowCount(0)

    def remove_selected_color_records(self) -> list[int]:
        rows = sorted({i.row() for i in self.color_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.color_table.removeRow(row)
        return rows
