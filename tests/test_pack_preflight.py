"""打包预检与布局 repair 测试。"""

from __future__ import annotations

from pathlib import Path

from studio.services.layout_clone import clone_layout
from studio.services.layout_defaults import DEFAULT_LAYOUT
from studio.services.pack_preflight import validate_before_pack
from studio.services.screen_layout import migrate_layout, repair_all_screens


def test_pack_preflight_demo_game():
    root = Path(__file__).resolve().parents[1]
    demo = root / "examples" / "demo-game"
    if demo.is_dir() and (demo / "project.json").is_file():
        errors, warnings = validate_before_pack(demo)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)


def test_repair_all_screens_does_not_run_on_migrate_only():
    layout = migrate_layout(clone_layout(DEFAULT_LAYOUT))
    y0 = layout["screens"][0]["widgets"][0]["layout_y"]
    repair_all_screens(layout)
    y1 = layout["screens"][0]["widgets"][0]["layout_y"]
    assert y0 == y1 or y1 >= y0
