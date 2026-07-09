"""adb-ide YOLO 导入桥接测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from studio.services.adb_ide_import import read_names_from_data_yaml, resolve_best_pt


def test_resolve_best_pt_from_weights_dir(tmp_path: Path):
    weights = tmp_path / "weights"
    weights.mkdir()
    pt = weights / "best.pt"
    pt.write_bytes(b"fake")
    assert resolve_best_pt(tmp_path) == pt


def test_resolve_best_pt_direct_file(tmp_path: Path):
    pt = tmp_path / "best.pt"
    pt.write_bytes(b"fake")
    assert resolve_best_pt(pt) == pt


def test_resolve_best_pt_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        resolve_best_pt(tmp_path)


def test_read_names_from_data_yaml(tmp_path: Path):
    yaml_path = tmp_path / "data.yaml"
    yaml_path.write_text("names:\n  0: btn\n  1: icon\n", encoding="utf-8")
    names = read_names_from_data_yaml(tmp_path)
    assert names == ["btn", "icon"]
