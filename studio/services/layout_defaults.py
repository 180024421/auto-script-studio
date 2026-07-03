"""layout.json 控件 schema 与归一化。"""

from __future__ import annotations

import json
from typing import Any

from studio.services.free_layout import default_rect_for_type, is_free_mode
from studio.services.screen_layout import ensure_all_rects, migrate_layout
ACTION_TYPES = [
    ("start_script", "启动主脚本"),
    ("stop_script", "停止主脚本"),
    ("tap", "点击坐标"),
    ("swipe", "滑动"),
    ("long_press", "长按"),
    ("lua", "Lua 片段"),
    ("collapse", "收起面板"),
    ("open_app", "打开本应用"),
]

FORM_WIDGET_TYPES = [
    ("text", "文字框"),
    ("label", "标签"),
    ("input", "输入框"),
    ("select", "下拉选择"),
    ("radio", "单选框"),
    ("multiselect", "多选"),
    ("switch", "开关"),
    ("time_range", "时间范围"),
    ("slider", "滑条"),
    ("stepper", "步进器"),
    ("textarea", "多行文本"),
    ("divider", "分隔线"),
    ("tabs", "标签页"),
]

# 兼容旧名
BUTTON_TYPES = ACTION_TYPES

WIDGET_TYPE_LABELS = {k: v for k, v in ACTION_TYPES + FORM_WIDGET_TYPES}

PANEL_THEMES = [
    ("light", "浅色商务"),
    ("dark", "深色经典"),
]

DEFAULT_LAYOUT: dict[str, Any] = {
    "version": 3,
    "enabled": True,
    "panel": {
        "title": "UI界面例子",
        "theme": "light",
        "layout_mode": "free",
        "design_width": 720,
        "design_height": 1280,
        "active_screen": 0,
        "width_mode": "auto",
        "width_dp": 720,
        "height_mode": "full",
        "display_mode": "minimal",
        "auto_collapse_idle_ms": 15000,
        "show_on_launch": False,
        "opacity": 0.96,
        "position": "left_center",
        "start_x": 20,
        "start_y": 200,
        "columns": 2,
        "ball_size_dp": 48,
        "show_log": True,
        "log_height_dp": 88,
        "draggable": True,
        "collapsible": True,
        "allow_design": True,
        "start_confirm_collapse": True,
    },
    "screens": [
        {
            "title": "标签页1",
            "widgets": [
                {
                    "id": "hint",
                    "type": "text",
                    "text": "请填写登陆账号信息",
                    "text_style": "title",
                    "layout_x": 24,
                    "layout_y": 24,
                    "layout_w": 164,
                    "layout_h": 40,
                },
                {
                    "id": "account",
                    "type": "input",
                    "label": "账号",
                    "placeholder": "请输入账号，多个用:号分隔",
                    "layout_x": 24,
                    "layout_y": 72,
                    "layout_w": 672,
                    "layout_h": 52,
                },
                {
                    "id": "password",
                    "type": "input",
                    "label": "密码",
                    "placeholder": "请输入密码",
                    "layout_x": 24,
                    "layout_y": 132,
                    "layout_w": 672,
                    "layout_h": 52,
                },
                {
                    "id": "section_div",
                    "type": "divider",
                    "text": "",
                    "layout_x": 24,
                    "layout_y": 192,
                    "layout_w": 672,
                    "layout_h": 12,
                },
                {
                    "id": "func_hint",
                    "type": "text",
                    "text": "脚本功能选择：",
                    "text_style": "hint",
                    "layout_x": 24,
                    "layout_y": 228,
                    "layout_w": 112,
                    "layout_h": 36,
                },
            ],
        },
        {
            "title": "界面1",
            "widgets": [
                {
                    "id": "mode",
                    "type": "select",
                    "label": "模式",
                    "options": ["普通", "极速"],
                    "default": "普通",
                    "layout_x": 24,
                    "layout_y": 24,
                    "layout_w": 672,
                    "layout_h": 64,
                },
            ],
        },
    ],
    "widgets": [
        {
            "id": "start",
            "type": "start_script",
            "label": "开始",
            "color": "#2563EB",
            "layout_x": 24,
            "layout_y": 4,
            "layout_w": 672,
            "layout_h": 52,
        },
    ],
}

def layout_path(project_dir) -> "Path":
    from pathlib import Path

    return Path(project_dir) / "ui" / "layout.json"


def normalize_layout(data: dict[str, Any]) -> dict[str, Any]:
    """读取后归一化：buttons → widgets，补齐缺省字段。"""
    from studio.services.layout_clone import clone_layout

    out = clone_layout(data)
    if "widgets" not in out and "buttons" in out:
        out["widgets"] = out["buttons"]
    out.setdefault("widgets", [])
    out.setdefault("version", 2 if "widgets" in data else 1)
    panel = out.setdefault("panel", {})
    panel.setdefault("theme", "light")
    panel.setdefault("width_dp", 220)
    panel.setdefault("width_mode", "fixed")
    panel.setdefault("height_mode", "wrap")
    panel.setdefault("height_dp", int(panel.get("design_height", 1280) or 1280))
    panel.setdefault("display_mode", "form")
    panel.setdefault("auto_collapse_idle_ms", 0)
    panel.setdefault("show_on_launch", False)
    panel.setdefault("log_height_dp", 88)
    panel.setdefault("columns", 2)
    panel.setdefault("allow_design", True)
    panel.setdefault("start_confirm_collapse", True)
    panel.setdefault("layout_mode", "grid")
    panel.setdefault("design_width", 720)
    panel.setdefault("design_height", 1280)
    out = migrate_layout(out)
    panel.setdefault("active_screen", 0)
    if is_free_mode(out):
        panel.setdefault("width_mode", "auto")
        design_w = int(panel.get("design_width", 720) or 720)
        panel.setdefault("width_dp", int(design_w * 0.9))
        from studio.services.screen_layout import normalize_chrome_widgets

        out["widgets"] = normalize_chrome_widgets(out.get("widgets") or [], out.get("panel"))
        out = ensure_all_rects(out)
    return out


def load_layout(project_dir) -> dict[str, Any]:
    path = layout_path(project_dir)
    if not path.is_file():
        from studio.services.layout_clone import clone_layout

        return clone_layout(DEFAULT_LAYOUT)
    return normalize_layout(json.loads(path.read_text(encoding="utf-8")))


def save_layout(project_dir, data: dict[str, Any]) -> None:
    path = layout_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = normalize_layout(data)
    # 写出 widgets 为主；保留 buttons 镜像方便旧工具查看
    if "widgets" in payload:
        payload["buttons"] = payload["widgets"]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def widget_display_name(w: dict[str, Any]) -> str:
    wtype = w.get("type", "")
    label = WIDGET_TYPE_LABELS.get(wtype, wtype)
    if wtype == "divider":
        return f"[{label}]"
    title = w.get("label") or w.get("text") or w.get("id", "?")
    return f"{title}  [{label}]"


def default_widget(wtype: str, index: int) -> dict[str, Any]:
    wid = f"w_{index}"
    if wtype == "label":
        rect = default_rect_for_type("label", index)
        return {"id": wid, "type": "label", "text": "说明文字", "width": 2, **rect}
    if wtype == "text":
        from studio.services.free_layout import estimate_text_layout_width

        sample = "提示用户的文字内容"
        rect = default_rect_for_type("text", index)
        rect["layout_w"] = estimate_text_layout_width(sample, "hint")
        return {
            "id": wid,
            "type": "text",
            "text": sample,
            "text_style": "hint",
            "width": 2,
            **rect,
        }
    if wtype == "input":
        rect = default_rect_for_type("input", index)
        return {
            "id": wid,
            "type": "input",
            "label": "输入项",
            "placeholder": "",
            "default": "",
            "width": 2,
            **rect,
        }
    if wtype == "select":
        rect = default_rect_for_type("select", index)
        return {
            "id": wid,
            "type": "select",
            "label": "下拉项",
            "options": ["选项1", "选项2"],
            "default": "选项1",
            "width": 2,
            **rect,
        }
    if wtype == "radio":
        rect = default_rect_for_type("radio", index)
        return {
            "id": wid,
            "type": "radio",
            "label": "单选项",
            "options": ["选项A", "选项B"],
            "default": "选项A",
            "width": 2,
            **rect,
        }
    if wtype == "multiselect":
        rect = default_rect_for_type("multiselect", index)
        return {
            "id": wid,
            "type": "multiselect",
            "label": "多选项",
            "options": ["选项A", "选项B"],
            "default": "选项A",
            "width": 2,
            **rect,
        }
    if wtype == "switch":
        rect = default_rect_for_type("switch", index)
        return {
            "id": wid,
            "type": "switch",
            "label": "开关项",
            "default": "false",
            "width": 2,
            **rect,
        }
    if wtype == "time_range":
        rect = default_rect_for_type("time_range", index)
        return {
            "id": wid,
            "type": "time_range",
            "label": "时段",
            "default_start": "09:00",
            "default_end": "18:00",
            "default": "09:00-18:00",
            "width": 2,
            **rect,
        }
    if wtype == "slider":
        rect = default_rect_for_type("slider", index)
        return {
            "id": wid,
            "type": "slider",
            "label": "滑条",
            "default": "50",
            "min": 0,
            "max": 100,
            "step": 1,
            "width": 2,
            **rect,
        }
    if wtype == "stepper":
        rect = default_rect_for_type("stepper", index)
        return {
            "id": wid,
            "type": "stepper",
            "label": "数量",
            "default": "1",
            "min": 0,
            "max": 99,
            "step": 1,
            "width": 2,
            **rect,
        }
    if wtype == "textarea":
        rect = default_rect_for_type("textarea", index)
        return {
            "id": wid,
            "type": "textarea",
            "label": "备注",
            "placeholder": "请输入…",
            "default": "",
            "rows": 4,
            "width": 2,
            **rect,
        }
    if wtype == "divider":
        rect = default_rect_for_type("divider", index)
        return {"id": wid, "type": "divider", "text": "", "width": 2, **rect}
    if wtype == "tabs":
        rect = default_rect_for_type("tabs", index)
        return {
            "id": wid,
            "type": "tabs",
            "label": "标签页",
            "width": 2,
            **rect,
            "tabs": [
                {"title": "页签1", "widgets": []},
                {"title": "页签2", "widgets": []},
            ],
        }
    # action button
    rect = default_rect_for_type(wtype, index)
    return {
        "id": wid,
        "type": wtype,
        "label": WIDGET_TYPE_LABELS.get(wtype, "按钮"),
        "color": "#64748B",
        "width": 1,
        **rect,
    }


def is_action_type(wtype: str) -> bool:
    return wtype in {t for t, _ in ACTION_TYPES}


def action_types_for_layout(layout: dict[str, Any]) -> list[tuple[str, str]]:
    """自由布局 chrome 不再提供停止按钮（改由悬浮球 ■ 停止）。"""
    if is_free_mode(layout):
        return [(t, d) for t, d in ACTION_TYPES if t != "stop_script"]
    return list(ACTION_TYPES)


def is_form_type(wtype: str) -> bool:
    return wtype in {t for t, _ in FORM_WIDGET_TYPES}


def validate_widget_value(spec: dict[str, Any], value: str) -> str | None:
    """校验控件值；通过返回 None，失败返回错误文案。"""
    val = value.strip()
    label = spec.get("label") or spec.get("id") or "字段"
    if spec.get("required") and not val:
        return f"「{label}」为必填项"
    min_v = spec.get("min")
    max_v = spec.get("max")
    if min_v is not None or max_v is not None:
        if not val:
            return None
        try:
            num = float(val)
        except ValueError:
            return "须为数字"
        if min_v is not None and num < float(min_v):
            return f"不能小于 {min_v}"
        if max_v is not None and num > float(max_v):
            return f"不能大于 {max_v}"
    return None
