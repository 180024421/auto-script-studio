"""脚本页左侧命令工具箱（对齐按键精灵「基本命令」交互）。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

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
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from studio.services import lua_snippets
from studio.services.project_images import image_rel_path, list_images
from studio.services.yolo_models import (
    default_model_path,
    list_yolo_models,
    load_class_names,
    model_rel_path as yolo_model_rel_path,
)
from studio.ui.app_theme import set_button_role
from studio.ui.page_shell import hint_label, section_title
from studio.ui.script_all_commands_widget import ScriptAllCommandsWidget


class _CommandCard(QFrame):
    """单条命令卡片，支持搜索过滤。"""

    def __init__(self, title: str, keywords: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandCard")
        self._search_blob = f"{title} {keywords}".lower()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("SectionTitle")
        lay.addWidget(self.title_label)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        lay.addLayout(self.body)

    def matches(self, query: str) -> bool:
        if not query:
            return True
        return query in self._search_blob


class ScriptCommandToolbox(QWidget):
    """可视化生成 bot API 代码。"""

    insert_code = Signal(str)
    copy_code = Signal(str)

    def __init__(self, project_dir_getter: Callable[[], Path | None]) -> None:
        super().__init__()
        self._project_dir_getter = project_dir_getter
        self._command_cards: list[_CommandCard] = []
        self.setMinimumWidth(240)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.setObjectName("CommandModeTabs")
        self.mode_tabs.setDocumentMode(True)
        self.mode_tabs.addTab(self._build_basic_page(), "基本命令")
        self.all_commands = ScriptAllCommandsWidget()
        self.all_commands.insert_code.connect(self.insert_code.emit)
        self.all_commands.copy_code.connect(self.copy_code.emit)
        self.mode_tabs.addTab(self.all_commands, "全部命令")
        root.addWidget(self.mode_tabs, 1)

    def _build_basic_page(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        root.addWidget(section_title("基本命令"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索命令（找图、控件、YOLO、滑动、ROI…）")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_search_filter)
        root.addWidget(self.search_edit)

        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(4)

        self.toolbox = QToolBox()
        self.toolbox.setObjectName("ScriptCommandToolbox")
        self.toolbox.addItem(self._build_touch_tab(), "触控")
        self.toolbox.addItem(self._build_vision_tab(), "图色")
        self.toolbox.addItem(self._build_node_tab(), "控件")
        self.toolbox.addItem(self._build_yolo_tab(), "YOLO")
        self.toolbox.addItem(self._build_other_tab(), "其它")
        inner_lay.addWidget(self.toolbox)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)
        root.addWidget(
            hint_label("插入：光标处 · 复制：剪贴板\nROI 宽高 0=全屏 · 「找到后点击」控制是否 click"),
        )
        return page

    def refresh_templates(self) -> None:
        if not hasattr(self, "_template_combo"):
            return
        current = self._template_combo.currentData() or self._template_combo.currentText()
        self._template_combo.clear()
        self._template_combo.addItem("image/模板.png", "image/模板.png")
        project = self._project_dir_getter()
        if project:
            for path in list_images(Path(project)):
                rel = image_rel_path(Path(project), path)
                self._template_combo.addItem(path.name, rel)
        idx = self._template_combo.findData(current)
        if idx >= 0:
            self._template_combo.setCurrentIndex(idx)

    def _register_card(self, parent_lay: QVBoxLayout, card: _CommandCard) -> None:
        parent_lay.addWidget(card)
        self._command_cards.append(card)

    def _action_buttons(self, parent: QVBoxLayout, on_snippet: Callable[[], str]) -> None:
        row = QHBoxLayout()
        insert_btn = QPushButton("插入")
        set_button_role(insert_btn, "accent")
        copy_btn = QPushButton("复制")
        set_button_role(copy_btn, "ghost")
        insert_btn.clicked.connect(lambda: self.insert_code.emit(on_snippet()))
        copy_btn.clicked.connect(lambda: self.copy_code.emit(on_snippet()))
        row.addWidget(insert_btn)
        row.addWidget(copy_btn)
        row.addStretch()
        parent.addLayout(row)

    def _click_checkbox(self, parent: QVBoxLayout, *, checked: bool = False) -> QCheckBox:
        cb = QCheckBox("找到后点击")
        cb.setChecked(checked)
        parent.addWidget(cb)
        return cb

    def _int_field(self, default: str, *, width: int = 72) -> QLineEdit:
        e = QLineEdit(default)
        e.setAlignment(Qt.AlignmentFlag.AlignRight)
        e.setMaximumWidth(width)
        return e

    def _roi_fields(self) -> tuple[QLineEdit, QLineEdit, QLineEdit, QLineEdit]:
        return (
            self._int_field("0"),
            self._int_field("0"),
            self._int_field("0"),
            self._int_field("0"),
        )

    def _add_roi_form(self, parent: QVBoxLayout, fields: tuple[QLineEdit, ...]) -> None:
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        labels = ("区域 X", "区域 Y", "区域宽 W", "区域高 H")
        for label, edit in zip(labels, fields):
            form.addRow(label, edit)
        wrap = QWidget()
        wrap.setLayout(form)
        parent.addWidget(wrap)

    def _parse_roi(
        self,
        x: QLineEdit,
        y: QLineEdit,
        w: QLineEdit,
        h: QLineEdit,
    ) -> Optional[tuple[int, int, int, int]]:
        vals = [self._parse_int(e.text(), -1) for e in (x, y, w, h)]
        if any(v < 0 for v in vals):
            return None
        if vals[2] <= 0 or vals[3] <= 0:
            return None
        return vals[0], vals[1], vals[2], vals[3]

    def _build_touch_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(10)

        tap_card = _CommandCard("点击", "tap 触控 坐标")
        tap_form = QFormLayout()
        tap_x = self._int_field("0")
        tap_y = self._int_field("0")
        tap_form.addRow("X", tap_x)
        tap_form.addRow("Y", tap_y)
        tap_wrap = QWidget()
        tap_wrap.setLayout(tap_form)
        tap_card.body.addWidget(tap_wrap)
        self._action_buttons(
            tap_card.body,
            lambda: lua_snippets.tap(
                self._parse_int(tap_x.text(), 0),
                self._parse_int(tap_y.text(), 0),
            ),
        )
        self._register_card(lay, tap_card)

        lp_card = _CommandCard("长按", "longPress 触控")
        lp_form = QFormLayout()
        lp_x = self._int_field("0")
        lp_y = self._int_field("0")
        lp_ms = self._int_field("500")
        lp_form.addRow("X", lp_x)
        lp_form.addRow("Y", lp_y)
        lp_form.addRow("时长 ms", lp_ms)
        lp_wrap = QWidget()
        lp_wrap.setLayout(lp_form)
        lp_card.body.addWidget(lp_wrap)
        self._action_buttons(
            lp_card.body,
            lambda: lua_snippets.long_press(
                self._parse_int(lp_x.text(), 0),
                self._parse_int(lp_y.text(), 0),
                duration_ms=self._parse_int(lp_ms.text(), 500),
            ),
        )
        self._register_card(lay, lp_card)

        sw_card = _CommandCard("滑动", "swipe 划动")
        sw_form = QFormLayout()
        sw_x1 = self._int_field("0")
        sw_y1 = self._int_field("0")
        sw_x2 = self._int_field("100")
        sw_y2 = self._int_field("100")
        sw_ms = self._int_field("300")
        for label, edit in [
            ("起点 X1", sw_x1),
            ("起点 Y1", sw_y1),
            ("终点 X2", sw_x2),
            ("终点 Y2", sw_y2),
            ("时长 ms", sw_ms),
        ]:
            sw_form.addRow(label, edit)
        sw_wrap = QWidget()
        sw_wrap.setLayout(sw_form)
        sw_card.body.addWidget(sw_wrap)
        self._action_buttons(
            sw_card.body,
            lambda: lua_snippets.swipe(
                self._parse_int(sw_x1.text(), 0),
                self._parse_int(sw_y1.text(), 0),
                self._parse_int(sw_x2.text(), 100),
                self._parse_int(sw_y2.text(), 100),
                duration_ms=self._parse_int(sw_ms.text(), 300),
            ),
        )
        self._register_card(lay, sw_card)
        lay.addStretch()
        return w

    def _build_vision_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(10)

        # —— 找色（ROI 留空或 0 = 全屏）——
        fc_card = _CommandCard("找色", "findColor 找色 颜色 区域 roi click")
        fb, fg, fr, ftol = (
            self._int_field("0"),
            self._int_field("0"),
            self._int_field("0"),
            self._int_field("15"),
        )
        form = QFormLayout()
        form.addRow("B", fb)
        form.addRow("G", fg)
        form.addRow("R", fr)
        form.addRow("容差", ftol)
        fc_card.body.addWidget(self._form_wrap(form))
        rx, ry, rw, rh = self._roi_fields()
        self._add_roi_form(fc_card.body, (rx, ry, rw, rh))
        fc_card.body.addWidget(hint_label("区域宽高为 0 表示全屏搜索"))
        fc_click = self._click_checkbox(fc_card.body)
        self._register_card(lay, fc_card)
        self._action_buttons(
            fc_card.body,
            lambda: lua_snippets.find_color(
                (
                    self._parse_int(fb.text(), 0),
                    self._parse_int(fg.text(), 0),
                    self._parse_int(fr.text(), 0),
                ),
                tol=self._parse_int(ftol.text(), 15),
                roi=self._parse_roi(rx, ry, rw, rh),
                click=fc_click.isChecked(),
            ),
        )

        # —— 找图 ——
        fi_card = _CommandCard("找图", "findImage 找图 模板 区域 roi click")
        self._template_combo = QComboBox()
        self._template_combo.setEditable(True)
        fi_card.body.addWidget(QLabel("模板路径"))
        fi_card.body.addWidget(self._template_combo)
        fi_thr = self._int_field("0.90")
        fi_thr.setMaximumWidth(120)
        thr_form = QFormLayout()
        thr_form.addRow("相似度", fi_thr)
        fi_card.body.addWidget(self._form_wrap(thr_form))
        rx2, ry2, rw2, rh2 = self._roi_fields()
        self._add_roi_form(fi_card.body, (rx2, ry2, rw2, rh2))
        fi_click = self._click_checkbox(fi_card.body)
        self._register_card(lay, fi_card)
        self._action_buttons(
            fi_card.body,
            lambda: self._find_image_snippet(
                fi_thr,
                self._parse_roi(rx2, ry2, rw2, rh2),
                click=fi_click.isChecked(),
            ),
        )

        # —— 识字 ——
        ft_card = _CommandCard("识字", "findText 文字 ocr 区域 roi click")
        ft_text = QLineEdit()
        ft_text.setPlaceholderText("目标文字")
        ft_mode = QComboBox()
        ft_mode.addItem("包含匹配", "contains")
        ft_mode.addItem("完全匹配", "exact")
        ft_form = QFormLayout()
        ft_form.addRow("文字", ft_text)
        ft_form.addRow("模式", ft_mode)
        ft_card.body.addWidget(self._form_wrap(ft_form))
        rx3, ry3, rw3, rh3 = self._roi_fields()
        self._add_roi_form(ft_card.body, (rx3, ry3, rw3, rh3))
        ft_click = self._click_checkbox(ft_card.body)
        self._register_card(lay, ft_card)
        self._action_buttons(
            ft_card.body,
            lambda: lua_snippets.find_text(
                ft_text.text().strip() or "确定",
                match_mode=str(ft_mode.currentData() or "contains"),
                roi=self._parse_roi(rx3, ry3, rw3, rh3),
                click=ft_click.isChecked(),
            ),
        )

        lay.addStretch()
        self.refresh_templates()
        return w

    def _form_wrap(self, form: QFormLayout) -> QWidget:
        wrap = QWidget()
        wrap.setLayout(form)
        return wrap

    def _find_image_snippet(
        self,
        thr_edit: QLineEdit,
        roi: Optional[tuple[int, int, int, int]],
        *,
        click: bool = False,
    ) -> str:
        path = self._template_combo.currentData() or self._template_combo.currentText()
        path = str(path or "image/模板.png").strip()
        thr_text = thr_edit.text().strip().replace(",", ".")
        try:
            thr = float(thr_text)
            if thr > 1:
                thr /= 100.0
        except ValueError:
            thr = 0.9
        return lua_snippets.find_image(path, threshold=thr, roi=roi, click=click)

    def refresh_yolo_models(self) -> None:
        if not hasattr(self, "_yolo_model_combo"):
            return
        project = self._project_dir_getter()
        current = self._yolo_model_combo.currentData()
        self._yolo_model_combo.clear()
        self._yolo_class_combo.clear()
        self._yolo_class_combo.addItem("（全部）", "")
        if not project:
            return
        for path in list_yolo_models(Path(project)):
            rel = yolo_model_rel_path(Path(project), path)
            self._yolo_model_combo.addItem(path.name, rel)
            for cls in load_class_names(path):
                if self._yolo_class_combo.findData(cls) < 0:
                    self._yolo_class_combo.addItem(cls, cls)
        default = default_model_path(Path(project))
        if default:
            rel = yolo_model_rel_path(Path(project), default)
            idx = self._yolo_model_combo.findData(rel)
            if idx >= 0:
                self._yolo_model_combo.setCurrentIndex(idx)
        elif current:
            idx = self._yolo_model_combo.findData(current)
            if idx >= 0:
                self._yolo_model_combo.setCurrentIndex(idx)

    def _yolo_model_rel(self) -> str:
        raw = self._yolo_model_combo.currentData() or self._yolo_model_combo.currentText()
        return str(raw or "models/ui.onnx").strip()

    def _yolo_class(self) -> str:
        raw = self._yolo_class_combo.currentData()
        if raw is not None and str(raw) == "":
            return ""
        text = self._yolo_class_combo.currentText().strip()
        return "" if text in ("（全部）", "") else text

    def _build_node_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(10)

        node_card = _CommandCard("找控件", "findNode 无障碍 text id 控件")
        nform = QFormLayout()
        node_text = QLineEdit()
        node_text.setPlaceholderText("控件文字，如 设置")
        node_id = QLineEdit()
        node_id.setPlaceholderText("resource-id，可留空")
        node_mode = QComboBox()
        node_mode.addItem("包含", "contains")
        node_mode.addItem("完全匹配", "equals")
        node_mode.addItem("开头", "starts_with")
        node_timeout = self._int_field("10")
        node_timeout.setMaximumWidth(120)
        nform.addRow("文字", node_text)
        nform.addRow("ID", node_id)
        nform.addRow("匹配", node_mode)
        nform.addRow("超时秒", node_timeout)
        nwrap = QWidget()
        nwrap.setLayout(nform)
        node_card.body.addWidget(nwrap)
        node_click = self._click_checkbox(node_card.body)
        node_optional = QCheckBox("找不到不报错（optional）")
        node_optional.setChecked(True)
        node_card.body.addWidget(node_optional)
        node_card.body.addWidget(hint_label("仅 APK + 无障碍可用；PC 运行请勾选 optional"))
        self._register_card(lay, node_card)
        self._action_buttons(
            node_card.body,
            lambda: lua_snippets.find_node(
                text=node_text.text().strip(),
                resource_id=node_id.text().strip(),
                match_mode=str(node_mode.currentData() or "contains"),
                timeout=self._parse_float(node_timeout.text(), 10.0),
                click=node_click.isChecked(),
                optional=node_optional.isChecked(),
            ),
        )
        lay.addStretch()
        return w

    def _build_yolo_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(10)

        lay.addWidget(QLabel("模型 / 类别"))
        self._yolo_model_combo = QComboBox()
        self._yolo_model_combo.setEditable(True)
        lay.addWidget(self._yolo_model_combo)
        self._yolo_class_combo = QComboBox()
        self._yolo_class_combo.setEditable(True)
        lay.addWidget(self._yolo_class_combo)

        shared_form = QFormLayout()
        self._yolo_conf = self._int_field("0.35")
        self._yolo_conf.setMaximumWidth(120)
        self._yolo_pick = QComboBox()
        self._yolo_pick.addItem("最高置信度", "best_conf")
        self._yolo_pick.addItem("最大框", "largest")
        self._yolo_frac_x = self._int_field("0.5")
        self._yolo_frac_y = self._int_field("0.5")
        self._yolo_frac_x.setMaximumWidth(120)
        self._yolo_frac_y.setMaximumWidth(120)
        shared_form.addRow("置信度", self._yolo_conf)
        shared_form.addRow("选取", self._yolo_pick)
        shared_form.addRow("点击 X%", self._yolo_frac_x)
        shared_form.addRow("点击 Y%", self._yolo_frac_y)
        shared_wrap = QWidget()
        shared_wrap.setLayout(shared_form)
        lay.addWidget(shared_wrap)

        def _frac() -> tuple[float, float]:
            return (
                self._parse_float(self._yolo_frac_x.text(), 0.5),
                self._parse_float(self._yolo_frac_y.text(), 0.5),
            )

        def _conf() -> float:
            return self._parse_float(self._yolo_conf.text(), 0.35)

        def _pick() -> str:
            return str(self._yolo_pick.currentData() or "best_conf")

        det_card = _CommandCard("YOLO 检测列表", "yoloDetect 检测 yolo")
        self._register_card(lay, det_card)
        self._action_buttons(
            det_card.body,
            lambda: lua_snippets.yolo_detect(
                self._yolo_model_rel(),
                class_name=self._yolo_class(),
                conf=_conf(),
            ),
        )

        find_card = _CommandCard("找 YOLO 类", "findYolo 找类 坐标 click 点击 偏移")
        rx, ry, rw, rh = self._roi_fields()
        self._add_roi_form(find_card.body, (rx, ry, rw, rh))
        yolo_click = self._click_checkbox(find_card.body)
        cdx = self._int_field("0")
        cdy = self._int_field("0")
        cdelay = self._int_field("0")
        for e in (cdx, cdy, cdelay):
            e.setMaximumWidth(120)
        cform = QFormLayout()
        cform.addRow("偏移 dx", cdx)
        cform.addRow("偏移 dy", cdy)
        cform.addRow("延迟秒", cdelay)
        find_card.body.addWidget(self._form_wrap(cform))
        find_card.body.addWidget(hint_label("勾选「找到后点击」时生效偏移/延迟；ROI 宽高 0=全屏"))
        self._register_card(lay, find_card)
        self._action_buttons(
            find_card.body,
            lambda: lua_snippets.find_yolo(
                self._yolo_model_rel(),
                class_name=self._yolo_class(),
                conf=_conf(),
                pick=_pick(),
                roi=self._parse_roi(rx, ry, rw, rh),
                frac=_frac(),
                tap_dx=self._parse_int(cdx.text(), 0),
                tap_dy=self._parse_int(cdy.text(), 0),
                delay_before_click=self._parse_float(cdelay.text(), 0.0),
                click=yolo_click.isChecked(),
                optional=True,
            ),
        )

        swipe_card = _CommandCard("找类并滑动", "yoloSwipe 滑动")
        sdir = QComboBox()
        sdir.addItem("向上", "up")
        sdir.addItem("向下", "down")
        sdir.addItem("向左", "left")
        sdir.addItem("向右", "right")
        sdist = self._int_field("400")
        sms = self._int_field("350")
        sform = QFormLayout()
        sform.addRow("方向", sdir)
        sform.addRow("距离", sdist)
        sform.addRow("时长ms", sms)
        swrap = QWidget()
        swrap.setLayout(sform)
        swipe_card.body.addWidget(swrap)
        self._register_card(lay, swipe_card)
        self._action_buttons(
            swipe_card.body,
            lambda: lua_snippets.yolo_swipe(
                self._yolo_model_rel(),
                class_name=self._yolo_class() or "hand",
                conf=_conf(),
                pick=_pick(),
                frac=_frac(),
                direction=str(sdir.currentData() or "up"),
                distance=self._parse_int(sdist.text(), 400),
                duration_ms=self._parse_int(sms.text(), 350),
            ),
        )
        lay.addStretch()
        self.refresh_yolo_models()
        return w

    def _build_other_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(10)

        delay_card = _CommandCard("等待", "delay 延时 暂停")
        delay_sec = self._int_field("1")
        delay_sec.setMaximumWidth(120)
        d_form = QFormLayout()
        d_form.addRow("秒", delay_sec)
        d_wrap = QWidget()
        d_wrap.setLayout(d_form)
        delay_card.body.addWidget(d_wrap)
        self._action_buttons(
            delay_card.body,
            lambda: lua_snippets.delay(self._parse_float(delay_sec.text(), 1.0)),
        )
        self._register_card(lay, delay_card)

        log_card = _CommandCard("输出日志", "log 打印")
        log_edit = QLineEdit()
        log_edit.setPlaceholderText("日志内容")
        log_card.body.addWidget(log_edit)
        self._action_buttons(
            log_card.body,
            lambda: lua_snippets.log_message(log_edit.text().strip() or "消息"),
        )
        self._register_card(lay, log_card)
        lay.addStretch()
        return w

    def _apply_search_filter(self, text: str) -> None:
        query = text.strip().lower()
        for card in self._command_cards:
            card.setVisible(card.matches(query))
        for i in range(self.toolbox.count()):
            if not query:
                self.toolbox.setItemEnabled(i, True)
                continue
            page = self.toolbox.widget(i)
            if page is None:
                continue
            visible = any(c.isVisible() for c in page.findChildren(_CommandCard))
            self.toolbox.setItemEnabled(i, visible)
            if visible and self.toolbox.currentIndex() != i:
                self.toolbox.setCurrentIndex(i)
                break

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
