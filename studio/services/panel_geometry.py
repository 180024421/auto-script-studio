"""自由布局面板几何（PC 预览 + 抓抓 overlay 共用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from studio.services.free_layout import panel_design_size

TITLE_DP = 48
TAB_BAR_DP = 44


def dp_to_preview_px(dp: float, screen_w: int) -> int:
    """预览/截图坐标：360dp 屏宽基准（与 layout_preview.dp_to_px 一致）。"""
    density = max(1.0, screen_w / 360.0)
    return max(1, int(dp * density))


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


@dataclass(frozen=True)
class PanelOverlayRect:
    x: int
    y: int
    w: int
    h: int
    inner_scale: float


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


def compute_host_panel_overlay_rect(
    layout: dict[str, Any],
    screen_w: int,
    screen_h: int,
    *,
    active_screen: int | None = None,
    margin_dp: int = 12,
) -> PanelOverlayRect:
    """与 Android OverlayService.applyPanelPosition 对齐的浮动面板矩形。"""
    panel = layout.get("panel", {})
    metrics = compute_free_panel_overlay_metrics(
        layout,
        screen_w,
        screen_h,
        dp_to_px_fn=dp_to_preview_px,
        active_screen=active_screen,
    )
    pw, ph = metrics.panel_w_px, metrics.panel_h_px
    margin = dp_to_preview_px(margin_dp, screen_w)
    start_x = int(panel.get("start_x", 0))
    start_y = int(panel.get("start_y", 0))
    position = str(panel.get("position", "left_center")).lower()
    min_h = dp_to_preview_px(48, screen_w)

    if position in ("right_center", "right"):
        x = screen_w - pw - margin - start_x
        x = max(margin, x)
    elif position in ("left_center", "left"):
        x = max(margin, start_x + margin)
    else:
        x = max(0, start_x)

    y = max(margin, (screen_h - max(ph, min_h)) // 2 + start_y)
    return PanelOverlayRect(x=x, y=y, w=pw, h=ph, inner_scale=metrics.inner_scale)


def compute_device_screen_px(
    design_w: int,
    design_h: int,
    scale: float,
    *,
    landscape: bool,
) -> tuple[int, int]:
    """设备仿真外屏尺寸（竖屏=设计宽高，横屏=对调）。"""
    if landscape:
        return int(design_h * scale), int(design_w * scale)
    return int(design_w * scale), int(design_h * scale)
