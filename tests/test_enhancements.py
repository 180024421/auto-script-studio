"""新增能力单元测试。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from studio.services.action_recorder import ActionRecorder
from studio.services.onnx_inspect import inspect_onnx, validate_onnx_for_pack
from studio.services.training_export import export_yolo_sample
from studio.services.vision_pc import _scale_list, find_multi_point_color, match_template


def test_action_recorder_to_lua():
    rec = ActionRecorder()
    rec.start()
    rec.tap(10, 20)
    rec.delay(0.5)
    rec.stop()
    code = rec.to_lua()
    assert "bot.tap(10, 20)" in code
    assert "bot.delay(0.5)" in code


def test_scale_list():
    scales = _scale_list(0.9, 1.1, 0.1)
    assert 0.9 in scales
    assert 1.0 in scales
    assert 1.1 in scales


def test_find_multi_point_color():
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    img[5, 5] = (10, 20, 30)
    img[5, 6] = (11, 21, 31)
    pt = find_multi_point_color(img, [(0, 0, (10, 20, 30)), (1, 0, (11, 21, 31))], tol=2)
    assert pt == (5, 5)


def test_match_template_multiscale():
    screen = np.zeros((100, 100, 3), dtype=np.uint8)
    screen[40:60, 40:60] = 255
    tpl = np.ones((20, 20, 3), dtype=np.uint8) * 255
    m = match_template(screen, tpl, threshold=0.8, scale_min=0.9, scale_max=1.1, scale_step=0.1)
    assert m is not None


def test_inspect_onnx_missing(tmp_path: Path):
    info = inspect_onnx(tmp_path / "missing.onnx")
    assert info["ok"] is False


def test_validate_onnx_for_pack_size_warning(tmp_path: Path):
    big = tmp_path / "big.onnx"
    big.write_bytes(b"x" * (81 * 1024 * 1024))
    _, warnings = validate_onnx_for_pack(big)
    assert any("较大" in w for w in warnings)


def test_export_yolo_sample(tmp_path: Path):
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    dets = [{"class_name": "a", "confidence": 0.9, "x": 10, "y": 10, "w": 20, "h": 20}]
    out = export_yolo_sample(tmp_path, img, dets, class_names=["a"])
    assert out.is_file()
    assert (tmp_path / "dataset" / "labels").is_dir()
