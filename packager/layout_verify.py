"""打包后校验 APK 内 layout 与工程一致。"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


def read_layout_title_from_apk(apk_path: Path) -> str | None:
    apk_path = apk_path.resolve()
    if not apk_path.is_file():
        return None
    with zipfile.ZipFile(apk_path) as zf:
        try:
            raw = zf.read("assets/project/ui/layout.json").decode("utf-8")
        except KeyError:
            return None
    return str(json.loads(raw).get("panel", {}).get("title", "") or "")


def expected_layout_title(project_dir: Path) -> str:
    layout_path = project_dir / "ui" / "layout.json"
    if not layout_path.is_file():
        return ""
    return str(json.loads(layout_path.read_text(encoding="utf-8")).get("panel", {}).get("title", "") or "")


def verify_apk_layout(apk_path: Path, project_dir: Path) -> dict:
    """
    返回 {ok, expected_title, actual_title, message, has_layout}.
    """
    expected = expected_layout_title(project_dir)
    if not expected:
        return {
            "ok": True,
            "expected_title": "",
            "actual_title": "",
            "message": "工程无 ui/layout.json，跳过 layout 校验",
            "has_layout": False,
        }
    if not apk_path.is_file():
        return {
            "ok": False,
            "expected_title": expected,
            "actual_title": "",
            "message": f"APK 不存在: {apk_path}",
            "has_layout": True,
        }
    actual = read_layout_title_from_apk(apk_path)
    if actual is None:
        return {
            "ok": False,
            "expected_title": expected,
            "actual_title": "",
            "message": "APK 内缺少 assets/project/ui/layout.json",
            "has_layout": True,
        }
    if actual != expected:
        return {
            "ok": False,
            "expected_title": expected,
            "actual_title": actual,
            "message": f"panel.title 不一致：期望 {expected!r}，APK 内 {actual!r}",
            "has_layout": True,
        }
    return {
        "ok": True,
        "expected_title": expected,
        "actual_title": actual,
        "message": f"layout 校验通过（panel.title = {expected!r}）",
        "has_layout": True,
    }
