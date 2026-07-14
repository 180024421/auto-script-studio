"""layout.json 清理：移除遗留控件并整理自由布局。"""

from __future__ import annotations

from typing import Any

from studio.services.free_layout import is_free_mode
from studio.services.screen_layout import chrome_widgets, ensure_migrated, flatten_all_widgets, repair_all_screens, screens

LEGACY_WIDGET_IDS = frozenset({"section_div", "func_hint"})


def next_widget_id(layout: dict[str, Any]) -> str:
    """生成 layout 内尚未占用的 w_n id。"""
    ensure_migrated(layout)
    seen = {str(w.get("id", "")).strip() for w in flatten_all_widgets(layout) if str(w.get("id", "")).strip()}
    n = 0
    while f"w_{n}" in seen:
        n += 1
    return f"w_{n}"


def dedupe_widget_ids(layout: dict[str, Any]) -> None:
    """重复或空 id 自动重命名（保留首次出现的 id）。"""
    ensure_migrated(layout)
    seen: set[str] = set()

    def assign(w: dict[str, Any]) -> None:
        wid = str(w.get("id", "")).strip()
        if not wid or wid in seen:
            n = 0
            while f"w_{n}" in seen:
                n += 1
            w["id"] = f"w_{n}"
        seen.add(str(w["id"]))

    for sc in screens(layout):
        for w in sc.get("widgets") or []:
            assign(w)
    for w in chrome_widgets(layout):
        assign(w)


def prune_legacy_widgets(layout: dict[str, Any]) -> None:
    """从各 screen 中移除已废弃的控件 id。"""
    for sc in screens(layout):
        widgets = sc.get("widgets") or []
        sc["widgets"] = [w for w in widgets if str(w.get("id", "")) not in LEGACY_WIDGET_IDS]


def sanitize_free_layout(layout: dict[str, Any]) -> None:
    """清理遗留控件、修正重复 id；自由布局下再执行 repair_all_screens。"""
    prune_legacy_widgets(layout)
    dedupe_widget_ids(layout)
    if is_free_mode(layout):
        repair_all_screens(layout)
