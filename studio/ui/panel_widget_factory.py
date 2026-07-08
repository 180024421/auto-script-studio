"""画布/预览共用：构建可交互表单控件（左标签 · 右控件）。"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from studio.runtime.panel_state import PanelState

OnChange = Callable[[], None] | None

INTERACTIVE_TYPES = frozenset(
    {
        "input",
        "select",
        "radio",
        "multiselect",
        "switch",
        "time_range",
        "slider",
        "stepper",
        "textarea",
    }
)

FORM_PREVIEW_TYPES = INTERACTIVE_TYPES | frozenset({"label", "text", "divider"})

_CONTROL_HINTS: dict[str, str] = {
    "input": "输入框",
    "select": "下拉选择",
    "radio": "单选",
    "multiselect": "多选",
    "switch": "开关",
    "time_range": "时段",
    "slider": "滑条",
    "stepper": "步进",
    "textarea": "多行文本",
}


_FIELD_CTRL_STYLE = (
    "QLineEdit, QComboBox, QTextEdit {"
    "padding: 2px 6px; border: 1px solid #CBD5E1; border-radius: 4px; background: #FFFFFF;"
    "}"
    "QLineEdit:focus, QComboBox:focus, QTextEdit:focus { border-color: #2563EB; }"
)

_FIELD_COMBO_STYLE = (
    _FIELD_CTRL_STYLE
    + """
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    border-left: 1px solid #CBD5E1;
    background: #F8FAFC;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}
QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #64748B;
}
"""
)

def _switch_style(scale: float = 1.0) -> str:
    s = max(0.45, min(1.0, float(scale)))
    w = max(28, int(44 * s))
    h = max(16, int(24 * s))
    radius = max(8, h // 2)
    return f"""
#PanelSwitch {{ spacing: 0; background: transparent; }}
#PanelSwitch::indicator {{
    width: {w}px;
    height: {h}px;
    border-radius: {radius}px;
    border: 1px solid #94A3B8;
    background: #E2E8F0;
}}
#PanelSwitch::indicator:checked {{
    background: #2563EB;
    border-color: #1D4ED8;
}}
#PanelSwitch::indicator:disabled {{
    background: #F1F5F9;
    border-color: #CBD5E1;
}}
"""


def _options_list(spec: dict[str, Any]) -> list[str]:
    raw = spec.get("options")
    if raw is None:
        from studio.services.layout_defaults import DEFAULT_WIDGET_OPTIONS

        return list(DEFAULT_WIDGET_OPTIONS)
    return [str(o) for o in raw]


def _make_switch(*, checked: bool = False, enabled: bool = True, scale: float = 1.0) -> QCheckBox:
    sw = QCheckBox()
    sw.setObjectName("PanelSwitch")
    sw.setText("")
    sw.setStyleSheet(_switch_style(scale))
    sw.setFixedWidth(max(28, int(48 * max(0.45, min(1.0, float(scale))))))
    sw.setChecked(checked)
    sw.setEnabled(enabled)
    return sw


def _multiselect_options(
    opts: list[str],
    selected: set[str],
    *,
    wid: str = "",
    on_change: OnChange = None,
    interactive: bool = True,
) -> QWidget:
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(12)

    def sync() -> None:
        if not wid:
            return
        checked = []
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if isinstance(w, QCheckBox) and w.isChecked():
                checked.append(w.text())
        PanelState.set(wid, ",".join(checked))
        if on_change:
            on_change()

    for opt in opts:
        cb = QCheckBox(opt)
        cb.setChecked(opt in selected)
        cb.setEnabled(interactive)
        if interactive and wid:
            cb.toggled.connect(lambda _on: sync())
        lay.addWidget(cb)
    lay.addStretch(1)
    return host


def _scaled_px(base: int, scale: float, *, floor: int = 12) -> int:
    s = max(0.35, min(1.0, float(scale)))
    return max(floor, int(base * s))


def _font_px(base: int, scale: float) -> int:
    s = max(0.45, min(1.0, float(scale)))
    return max(8, int(base * s))


def _label_width(text: str, scale: float = 1.0) -> int:
    t = text.strip()
    if not t:
        return 0
    raw = min(72, max(40, len(t) * 12 + 10))
    return _scaled_px(raw, scale, floor=28)


def _default_row_h(scale: float, container_h: int | None = None) -> int:
    h = _scaled_px(32, scale, floor=24)
    if container_h is not None and container_h > 0:
        return min(h, container_h)
    return h


def _style_line_edit(edit: QLineEdit, *, scale: float, row_h: int) -> None:
    edit.setObjectName("PanelField")
    fs = _font_px(12, scale)
    edit.setMinimumHeight(row_h)
    edit.setMaximumHeight(row_h)
    edit.setStyleSheet(
        f"QLineEdit#PanelField {{ font-size:{fs}px; padding:0 4px; "
        f"border:1px solid #CBD5E1; border-radius:3px; background:#FFF; }}"
    )


def _style_combo(cb: QComboBox, *, scale: float, row_h: int) -> None:
    cb.setObjectName("PanelField")
    fs = _font_px(12, scale)
    cb.setMinimumHeight(row_h)
    cb.setMaximumHeight(row_h)
    cb.setStyleSheet(
        f"QComboBox#PanelField {{ font-size:{fs}px; padding:0 4px; "
        f"border:1px solid #CBD5E1; border-radius:3px; background:#FFF; }}"
        "QComboBox#PanelField::drop-down { width:22px; border:none; "
        "border-left:1px solid #CBD5E1; background:#F8FAFC; }"
    )


def _style_spin(sp: QSpinBox, *, scale: float, row_h: int) -> None:
    sp.setObjectName("PanelField")
    fs = _font_px(12, scale)
    sp.setMinimumHeight(row_h)
    sp.setMaximumHeight(row_h)
    sp.setStyleSheet(
        f"QSpinBox#PanelField {{ font-size:{fs}px; padding:0 4px; "
        f"border:1px solid #CBD5E1; border-radius:3px; background:#FFF; }}"
    )


def _style_radio(rb: QRadioButton, *, scale: float) -> None:
    fs = _font_px(12, scale)
    ind = max(12, int(14 * max(0.45, min(1.0, scale))))
    rb.setStyleSheet(
        f"QRadioButton {{ font-size:{fs}px; spacing:4px; color:#334155; }}"
        f"QRadioButton::indicator {{ width:{ind}px; height:{ind}px; }}"
    )


def _style_slider(slider: QSlider, *, scale: float, row_h: int) -> None:
    slider.setFixedHeight(row_h)


def _build_radio_group(
    spec: dict[str, Any],
    *,
    scale: float,
    container_h: int | None,
    current: str,
    interactive: bool,
    wid: str = "",
    on_change: OnChange = None,
) -> QWidget:
    opts = [str(o) for o in (spec.get("options") or ["选项A", "选项B"])]
    row_h = _default_row_h(scale, container_h)
    group_host = QWidget()
    group_lay = QHBoxLayout(group_host)
    group_lay.setContentsMargins(0, 0, 0, 0)
    group_lay.setSpacing(max(4, _scaled_px(8, scale, floor=4)))
    for opt in opts:
        rb = QRadioButton(opt)
        _style_radio(rb, scale=scale)
        rb.setFixedHeight(row_h)
        rb.setChecked(opt == current or (not current and opt == opts[0]))
        rb.setEnabled(interactive)
        if interactive and wid:
            rb.toggled.connect(
                lambda on, i=wid, o=opt: (PanelState.set(i, o), on_change()) if on and on_change else None
            )
        group_lay.addWidget(rb)
    group_lay.addStretch(1)
    return group_host


def _build_time_range(
    spec: dict[str, Any],
    *,
    scale: float,
    container_h: int | None,
    start_text: str,
    end_text: str,
    interactive: bool,
    wid: str = "",
    on_change: OnChange = None,
) -> QWidget:
    row_h = _default_row_h(scale, container_h)
    start = QLineEdit(start_text)
    end = QLineEdit(end_text)
    start.setReadOnly(not interactive)
    end.setReadOnly(not interactive)
    _style_line_edit(start, scale=scale, row_h=row_h)
    _style_line_edit(end, scale=scale, row_h=row_h)
    fs = _font_px(11, scale)

    def sync() -> None:
        if wid:
            PanelState.set(wid, f"{start.text().strip()}-{end.text().strip()}")
        if on_change:
            on_change()

    if interactive and wid:
        start.textChanged.connect(lambda _t: sync())
        end.textChanged.connect(lambda _t: sync())

    host = QWidget()
    inner = QHBoxLayout(host)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(max(2, _scaled_px(4, scale, floor=2)))
    for text, widget in (("从", start), ("到", end)):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:#64748B;font-size:{fs}px;background:transparent;")
        inner.addWidget(lbl)
        inner.addWidget(widget, 1)
    return host


def _build_slider(
    spec: dict[str, Any],
    *,
    scale: float,
    container_h: int | None,
    value: int,
    interactive: bool,
    wid: str = "",
    on_change: OnChange = None,
) -> QSlider:
    lo = int(spec.get("min", 0) or 0)
    hi = int(spec.get("max", 100) or 100)
    row_h = _default_row_h(scale, container_h)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(lo, hi)
    slider.setValue(max(lo, min(hi, value)))
    slider.setEnabled(interactive)
    _style_slider(slider, scale=scale, row_h=row_h)
    if interactive and wid:
        slider.valueChanged.connect(lambda v, i=wid: (PanelState.set(i, str(v)), on_change()))
    return slider


def _build_stepper(
    spec: dict[str, Any],
    *,
    scale: float,
    container_h: int | None,
    value: int,
    interactive: bool,
    wid: str = "",
    on_change: OnChange = None,
) -> QSpinBox:
    lo = int(spec.get("min", 0) or 0)
    hi = int(spec.get("max", 99) or 99)
    row_h = _default_row_h(scale, container_h)
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(max(lo, min(hi, value)))
    sp.setEnabled(interactive)
    sp.setButtonSymbols(
        QSpinBox.ButtonSymbols.UpDownArrows if interactive else QSpinBox.ButtonSymbols.NoButtons
    )
    _style_spin(sp, scale=scale, row_h=row_h)
    if interactive and wid:
        sp.valueChanged.connect(lambda v, i=wid: (PanelState.set(i, str(v)), on_change()))
    return sp


def _build_textarea(
    spec: dict[str, Any],
    *,
    scale: float,
    container_h: int | None,
    text: str,
    interactive: bool,
    wid: str = "",
    on_change: OnChange = None,
) -> QTextEdit:
    te = QTextEdit()
    te.setObjectName("PanelField")
    te.setPlaceholderText(str(spec.get("placeholder", "")))
    te.setPlainText(text)
    te.setReadOnly(not interactive)
    if container_h is not None and container_h > 0:
        te.setMaximumHeight(container_h)
        te.setMinimumHeight(min(container_h, _default_row_h(scale, container_h)))
    else:
        rows = int(spec.get("rows", 3) or 3)
        te.setMaximumHeight(max(_scaled_px(48, scale, floor=24), rows * _scaled_px(22, scale, floor=14)))
    fs = _font_px(12, scale)
    te.setStyleSheet(
        f"QTextEdit#PanelField {{ font-size:{fs}px; padding:2px 4px; "
        f"border:1px solid #CBD5E1; border-radius:3px; background:#FFF; }}"
    )
    if interactive and wid:
        te.textChanged.connect(lambda i=wid, w=te: (PanelState.set(i, w.toPlainText()), on_change()))
    return te


def _row_height(scale: float, control: QWidget, container_h: int | None = None) -> int:
    base = _default_row_h(scale, container_h)
    hint = control.sizeHint().height()
    if hint > 0:
        base = min(base, hint) if container_h is None else min(base, hint, container_h)
    return base


def _form_row(
    label: str,
    control: QWidget,
    *,
    label_width: int | None = None,
    scale: float = 1.0,
    container_h: int | None = None,
) -> QWidget:
    host = QWidget()
    host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    lay = QHBoxLayout(host)
    m = max(0, _scaled_px(4, scale, floor=0))
    lay.setContentsMargins(m, 0, m, 0)
    lay.setSpacing(max(2, _scaled_px(4, scale, floor=2)))
    row_h = _row_height(scale, control, container_h)
    host.setMinimumHeight(row_h)
    if container_h is not None and container_h > 0:
        host.setMaximumHeight(container_h)
    if label:
        lbl = QLabel(label)
        lbl.setFixedWidth(label_width if label_width is not None else _label_width(label, scale))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        fs = _font_px(12, scale)
        lbl.setStyleSheet(f"color:#475569;font-size:{fs}px;background:transparent;padding:0;")
        lay.addWidget(lbl)
    control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    fixed_height = isinstance(control, (QLineEdit, QComboBox, QFrame, QSpinBox, QSlider))
    if fixed_height:
        if not isinstance(control, (QSlider,)):
            if isinstance(control, QLineEdit):
                _style_line_edit(control, scale=scale, row_h=row_h)
            elif isinstance(control, QComboBox):
                _style_combo(control, scale=scale, row_h=row_h)
            elif isinstance(control, QSpinBox):
                _style_spin(control, scale=scale, row_h=row_h)
            else:
                control.setMinimumHeight(row_h)
                control.setMaximumHeight(row_h)
        else:
            _style_slider(control, scale=scale, row_h=row_h)
    elif isinstance(control, QTextEdit):
        if container_h is not None and container_h > 0:
            control.setMaximumHeight(container_h)
        control.setMinimumHeight(min(row_h, container_h or row_h))
    else:
        control.setMinimumHeight(min(row_h, container_h or row_h))
        if container_h is not None and container_h > 0:
            control.setMaximumHeight(container_h)
    lay.addWidget(control, 1)
    return host


def _control_box(text: str = "", *, scale: float = 1.0) -> QFrame:
    box = QFrame()
    row_h = _scaled_px(32, scale, floor=24)
    box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    box.setStyleSheet(
        "QFrame { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:4px; }"
    )
    box.setMinimumHeight(row_h)
    box.setMaximumHeight(row_h)
    inner = QLabel(text)
    inner.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    fs = _font_px(11, scale)
    inner.setStyleSheet(f"color:#94A3B8;font-size:{fs}px;border:none;background:transparent;")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(4, 0, 4, 0)
    lay.addWidget(inner, 1)
    return box


def _input_preview_widget(placeholder: str = "", *, scale: float = 1.0) -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder or "请输入…")
    edit.setReadOnly(True)
    row_h = _default_row_h(scale)
    _style_line_edit(edit, scale=scale, row_h=row_h)
    return edit


def _select_preview_widget(spec: dict[str, Any], *, scale: float = 1.0) -> QComboBox:
    cb = QComboBox()
    opts = _options_list(spec) if spec.get("options") is not None else ["选项1", "选项2"]
    if not opts:
        opts = ["请选择"]
    cb.addItems(opts)
    cur = str(spec.get("default") or opts[0])
    idx = cb.findText(cur)
    if idx >= 0:
        cb.setCurrentIndex(idx)
    cb.setEnabled(False)
    row_h = _default_row_h(scale)
    _style_combo(cb, scale=scale, row_h=row_h)
    return cb


def _divider_line_widget(*, scale: float = 1.0) -> QWidget:
    host = QWidget()
    lay = QVBoxLayout(host)
    lay.setContentsMargins(8, 0, 8, 0)
    lay.setSpacing(0)
    lay.addStretch(1)
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet("background:#CBD5E1;border:none;")
    lay.addWidget(line)
    lay.addStretch(1)
    return host


def _text_display_widget(spec: dict[str, Any], *, scale: float = 1.0) -> QLabel:
    content = str(spec.get("text") or spec.get("label") or "提示文字")
    style = str(spec.get("text_style") or "normal").lower()
    host = QLabel(content)
    host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    host.setWordWrap(True)
    align = str(spec.get("align") or "left").lower()
    qt_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
    if align == "center":
        qt_align = Qt.AlignmentFlag.AlignCenter
    elif align == "right":
        qt_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
    host.setAlignment(qt_align)
    pad = _scaled_px(8, scale, floor=2)
    if style == "title":
        fs = _font_px(14, scale)
        host.setStyleSheet(
            f"color:#1E293B;font-weight:700;font-size:{fs}px;padding:{pad}px {pad + 4}px;"
            "background:transparent;"
        )
    elif style == "hint":
        fs = _font_px(11, scale)
        host.setStyleSheet(
            f"color:#64748B;font-size:{fs}px;padding:{pad}px {pad + 4}px;background:transparent;"
        )
    else:
        fs = _font_px(12, scale)
        host.setStyleSheet(
            f"color:#334155;font-size:{fs}px;padding:{pad}px {pad + 4}px;background:transparent;"
        )
    return host


def build_design_preview(
    spec: dict[str, Any], *, scale: float = 1.0, container_h: int | None = None
) -> QWidget | None:
    """非交互画布：与交互预览同结构，只读/禁用。"""
    wtype = spec.get("type", "")
    if wtype == "divider":
        return _divider_line_widget(scale=scale)
    if wtype not in FORM_PREVIEW_TYPES:
        return None
    label = str(spec.get("label") or spec.get("text") or spec.get("id", ""))
    if wtype in ("label", "text"):
        return _text_display_widget(spec, scale=scale)
    if wtype == "input":
        hint = str(spec.get("placeholder") or "请输入…")
        return _form_row(
            label, _input_preview_widget(hint, scale=scale), scale=scale, container_h=container_h
        )
    if wtype == "select":
        return _form_row(
            label, _select_preview_widget(spec, scale=scale), scale=scale, container_h=container_h
        )
    if wtype == "multiselect":
        opts = _options_list(spec)
        selected = {x.strip() for x in str(spec.get("default", "")).split(",") if x.strip()}
        return _form_row(
            label,
            _multiselect_options(opts, selected, interactive=False),
            scale=scale,
            container_h=container_h,
        )
    if wtype == "switch":
        cur = str(spec.get("default", "false")).lower()
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lay.addWidget(
            _make_switch(checked=cur in ("true", "1", "yes", "on"), enabled=False, scale=scale)
        )
        return _form_row(label, row, scale=scale, container_h=container_h)
    if wtype == "radio":
        current = str(spec.get("default", ""))
        return _form_row(
            label,
            _build_radio_group(
                spec, scale=scale, container_h=container_h, current=current, interactive=False
            ),
            scale=scale,
            container_h=container_h,
        )
    if wtype == "time_range":
        raw = str(spec.get("default", ""))
        if raw and "-" in raw:
            a, b = raw.split("-", 1)
            start_text, end_text = a.strip(), b.strip()
        else:
            start_text = str(spec.get("default_start", "09:00"))
            end_text = str(spec.get("default_end", "18:00"))
        return _form_row(
            label,
            _build_time_range(
                spec,
                scale=scale,
                container_h=container_h,
                start_text=start_text,
                end_text=end_text,
                interactive=False,
            ),
            scale=scale,
            container_h=container_h,
        )
    if wtype == "slider":
        lo = int(spec.get("min", 0) or 0)
        cur = int(float(spec.get("default", lo) or lo))
        return _form_row(
            label,
            _build_slider(
                spec, scale=scale, container_h=container_h, value=cur, interactive=False
            ),
            scale=scale,
            container_h=container_h,
        )
    if wtype == "stepper":
        lo = int(spec.get("min", 0) or 0)
        cur = int(float(spec.get("default", lo) or lo))
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lay.addWidget(
            _build_stepper(
                spec, scale=scale, container_h=container_h, value=cur, interactive=False
            )
        )
        return _form_row(label, row, scale=scale, container_h=container_h)
    if wtype == "textarea":
        return _form_row(
            label,
            _build_textarea(
                spec,
                scale=scale,
                container_h=container_h,
                text=str(spec.get("default", "")),
                interactive=False,
            ),
            scale=scale,
            container_h=container_h,
        )
    hint = _CONTROL_HINTS.get(wtype, wtype)
    return _form_row(label, _control_box(hint, scale=scale), scale=scale, container_h=container_h)


def build_interactive_widget(
    spec: dict[str, Any],
    on_change: OnChange = None,
    *,
    scale: float = 1.0,
    container_h: int | None = None,
) -> QWidget | None:
    wtype = spec.get("type", "")
    if wtype not in INTERACTIVE_TYPES:
        return None
    wid = str(spec.get("id", ""))
    label = str(spec.get("label") or "")

    def emit() -> None:
        if on_change:
            on_change()

    if wtype == "input":
        edit = QLineEdit()
        edit.setPlaceholderText(str(spec.get("placeholder", "")))
        edit.setText(PanelState.get(wid) or str(spec.get("default", "")))
        row_h = _default_row_h(scale, container_h)
        _style_line_edit(edit, scale=scale, row_h=row_h)
        if wid:
            edit.textChanged.connect(lambda t, i=wid: (PanelState.set(i, t), emit()))
        return _form_row(label, edit, scale=scale, container_h=container_h)

    if wtype == "select":
        cb = QComboBox()
        opts = _options_list(spec) if spec.get("options") is not None else ["选项1", "选项2"]
        cb.addItems(opts if opts else ["请选择"])
        cur = PanelState.get(wid) or str(spec.get("default", ""))
        idx = cb.findText(cur)
        if idx >= 0:
            cb.setCurrentIndex(idx)
        row_h = _default_row_h(scale, container_h)
        _style_combo(cb, scale=scale, row_h=row_h)
        if wid:
            cb.currentTextChanged.connect(lambda t, i=wid: (PanelState.set(i, t), emit()))
        return _form_row(label, cb, scale=scale, container_h=container_h)

    if wtype == "radio":
        current = PanelState.get(wid) or str(spec.get("default", ""))
        return _form_row(
            label,
            _build_radio_group(
                spec,
                scale=scale,
                container_h=container_h,
                current=current,
                interactive=True,
                wid=wid,
                on_change=emit,
            ),
            scale=scale,
            container_h=container_h,
        )

    if wtype == "multiselect":
        opts = _options_list(spec)
        selected = {
            x.strip()
            for x in (PanelState.get(wid) or str(spec.get("default", ""))).split(",")
            if x.strip()
        }
        return _form_row(
            label,
            _multiselect_options(opts, selected, wid=wid, on_change=emit, interactive=True),
            scale=scale,
            container_h=container_h,
        )

    if wtype == "switch":
        cur = (PanelState.get(wid) or str(spec.get("default", "false"))).lower()
        sw = _make_switch(checked=cur in ("true", "1", "yes", "on"), enabled=True, scale=scale)
        if wid:
            sw.toggled.connect(
                lambda on, i=wid: (PanelState.set(i, "true" if on else "false"), emit())
            )
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lay.addWidget(sw)
        return _form_row(label, row, scale=scale, container_h=container_h)

    if wtype == "time_range":
        raw = PanelState.get(wid) or str(spec.get("default", ""))
        if raw and "-" in raw:
            a, b = raw.split("-", 1)
            start_text, end_text = a.strip(), b.strip()
        else:
            start_text = str(spec.get("default_start", "09:00"))
            end_text = str(spec.get("default_end", "18:00"))
        return _form_row(
            label,
            _build_time_range(
                spec,
                scale=scale,
                container_h=container_h,
                start_text=start_text,
                end_text=end_text,
                interactive=True,
                wid=wid,
                on_change=emit,
            ),
            scale=scale,
            container_h=container_h,
        )

    if wtype == "slider":
        lo = int(spec.get("min", 0) or 0)
        cur = int(float(PanelState.get(wid) or spec.get("default", lo) or lo))
        return _form_row(
            label,
            _build_slider(
                spec, scale=scale, container_h=container_h, value=cur, interactive=True, wid=wid, on_change=emit
            ),
            scale=scale,
            container_h=container_h,
        )

    if wtype == "stepper":
        lo = int(spec.get("min", 0) or 0)
        cur = int(float(PanelState.get(wid) or spec.get("default", lo) or lo))
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lay.addWidget(
            _build_stepper(
                spec, scale=scale, container_h=container_h, value=cur, interactive=True, wid=wid, on_change=emit
            )
        )
        return _form_row(label, row, scale=scale, container_h=container_h)

    if wtype == "textarea":
        return _form_row(
            label,
            _build_textarea(
                spec,
                scale=scale,
                container_h=container_h,
                text=PanelState.get(wid) or str(spec.get("default", "")),
                interactive=True,
                wid=wid,
                on_change=emit,
            ),
            scale=scale,
            container_h=container_h,
        )

    return None
