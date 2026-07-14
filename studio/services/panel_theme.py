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
    section_bg: str
    section_border: str
    section_title: str


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
            section_bg="#3A3A48",
            section_border="#6B6B7C",
            section_title="#F1F5F9",
        )
    if t == "green":
        return PanelThemeColors(
            title_bg="#059669",
            title_fg="#FFFFFF",
            screen_bg="#F0FDF4",
            field_border="#A7F3D0",
            field_bg="#FFFFFF",
            field_focus="#059669",
            label_muted="#047857",
            chrome_bg="#ECFDF5",
            chrome_border="#A7F3D0",
            switch_checked="#059669",
            accent="#059669",
            section_bg="#FFFFFF",
            section_border="#BBF7D0",
            section_title="#065F46",
        )
    if t in ("gray", "neutral", "grey"):
        return PanelThemeColors(
            title_bg="#475569",
            title_fg="#FFFFFF",
            screen_bg="#F8FAFC",
            field_border="#CBD5E1",
            field_bg="#FFFFFF",
            field_focus="#475569",
            label_muted="#64748B",
            chrome_bg="#F1F5F9",
            chrome_border="#E2E8F0",
            switch_checked="#475569",
            accent="#475569",
            section_bg="#FFFFFF",
            section_border="#E2E8F0",
            section_title="#0F172A",
        )
    # light / business blue
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
        section_bg="#F8FAFC",
        section_border="#E2E8F0",
        section_title="#0F172A",
    )
