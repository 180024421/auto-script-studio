"""增强功能测试：工具箱、训练导出、dataset yaml、录制。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from studio.services.action_recorder import ActionRecorder
from studio.services.bot_command_catalog import all_commands, search_commands
from studio.services.dataset_yaml import write_data_yaml
from studio.services.training_export import export_yolo_sample


def test_bot_catalog_new_apis():
    ids = {c.id for c in all_commands()}
    assert "bot.waitGoneImage" in ids
    assert "bot.waitStable" in ids
    assert "bot.findMultiColor" in ids
    assert "bot.trace" in ids
    hits = search_commands("scale")
    assert any("findImage" in c.api for c in hits)


def test_training_export_seg_task(tmp_path: Path):
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    dets = [
        {
            "class_name": "btn",
            "x": 10,
            "y": 10,
            "w": 30,
            "h": 30,
            "has_mask": True,
            "mask_center_x": 25,
            "mask_center_y": 25,
        }
    ]
    out = export_yolo_sample(tmp_path, img, dets, class_names=["btn"])
    assert out.is_file()
    lbl = tmp_path / "dataset" / "labels" / (out.stem + ".txt")
    text = lbl.read_text(encoding="utf-8").strip()
    assert text.startswith("0 ")
    parts = text.split()
    assert len(parts) > 5  # seg 多边形


def test_write_data_yaml(tmp_path: Path):
    ds = tmp_path / "dataset" / "labels"
    ds.mkdir(parents=True)
    (ds / "a.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    out = write_data_yaml(tmp_path, class_names=["btn"])
    assert out.is_file()
    assert "names:" in out.read_text(encoding="utf-8")


def test_action_recorder_yolo_step():
    rec = ActionRecorder()
    rec.start()
    rec.find_yolo("models/ui.onnx", class_name="hand", use_mask_center=True)
    rec.stop()
    lua = rec.to_lua()
    assert "findYolo" in lua
    assert "use_mask_center" in lua
