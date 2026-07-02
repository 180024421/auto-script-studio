"""layout.json 校验。"""

from __future__ import annotations

from typing import Any

from studio.services.screen_layout import CHROME_PATH_TAG, ensure_migrated, flatten_all_widgets


def validate_layout(layout: dict[str, Any]) -> list[str]:
    """返回错误文案列表；空列表表示通过。"""
    errors: list[str] = []
    data = dict(layout)
    ensure_migrated(data)
    panel = data.get("panel", {})
    if panel.get("layout_mode") == "free":
        dw = int(panel.get("design_width", 720))
        dh = int(panel.get("design_height", 1280))
        for w in flatten_all_widgets(data):
            x = int(w.get("layout_x", 0))
            y = int(w.get("layout_y", 0))
            ww = int(w.get("layout_w", 48))
            hh = int(w.get("layout_h", 28))
            if x < 0 or y < 0:
                errors.append(f"控件「{w.get('id', '?')}」坐标不能为负")
            if ww < 24 or hh < 20:
                errors.append(f"控件「{w.get('id', '?')}」尺寸过小")
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
