"""layout 校验与发版写回测试。"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from packager.layout_verify import expected_layout_title, verify_apk_layout
from packager.publish_update import write_back_version


def test_write_back_version(tmp_path: Path) -> None:
    proj = tmp_path / "demo"
    proj.mkdir()
    (proj / "project.json").write_text(
        json.dumps({"version_code": 1, "version_name": "1.0.0"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    cfg = write_back_version(proj, 3, version_name="1.0.2")
    assert cfg["version_code"] == 3
    assert cfg["version_name"] == "1.0.2"
    saved = json.loads((proj / "project.json").read_text(encoding="utf-8"))
    assert saved["version_code"] == 3


def test_verify_apk_layout_ok(tmp_path: Path) -> None:
    proj = tmp_path / "game"
    proj.mkdir()
    (proj / "ui").mkdir()
    title = "测试助手"
    (proj / "ui" / "layout.json").write_text(
        json.dumps({"panel": {"title": title}}, ensure_ascii=False),
        encoding="utf-8",
    )
    apk = tmp_path / "test.apk"
    layout_bytes = json.dumps({"panel": {"title": title}}, ensure_ascii=False).encode()
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("assets/project/ui/layout.json", layout_bytes)
    result = verify_apk_layout(apk, proj)
    assert result["ok"] is True
    assert result["expected_title"] == title
    assert expected_layout_title(proj) == title


def test_verify_apk_layout_mismatch(tmp_path: Path) -> None:
    proj = tmp_path / "game"
    proj.mkdir()
    (proj / "ui").mkdir()
    (proj / "ui" / "layout.json").write_text(
        json.dumps({"panel": {"title": "新标题"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    apk = tmp_path / "test.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr(
            "assets/project/ui/layout.json",
            json.dumps({"panel": {"title": "旧标题"}}, ensure_ascii=False).encode(),
        )
    result = verify_apk_layout(apk, proj)
    assert result["ok"] is False
