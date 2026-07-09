"""工程设备 profile：记住 ADB serial 与屏幕尺寸。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def profile_path(project_dir: Path) -> Path:
    return project_dir / ".studio" / "device_profile.json"


def load_profile(project_dir: Path) -> dict[str, Any]:
    p = profile_path(project_dir)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_profile(project_dir: Path, *, serial: str = "", width: int = 0, height: int = 0, label: str = "default") -> dict[str, Any]:
    project_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "serial": serial.strip(),
        "width": int(width),
        "height": int(height),
        "label": label.strip() or "default",
    }
    out = profile_path(project_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def sync_to_project_json(project_dir: Path) -> None:
    """将 .studio/device_profile.json 写入 project.json runtime.device_profile。"""
    prof = load_profile(project_dir)
    if not prof:
        return
    cfg_path = project_dir / "project.json"
    if not cfg_path.is_file():
        return
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    runtime = dict(data.get("runtime") or {})
    runtime["device_profile"] = {
        "serial": prof.get("serial", ""),
        "width": prof.get("width", 0),
        "height": prof.get("height", 0),
        "label": prof.get("label", "default"),
    }
    data["runtime"] = runtime
    cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
