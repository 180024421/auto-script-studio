"""布局向导与 panel 代码生成测试。"""

from __future__ import annotations

import json
from pathlib import Path

from studio.services.layout_validate import validate_layout
from studio.services.layout_wizard_templates import build_wizard_layout
from studio.services.panel_lua_snippets import lua_reads_block_for_layout, safe_lua_var
from studio.services.screen_layout import migrate_layout


def test_build_wizard_full_validates():
    layout = build_wizard_layout("full", panel_title="测试助手")
    assert layout["panel"]["title"] == "测试助手"
    assert len(layout.get("screens") or []) == 2
    assert validate_layout(layout) == []


def test_build_wizard_login_has_account():
    layout = build_wizard_layout("login")
    ids = [w["id"] for sc in layout["screens"] for w in sc["widgets"]]
    assert "account" in ids
    assert "password" in ids


def test_lua_reads_block_for_full_template():
    layout = build_wizard_layout("full")
    code = lua_reads_block_for_layout(layout)
    assert 'panel.get("account")' in code
    assert 'panel.get("mode")' in code
    assert "bot.log" in code
    assert "panel.is" in code


def test_safe_lua_var():
    assert safe_lua_var("account") == "account"
    assert safe_lua_var("auto-login").startswith("v_")


def test_demo_game_lua_block():
    path = Path(__file__).resolve().parents[1] / "examples" / "demo-game" / "ui" / "layout.json"
    layout = migrate_layout(json.loads(path.read_text(encoding="utf-8")))
    code = lua_reads_block_for_layout(layout)
    assert "delay_sec" in code
    assert "loop_count" in code
