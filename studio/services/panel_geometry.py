"""自由布局面板几何（PC 预览 + 抓抓 overlay 共用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from studio.services.free_layout import panel_design_size

TITLE_DP = 48
TAB_BAR_DP = 44


def compute_free_panel_design_height(
    layout: dict[str, Any],
    *,
    active_screen: int | None = None,
) -> int:
    from studio.services.screen_layout import (
        active_screen_index,
        chrome_widgets,
        content_height,
        is_host_display,
    )

    panel = layout.get("panel", {})
    active = active_screen if active_screen is not None else active_screen_index(layout)
    body_h = content_height(layout, active, min_canvas=0)
    chrome_list = chrome_widgets(layout)
    if is_host_display(panel) or not chrome_list:
        chrome_h = 0
    else:
        chrome_h = max(int(w.get("layout_y", 0) + w.get("layout_h", 52)) for w in chrome_list) + 16
    return TITLE_DP + TAB_BAR_DP + body_h + chrome_h


@dataclass(frozen=True)
class FreePanelOverlayMetrics:
    design_w: int
    design_h: int
    panel_w_px: int
    panel_h_px: int
    inner_scale: float
    header_off_design: int


def compute_free_panel_overlay_metrics(
    layout: dict[str, Any],
    image_w: int,
    image_h: int,
    *,
    dp_to_px_fn,
    active_screen: int | None = None,
) -> FreePanelOverlayMetrics:
    """抓抓页虚线框与手机画布共用的面板外框尺寸。"""
    panel = layout.get("panel", {})
    dw, _dh = panel_design_size(panel)
    width_dp = int(panel.get("width_dp", 320))
    start_x = int(panel.get("start_x", 20))
    start_y = int(panel.get("start_y", 200))
    design_h = compute_free_panel_design_height(layout, active_screen=active_screen)

    panel_w = dp_to_px_fn(width_dp, image_w)
    panel_h = int(panel_w * design_h / max(1, dw))
    panel_h = min(panel_h, max(1, image_h - start_y))
    panel_w = min(panel_w, max(1, image_w - start_x))
    inner_scale = panel_w / max(1, dw)
    return FreePanelOverlayMetrics(
        design_w=dw,
        design_h=design_h,
        panel_w_px=panel_w,
        panel_h_px=panel_h,
        inner_scale=inner_scale,
        header_off_design=TITLE_DP + TAB_BAR_DP,
    )
