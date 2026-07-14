"""性能场景检测测试。"""

from __future__ import annotations

from studio.services.runtime_presets import PRESETS, SCENARIO_HINTS, detect_current_preset


def test_scenario_hints_cover_presets() -> None:
    for key in PRESETS:
        assert key in SCENARIO_HINTS


def test_detect_yolo_fast_preset() -> None:
    cfg = {"runtime": PRESETS["yolo_fast"]["runtime"].copy()}
    cfg["runtime"]["perf"] = dict(PRESETS["yolo_fast"]["runtime"]["perf"])
    assert detect_current_preset(cfg) == "yolo_fast"
