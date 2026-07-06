"""打包预检与发版工具测试。"""

from __future__ import annotations

from pathlib import Path

from studio.services.pack_preflight import validate_before_pack


def test_pack_preflight_demo_game():
    root = Path(__file__).resolve().parents[1]
    demo = root / "examples" / "demo-game"
    if demo.is_dir() and (demo / "project.json").is_file():
        issues = validate_before_pack(demo)
        assert isinstance(issues, list)


def test_publish_update_import():
    from packager.publish_update import build_update_zip, publish_to_jiaoben

    assert callable(build_update_zip)
    assert callable(publish_to_jiaoben)
