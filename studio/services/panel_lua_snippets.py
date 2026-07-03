"""根据 layout 控件类型生成 panel.* Lua 读取片段。"""

from __future__ import annotations

from typing import Any

from studio.services.free_layout import is_free_mode
from studio.services.screen_layout import resolve_widget, screens

VALUE_WIDGET_TYPES = frozenset(
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


def list_value_widgets(layout: dict[str, Any]) -> list[dict[str, Any]]:
    """返回带 id 的表单控件（供脚本页插入 panel.get 等）。"""
    out: list[dict[str, Any]] = []

    def walk(widgets: list[dict[str, Any]]) -> None:
        for w in widgets:
            wtype = str(w.get("type", ""))
            wid = str(w.get("id", "") or "")
            if wtype in VALUE_WIDGET_TYPES and wid:
                opts = w.get("options") or []
                if isinstance(opts, str):
                    opts = [x.strip() for x in opts.splitlines() if x.strip()]
                out.append(
                    {
                        "id": wid,
                        "type": wtype,
                        "label": str(w.get("label") or wid),
                        "options": list(opts),
                    }
                )
            elif wtype == "tabs":
                for tab in w.get("tabs") or []:
                    walk(tab.get("widgets") or [])

    if layout.get("screens"):
        for sc in screens(layout):
            walk(sc.get("widgets") or [])
    else:
        walk(layout.get("widgets") or layout.get("buttons") or [])
    return out


def _resolve_grid_widget(
    layout: dict[str, Any], path: tuple[int, ...]
) -> dict[str, Any] | None:
    if not path:
        return None
    widgets: list[dict[str, Any]] = list(
        layout.get("widgets") or layout.get("buttons") or []
    )
    pos = 0
    while pos < len(path):
        idx = path[pos]
        if idx < 0 or idx >= len(widgets):
            return None
        spec = widgets[idx]
        if pos == len(path) - 1:
            return spec
        if str(spec.get("type", "")) == "tabs" and pos + 1 < len(path):
            tab_idx = path[pos + 1]
            tabs = spec.get("tabs") or []
            if tab_idx < 0 or tab_idx >= len(tabs):
                return None
            widgets = list(tabs[tab_idx].get("widgets") or [])
            pos += 2
            continue
        return None
    return None


def resolve_layout_widget(
    layout: dict[str, Any], path: tuple[int, ...]
) -> dict[str, Any] | None:
    if is_free_mode(layout):
        return resolve_widget(layout, path)
    return _resolve_grid_widget(layout, path)


def widget_lua_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    """将 layout 控件规范化为 lua_read_snippet 所需结构。"""
    wtype = str(spec.get("type", ""))
    wid = str(spec.get("id", "") or "")
    if wtype not in VALUE_WIDGET_TYPES or not wid:
        return None
    opts = spec.get("options") or []
    if isinstance(opts, str):
        opts = [x.strip() for x in opts.splitlines() if x.strip()]
    return {
        "id": wid,
        "type": wtype,
        "label": str(spec.get("label") or wid),
        "options": list(opts),
    }


def lua_read_snippet(widget: dict[str, Any]) -> str:
    """生成读取单个控件值的 Lua 片段。"""
    wid = widget["id"]
    label = widget.get("label") or wid
    wtype = widget.get("type", "input")
    if wtype == "switch":
        return (
            f'if panel.isOn("{wid}") then\n'
            f'  bot.log("{label} 已开启")\n'
            "else\n"
            f'  bot.log("{label} 未开启")\n'
            "end"
        )
    if wtype == "time_range":
        return (
            f'local startT, endT = panel.getTimeRange("{wid}")\n'
            f'bot.log("{label}: " .. startT .. " - " .. endT)'
        )
    if wtype == "multiselect":
        opts = widget.get("options") or []
        sample = opts[0] if opts else "选项名"
        return (
            f'-- 当前值: panel.get("{wid}")\n'
            f'if panel.has("{wid}", "{sample}") then\n'
            f'  bot.log("已勾选 {sample}")\n'
            "end"
        )
    if wtype in ("select", "radio"):
        opts = widget.get("options") or []
        sample = opts[0] if opts else "某个选项"
        return (
            f'local val = panel.get("{wid}")\n'
            f'bot.log("{label}: " .. val)\n'
            f'if panel.is("{wid}", "{sample}") then\n'
            "  -- 分支逻辑\n"
            "end"
        )
    return f'local val = panel.get("{wid}")\n' f'bot.log("{label}: " .. val)'


def lua_panel_example() -> str:
    return (
        "-- 浮动面板表单（控件 id 须与 layout.json 一致）\n"
        'local mode = panel.get("mode")\n'
        'bot.log("模式: " .. mode)\n\n'
        'if panel.is("mode", "极速") then\n'
        '  bot.log("走极速分支")\n'
        "end\n\n"
        'if panel.isOn("notify") then\n'
        '  bot.log("通知已开启")\n'
        "end\n\n"
        'local startT, endT = panel.getTimeRange("work_hours")\n'
        'bot.log("工作时段: " .. startT .. " - " .. endT)\n\n'
        'if panel.has("tasks", "日常") then\n'
        '  bot.log("已勾选日常")\n'
        "end\n\n"
        'panel.watch("mode", function(v)\n'
        '  bot.log("模式变为: " .. v)\n'
        "end)\n\n"
        'local snap = panel.snapshot()\n'
        'for k, v in pairs(snap) do bot.log(k .. "=" .. v) end\n\n'
        'local delay = tonumber(panel.get("delay_ms")) or 500\n'
        "bot.delay(delay / 1000)\n"
    )


def lua_all_values() -> str:
    return (
        "local snap = panel.snapshot()\n"
        'for k, v in pairs(snap) do\n'
        '  bot.log(k .. "=" .. tostring(v))\n'
        "end"
    )
