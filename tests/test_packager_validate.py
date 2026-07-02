"""Packager 校验单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_validate_ldplayer_test():
    from packager.packager_cli import validate_project

    cfg = validate_project(ROOT / "examples" / "ldplayer-test")
    assert cfg["package_id"]


def test_validate_demo_game():
    from packager.packager_cli import validate_project

    cfg = validate_project(ROOT / "examples" / "demo-game")
    assert cfg["entry"] == "main.lua"


def test_layout_json_parse():
    from packager.validate_project import validate_assets

    project = ROOT / "examples" / "demo-game"
    cfg = json.loads((project / "project.json").read_text(encoding="utf-8"))
    errors, warnings = validate_assets(project, cfg)
    assert not errors


def test_missing_image_reference():
    from packager.validate_project import validate_assets

    errors, _ = validate_assets(ROOT / "examples" / "demo-game", {"entry": "main.lua"})
    assert not errors
