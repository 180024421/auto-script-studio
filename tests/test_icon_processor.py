"""icon_processor 单元测试。"""

from __future__ import annotations

from pathlib import Path

from packager.icon_processor import (
    default_icon_path,
    flood_remove_outer_white,
    make_launcher_icon,
    prepare_pack_icons,
    resolve_icon_source,
    style_ball_icon,
)

ROOT = Path(__file__).resolve().parents[1]


def test_default_icon_exists():
    assert default_icon_path().is_file()


def test_resolve_icon_fallback():
    cfg = {"name": "t", "package_id": "com.test.app", "entry": "main.lua"}
    path = resolve_icon_source(ROOT / "examples" / "demo-game", cfg)
    assert path == default_icon_path()


def test_prepare_pack_icons_outputs():
    import tempfile

    project = ROOT / "examples" / "demo-game"
    cfg = {"name": "demo", "package_id": "com.test.demo", "entry": "main.lua"}
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        src = prepare_pack_icons(project, cfg, ROOT / "android-runtime", staging)
        assert src.is_file()
        assert (staging / "ui" / "ball.png").is_file()
        gen = ROOT / "android-runtime" / "packager" / "generated-res" / "mipmap-xxhdpi" / "ic_launcher.png"
        assert gen.is_file()


def test_flood_and_ball_alpha():
    from PIL import Image

    src = default_icon_path()
    img = Image.open(src)
    cut = flood_remove_outer_white(img)
    ball = style_ball_icon(img)
    assert cut.getchannel("A").getextrema()[1] > 0
    assert ball.getchannel("A").getextrema()[1] > 0
    launcher = make_launcher_icon(img, 96)
    assert launcher.size == (96, 96)
