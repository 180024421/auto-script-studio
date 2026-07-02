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

_SWITCH_STYLE = """
QCheckBox { spacing: 0; background: transparent; }
QCheckBox::indicator {
    width: 44px;
    height: 24px;
    border-radius: 12px;
    border: 1px solid #94A3B8;
    background: #E2E8F0;
}
QCheckBox::indicator:checked {
    background: #2563EB;
    border-color: #1D4ED8;
}
QCheckBox::indicator:disabled {
    background: #F1F5F9;
    border-color: #CBD5E1;
}
"""


def _make_switch(*, checked: bool = False, enabled: bool = True) -> QCheckBox:
    sw = QCheckBox()
    sw.setText("")
    sw.setStyleSheet(_SWITCH_STYLE)
    sw.setFixedWidth(48)
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


def _label_width(text: str) -> int:
    t = text.strip()
    if not t:
        return 0
    # 约 12px/字，短标签不占用过宽列（对齐按键精灵「账号：」）
    return min(72, max(40, len(t) * 12 + 10))


def _form_row(label: str, control: QWidget, *, label_width: int | None = None) -> QWidget:
    host = QWidget()
    host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    lay = QHBoxLayout(host)
    lay.setContentsMargins(4, 2, 6, 2)
    lay.setSpacing(4)
    if label:
        lbl = QLabel(label)
        lbl.setFixedWidth(label_width if label_width is not None else _label_width(label))
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet("color:#475569;font-size:12px;background:transparent;padding:0;")
        lay.addWidget(lbl)
    control.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    control.setMinimumHeight(32)
    if isinstance(control, (QLineEdit, QComboBox, QTextEdit)):
        control.setStyleSheet(_FIELD_CTRL_STYLE)
    lay.addWidget(control, 1)
    return host


def _control_box(text: str = "") -> QFrame:
    box = QFrame()
    box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    box.setStyleSheet(
        "QFrame { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:4px; }"
    )
    box.setMinimumHeight(32)
    inner = QLabel(text)
    inner.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    inner.setStyleSheet("color:#94A3B8;font-size:11px;border:none;background:transparent;")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(6, 0, 6, 0)
    lay.addWidget(inner, 1)
    return box


def _input_preview_widget(placeholder: str = "") -> QLineEdit:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder or "请输入…")
    edit.setReadOnly(True)
    edit.setStyleSheet(_FIELD_CTRL_STYLE)
    edit.setMinimumHeight(32)
    return edit


def _select_preview_widget(spec: dict[str, Any]) -> QComboBox:
    cb = QComboBox()
    opts = [str(o) for o in (spec.get("options") or ["选项1", "选项2"])]
    if not opts:
        opts = ["请选择"]
    cb.addItems(opts)
    cur = str(spec.get("default") or opts[0])
    idx = cb.findText(cur)
    if idx >= 0:
        cb.setCurrentIndex(idx)
    cb.setEnabled(False)
    cb.setStyleSheet(_FIELD_COMBO_STYLE)
    cb.setMinimumHeight(32)
    return cb


def _divider_line_widget() -> QWidget:
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


def _text_display_widget(spec: dict[str, Any]) -> QLabel:
    content = str(spec.get("text") or spec.get("label") or "提示文字")
    style = str(spec.get("text_style") or "normal").lower()
    host = QLabel(content)
    host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    host.setWordWrap(False)
    align = str(spec.get("align") or "left").lower()
    qt_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
    if align == "center":
        qt_align = Qt.AlignmentFlag.AlignCenter
    elif align == "right":
        qt_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
    host.setAlignment(qt_align)
    if style == "title":
        host.setStyleSheet(
            "color:#1E293B;font-weight:700;font-size:14px;padding:8px 12px;background:transparent;"
        )
    elif style == "hint":
        host.setStyleSheet(
            "color:#64748B;font-size:11px;padding:6px 12px;background:transparent;"
        )
    else:
        host.setStyleSheet(
            "color:#334155;font-size:12px;padding:8px 12px;background:transparent;"
        )
    return host


def build_design_preview(spec: dict[str, Any]) -> QWidget | None:
    """非交互画布：左标签右控件占位预览。"""
    wtype = spec.get("type", "")
    if wtype == "divider":
        return _divider_line_widget()
    if wtype not in FORM_PREVIEW_TYPES:
        return None
    label = str(spec.get("label") or spec.get("text") or spec.get("id", ""))
    if wtype in ("label", "text"):
        return _text_display_widget(spec)
    if wtype == "input":
        hint = str(spec.get("placeholder") or "请输入…")
        return _form_row(label, _input_preview_widget(hint))
    if wtype == "select":
        return _form_row(label, _select_preview_widget(spec))
    if wtype == "multiselect":
        opts = [str(o) for o in (spec.get("options") or ["选项A", "选项B"])]
        selected = {x.strip() for x in str(spec.get("default", "")).split(",") if x.strip()}
        return _form_row(label, _multiselect_options(opts, selected, interactive=False))
    if wtype == "switch":
        cur = str(spec.get("default", "false")).lower()
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lay.addWidget(_make_switch(checked=cur in ("true", "1", "yes", "on"), enabled=False))
        return _form_row(label, row)
    hint = _CONTROL_HINTS.get(wtype, wtype)
    return _form_row(label, _control_box(hint))


def build_interactive_widget(spec: dict[str, Any], on_change: OnChange = None) -> QWidget | None:
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
        if wid:
            edit.textChanged.connect(lambda t, i=wid: (PanelState.set(i, t), emit()))
        return _form_row(label, edit)

    if wtype == "select":
        cb = QComboBox()
        opts = [str(o) for o in (spec.get("options") or ["选项1", "选项2"])]
        cb.addItems(opts)
        cur = PanelState.get(wid) or str(spec.get("default", ""))
        idx = cb.findText(cur)
        if idx >= 0:
            cb.setCurrentIndex(idx)
        cb.setStyleSheet(_FIELD_COMBO_STYLE)
        if wid:
            cb.currentTextChanged.connect(lambda t, i=wid: (PanelState.set(i, t), emit()))
        return _form_row(label, cb)

    if wtype == "radio":
        opts = [str(o) for o in (spec.get("options") or ["选项A", "选项B"])]
        current = PanelState.get(wid) or str(spec.get("default", ""))
        group_host = QWidget()
        group_lay = QVBoxLayout(group_host)
        group_lay.setContentsMargins(0, 0, 0, 0)
        group_lay.setSpacing(2)
        for opt in opts:
            rb = QRadioButton(opt)
            rb.setChecked(opt == current or (not current and opt == opts[0]))
            if wid:
                rb.toggled.connect(
                    lambda on, i=wid, o=opt: (PanelState.set(i, o), emit()) if on else None
                )
            group_lay.addWidget(rb)
        return _form_row(label, group_host)

    if wtype == "multiselect":
        opts = [str(o) for o in (spec.get("options") or ["选项A", "选项B"])]
        selected = {
            x.strip()
            for x in (PanelState.get(wid) or str(spec.get("default", ""))).split(",")
            if x.strip()
        }
        return _form_row(
            label,
            _multiselect_options(opts, selected, wid=wid, on_change=emit, interactive=True),
        )

    if wtype == "switch":
        cur = (PanelState.get(wid) or str(spec.get("default", "false"))).lower()
        sw = _make_switch(checked=cur in ("true", "1", "yes", "on"), enabled=True)
        if wid:
            sw.toggled.connect(
                lambda on, i=wid: (PanelState.set(i, "true" if on else "false"), emit())
            )
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lay.addWidget(sw)
        return _form_row(label, row)

    if wtype == "time_range":
        row = QHBoxLayout()
        row.setSpacing(4)
        start = QLineEdit()
        end = QLineEdit()
        raw = PanelState.get(wid) or str(spec.get("default", ""))
        if raw and "-" in raw:
            a, b = raw.split("-", 1)
            start.setText(a.strip())
            end.setText(b.strip())
        else:
            start.setText(str(spec.get("default_start", "09:00")))
            end.setText(str(spec.get("default_end", "18:00")))

        def sync(i=wid, s=start, e=end) -> None:
            if i:
                PanelState.set(i, f"{s.text().strip()}-{e.text().strip()}")
            emit()

        if wid:
            start.textChanged.connect(lambda _t: sync())
            end.textChanged.connect(lambda _t: sync())
        host = QWidget()
        inner = QHBoxLayout(host)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(QLabel("从"))
        inner.addWidget(start, 1)
        inner.addWidget(QLabel("到"))
        inner.addWidget(end, 1)
        return _form_row(label, host)

    if wtype == "slider":
        lo = int(spec.get("min", 0) or 0)
        hi = int(spec.get("max", 100) or 100)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        cur = int(float(PanelState.get(wid) or spec.get("default", lo) or lo))
        slider.setValue(max(lo, min(hi, cur)))
        if wid:
            slider.valueChanged.connect(lambda v, i=wid: (PanelState.set(i, str(v)), emit()))
        return _form_row(label, slider)

    if wtype == "stepper":
        lo = int(spec.get("min", 0) or 0)
        hi = int(spec.get("max", 99) or 99)
        sp = QSpinBox()
        sp.setRange(lo, hi)
        cur = int(float(PanelState.get(wid) or spec.get("default", lo) or lo))
        sp.setValue(max(lo, min(hi, cur)))
        if wid:
            sp.valueChanged.connect(lambda v, i=wid: (PanelState.set(i, str(v)), emit()))
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch(1)
        lay.addWidget(sp)
        return _form_row(label, row)

    if wtype == "textarea":
        te = QTextEdit()
        te.setPlaceholderText(str(spec.get("placeholder", "")))
        te.setPlainText(PanelState.get(wid) or str(spec.get("default", "")))
        rows = int(spec.get("rows", 3) or 3)
        te.setMaximumHeight(max(48, rows * 22))
        if wid:
            te.textChanged.connect(
                lambda i=wid, w=te: (PanelState.set(i, w.toPlainText()), emit())
            )
        return _form_row(label, te)

    return None
