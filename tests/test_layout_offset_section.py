"""section 几何包含随迁（与 Android LayoutEditorOps.offsetSectionContents 对齐的数据约定）。"""

from __future__ import annotations

from studio.services.screen_layout import migrate_layout


def test_remind_wizard_has_wifi_fields():
    from studio.services.layout_wizard_templates import build_wizard_layout

    layout = build_wizard_layout("remind", panel_title="钉钉提醒")
    layout = migrate_layout(layout)
    ids = {w["id"] for sc in layout["screens"] for w in sc["widgets"]}
    assert {"remind_on", "work_hours", "wifi_leave_on", "company_wifi", "sec_remind"} <= ids
    assert layout["panel"]["display_mode"] == "host"
    assert layout["panel"]["theme"] == "green"


def test_dingtalk_example_layout_host_remind_ids():
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "examples" / "dingtalk-remind" / "ui" / "layout.json"
    layout = migrate_layout(json.loads(path.read_text(encoding="utf-8")))
    ids = {w["id"] for sc in layout["screens"] for w in sc["widgets"]}
    assert "company_wifi" in ids
    assert layout["panel"]["allow_design"] is True
