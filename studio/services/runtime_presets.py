"""project.json runtime 性能预设。"""

from __future__ import annotations

import json
from copy import deepcopy
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
