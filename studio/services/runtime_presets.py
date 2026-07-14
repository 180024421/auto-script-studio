"""project.json runtime 性能预设。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "yolo_fast": {
        "label": "极速 YOLO（root点击+录屏）",
        "runtime": {
            "input_mode": "root",
            "screenshot_mode": "media_projection",
            "ocr_mode": "lazy",
            "default_interval_ms": 300,
            "perf": {
                "yolo_nnapi": True,
                "yolo_imgsz": 320,
                "capture_cache_ttl_ms": 80,
            },
        },
    },
    "less_perm": {
        "label": "少授权（仅无障碍截图）",
        "runtime": {
            "input_mode": "accessibility",
            "screenshot_mode": "accessibility",
            "ocr_mode": "lazy",
            "perf": {"yolo_nnapi": True, "yolo_imgsz": 320},
        },
    },
    "yolo_seg_fast": {
        "label": "seg 极速（adb-ide → APK）",
        "runtime": {
            "yolo_auto_mask_center": True,
            "perf": {
                "yolo_nnapi": True,
                "yolo_imgsz": 320,
                "yolo_warmup": True,
                "yolo_seg_fast": True,
                "yolo_max_mask_decode": 1,
                "capture_cache_ttl_ms": 80,
            },
        },
    },
    "root_compat": {
        "label": "纯 root（兼容向）",
        "runtime": {
            "input_mode": "root",
            "screenshot_mode": "root",
            "ocr_mode": "lazy",
            "perf": {"yolo_nnapi": False, "yolo_imgsz": 320},
        },
    },
}


SCENARIO_HINTS: dict[str, str] = {
    "yolo_fast": "有 root、追求 YOLO 与截屏速度。适合高频找图/找 UI。",
    "less_perm": "无 root，仅无障碍截图。授权少，单次截屏较慢。",
    "yolo_seg_fast": "seg 掩码模型（adb-ide 导入）。限制掩码解码数量以提速。",
    "root_compat": "老设备或 NNAPI 不稳定时关闭 NNAPI，兼容性优先。",
}


def detect_current_preset(cfg: dict) -> str:
    runtime = cfg.get("runtime") or {}
    perf = runtime.get("perf") or {}
    for key, preset in PRESETS.items():
        pr = preset.get("runtime") or {}
        pp = pr.get("perf") or {}
        match = True
        for k, v in pr.items():
            if k == "perf":
                continue
            if runtime.get(k) != v:
                match = False
                break
        if not match:
            continue
        for k, v in pp.items():
            if perf.get(k) != v:
                match = False
                break
        if match:
            return key
    return "yolo_fast"


def apply_preset(project_dir: Path, preset_key: str) -> str:
    preset = PRESETS.get(preset_key)
    if preset is None:
        raise ValueError(f"未知预设: {preset_key}")
    path = project_dir / "project.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    runtime = cfg.setdefault("runtime", {})
    for key, val in preset["runtime"].items():
        if key == "perf" and isinstance(val, dict):
            perf = runtime.setdefault("perf", {})
            perf.update(val)
        else:
            runtime[key] = val
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(preset["label"])
