"""bot 命令目录测试。"""

from __future__ import annotations

from studio.services.bot_command_catalog import all_commands, find_command, search_commands


def test_all_commands_not_empty():
    cmds = all_commands()
    assert len(cmds) >= 10
    ids = {c.id for c in cmds}
    assert "bot.tap" in ids
    assert "panel.get" in ids


def test_find_command():
    cmd = find_command("bot.findImage")
    assert cmd is not None
    assert cmd.category == "图色命令"
    assert "findImage" in cmd.snippet


def test_search_commands():
    hits = search_commands("yolo")
    assert any(c.id == "bot.findYolo" for c in hits)
    assert search_commands("") == all_commands()
