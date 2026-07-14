"""layout.json 校验。"""

from __future__ import annotations

from typing import Any

from studio.services.free_layout import min_rect_for_type
from studio.services.screen_layout import CHROME_PATH_TAG, ensure_migrated, flatten_all_widgets

# 可由 repair_all_screens / sanitize_free_layout 自动修正的校验项关键词
_AUTO_REPAIR_MARKERS = ("尺寸过小", "坐标不能为负", "超出设计宽度", "id 重复")


def is_auto_repairable(errors: list[str]) -> bool:
    """错误是否均可通过一键整理自动修复。"""
    if not errors:
        return False
    return all(any(m in e for m in _AUTO_REPAIR_MARKERS) for e in errors)


def validate_layout(layout: dict[str, Any]) -> list[str]:
    """返回错误文案列表；空列表表示通过。"""
    errors: list[str] = []
    data = dict(layout)
    ensure_migrated(data)
    panel = data.get("panel", {})
    mode = panel.get("display_mode", "host")
    overlay_minimal = mode in ("minimal", "host", "form")
    if panel.get("layout_mode") == "free":
        dw = int(panel.get("design_width", 720))
        dh = int(panel.get("design_height", 1280))
        for w in flatten_all_widgets(data):
            x = int(w.get("layout_x", 0))
            y = int(w.get("layout_y", 0))
            ww = int(w.get("layout_w", 48))
            hh = int(w.get("layout_h", 28))
            wtype = str(w.get("type", ""))
            min_w, min_h = min_rect_for_type(wtype)
            if overlay_minimal and wtype in ("start_script", "stop_script"):
                min_w, min_h = 24, 24
            if x < 0 or y < 0:
                errors.append(f"控件「{w.get('id', '?')}」坐标不能为负")
            if ww < min_w or hh < min_h:
                errors.append(
                    f"控件「{w.get('id', '?')}」尺寸过小（当前 {ww}×{hh}，"
                    f"{wtype} 至少 {min_w}×{min_h}）"
                )
            if x + ww > dw + 8:
                errors.append(f"控件「{w.get('id', '?')}」超出设计宽度 {dw}")
            if y > dh * 3:
                errors.append(f"控件「{w.get('id', '?')}」Y 坐标异常偏大")

    seen: dict[str, str] = {}
    for w in flatten_all_widgets(data):
        wid = str(w.get("id", "")).strip()
        if not wid:
            errors.append(f"存在未设置 id 的控件（type={w.get('type', '?')}）")
            continue
        if wid in seen:
            errors.append(f"控件 id 重复：「{wid}」（{seen[wid]} 与 {w.get('type', '?')}）")
        else:
            seen[wid] = str(w.get("type", "?"))

    for i, sc in enumerate(data.get("screens") or []):
        title = str(sc.get("title", "")).strip()
        if not title:
            errors.append(f"第 {i + 1} 个界面缺少标题")

    return errors
