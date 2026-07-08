"""设备端 layout 覆盖 ↔ PC 工程同步。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from studio.services.adb_service import AdbService
from studio.services.layout_defaults import load_layout, save_layout
from studio.services.layout_validate import validate_layout
from studio.services.screen_layout import migrate_layout


OVERRIDE_REL = "files/layout-overrides/ui/layout.json"


def _read_override_via_adb(adb: AdbService, package_id: str, serial: str | None) -> str:
    use_serial = serial or adb.default_serial()
    if not use_serial:
        raise RuntimeError("未连接设备")
    rel = OVERRIDE_REL
    attempts = [
        ["exec-out", "run-as", package_id, "cat", rel],
        ["shell", "run-as", package_id, "cat", rel],
    ]
    last_err = ""
    for args in attempts:
        proc = adb._run(args, serial=use_serial, check=False, text=True, timeout=30)
        text = (proc.stdout or "").strip()
        if proc.returncode == 0 and text.startswith("{"):
            return text
        last_err = (proc.stderr or proc.stdout or str(proc.returncode)).strip()
    raise RuntimeError(f"无法读取设备 layout 覆盖（需 debug 包且 run-as 可用）: {last_err}")


def pull_device_layout_override(
    adb: AdbService,
    package_id: str,
    *,
    serial: str | None = None,
) -> dict[str, Any]:
    raw = _read_override_via_adb(adb, package_id, serial)
    data = migrate_layout(json.loads(raw))
    errors = validate_layout(data)
    if errors:
        raise ValueError("设备 layout 校验失败:\n" + "\n".join(errors))
    return data


def merge_override_into_project(
    project_dir: Path,
    override: dict[str, Any],
    *,
    backup: bool = True,
) -> Path:
    project_dir = project_dir.resolve()
    layout_path = project_dir / "ui" / "layout.json"
    if backup and layout_path.is_file():
        bak = layout_path.with_suffix(".json.bak")
        bak.write_text(layout_path.read_text(encoding="utf-8"), encoding="utf-8")
    save_layout(project_dir, override)
    return layout_path


def pull_and_merge_to_project(
    adb: AdbService,
    project_dir: Path,
    package_id: str,
    *,
    serial: str | None = None,
) -> dict[str, Any]:
    override = pull_device_layout_override(adb, package_id, serial=serial)
    merge_override_into_project(project_dir, override)
    return override
