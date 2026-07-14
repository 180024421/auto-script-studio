"""打包 / 安装结果摘要。"""

from __future__ import annotations

from pathlib import Path

from packager.layout_verify import verify_apk_layout
from packager.pack_metadata import read_project_cfg


def build_pack_result_summary(
    project_dir: Path,
    *,
    apk_path: Path | None,
    installed: bool = False,
    launched: bool = False,
    device_serial: str = "",
) -> dict:
    project_dir = project_dir.resolve()
    cfg = read_project_cfg(project_dir)
    layout = verify_apk_layout(apk_path, project_dir) if apk_path else {
        "ok": False,
        "expected_title": "",
        "actual_title": "",
        "message": "未生成 APK",
        "has_layout": False,
    }
    apk_size_kb = 0
    if apk_path and apk_path.is_file():
        apk_size_kb = apk_path.stat().st_size // 1024
    runtime = cfg.get("runtime") or {}
    perf = runtime.get("perf") or {}
    return {
        "name": str(cfg.get("name", "")),
        "package_id": str(cfg.get("package_id", "")),
        "version_code": int(cfg.get("version_code", 1)),
        "version_name": str(cfg.get("version_name", "1.0.0")),
        "apk_path": str(apk_path) if apk_path else "",
        "apk_size_kb": apk_size_kb,
        "installed": installed,
        "launched": launched,
        "device_serial": device_serial,
        "layout_ok": layout.get("ok", False),
        "panel_title": layout.get("expected_title") or layout.get("actual_title") or "",
        "layout_message": layout.get("message", ""),
        "input_mode": str(runtime.get("input_mode", "auto")),
        "screenshot_mode": str(runtime.get("screenshot_mode", "media_projection")),
        "yolo_imgsz": int(perf.get("yolo_imgsz") or 320),
        "jiaoben_project_id": int((cfg.get("jiaoben") or {}).get("project_id") or 0),
    }
