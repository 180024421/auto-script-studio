"""PC 预览主题色（对齐 Android OverlayTheme）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelThemeColors:
    title_bg: str
    title_fg: str
    screen_bg: str
    field_border: str
    field_bg: str
    field_focus: str
    label_muted: str
    chrome_bg: str
    chrome_border: str
    switch_checked: str
    accent: str


def panel_theme_colors(theme: str) -> PanelThemeColors:
    t = (theme or "light").lower()
    if t == "dark":
        return PanelThemeColors(
            title_bg="#1E2838",
            title_fg="#E8EEF6",
            screen_bg="#282830",
            field_border="#444444",
            field_bg="#1A1A1A",
            field_focus="#4CAF50",
            label_muted="#B0BEC5",
            chrome_bg="#1E2838",
            chrome_border="#2E3D52",
            switch_checked="#4CAF50",
            accent="#4CAF50",
        )
    return PanelThemeColors(
        title_bg="#2563EB",
        title_fg="#FFFFFF",
        screen_bg="#FFFFFF",
        field_border="#CBD5E1",
        field_bg="#FFFFFF",
        field_focus="#2563EB",
        label_muted="#64748B",
        chrome_bg="#F8FAFC",
        chrome_border="#E2E8F0",
        switch_checked="#2563EB",
        accent="#2563EB",
    )
