"""pack_metadata 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

from packager.pack_metadata import escape_gradle_property, save_pack_metadata


def test_escape_chinese_app_name():
    assert "\\u5927" in escape_gradle_property("大帅测试")


def test_save_pack_metadata_with_icon(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps({"name": "t", "package_id": "com.test.app", "entry": "main.lua"}),
        encoding="utf-8",
    )
    (project / "main.lua").write_text("-- test\n", encoding="utf-8")
    icon = tmp_path / "custom.png"
    icon.write_bytes(b"\x89PNG\r\n\x1a\n")

    cfg = save_pack_metadata(
        project,
        name="我的脚本",
        package_id="com.example.script",
        icon_text=str(icon),
    )
    assert cfg["name"] == "我的脚本"
    assert cfg["icon"] == "icon.png"
    assert (project / "icon.png").is_file()
