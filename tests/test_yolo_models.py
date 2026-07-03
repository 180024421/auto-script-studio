"""YOLO 模型与 Lua 片段测试。"""

from __future__ import annotations

from pathlib import Path

from studio.services import lua_snippets
from studio.services.yolo_models import (
    labels_path_for,
    load_class_names,
    merge_class_names_from_detections,
    model_rel_path,
)


def test_labels_path_for():
    assert labels_path_for(Path("models/ui.onnx")) == Path("models/ui.labels")


def test_load_class_names_from_labels(tmp_path: Path):
    model = tmp_path / "models" / "ui.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"")
    labels = model.with_suffix(".labels")
    labels.write_text("hand\neye\n", encoding="utf-8")
    assert load_class_names(model) == ["hand", "eye"]


def test_merge_class_names_from_detections():
    merged = merge_class_names_from_detections(
        ["a"],
        [{"class_name": "b"}, {"class_name": "a"}],
    )
    assert merged == ["a", "b"]


def test_model_rel_path(tmp_path: Path):
    project = tmp_path / "proj"
    model = project / "models" / "ui.onnx"
    model.parent.mkdir(parents=True)
    model.touch()
    assert model_rel_path(project, model) == "models/ui.onnx"


def test_find_yolo_click_with_offset():
    code = lua_snippets.find_yolo(
        "models/ui.onnx",
        class_name="hand",
        tap_dx=10,
        tap_dy=-5,
        delay_before_click=0.3,
        click=True,
    )
    assert "bot.delay(0.3)" in code
    assert "yx + 10" in code
    assert "yy + -5" in code or "yy - 5" in code or "yy + -5" in code


def test_yolo_swipe_snippet():
    code = lua_snippets.yolo_swipe("models/ui.onnx", class_name="hand", direction="up")
    assert "bot.yoloSwipe" in code
    assert 'direction = "up"' in code


def test_normalize_detection():
    from studio.services.yolo_models import normalize_detection, normalize_detections

    d = normalize_detection({"class_name": "a", "confidence": 0.9, "x": 10, "y": 20, "w": 30, "h": 40})
    assert d["center_x"] == 25
    assert d["center_y"] == 40
    assert len(normalize_detections([d])) == 1


def test_set_default_model(tmp_path: Path):
    from studio.services.yolo_models import read_default_model_rel, set_default_model

    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    set_default_model(project, "models/ui.onnx")
    assert read_default_model_rel(project) == "models/ui.onnx"


def test_import_models(tmp_path: Path):
    from studio.services.yolo_models import import_models, list_yolo_models

    project = tmp_path / "proj"
    src = tmp_path / "m.onnx"
    src.write_bytes(b"onnx")
    (tmp_path / "m.labels").write_text("a\n", encoding="utf-8")
    imported = import_models(project, [src])
    assert len(imported) == 1
    assert list_yolo_models(project)


def test_find_node_snippet():
    code = lua_snippets.find_node(text="设置", click=True, optional=True)
    assert "bot.findNode" in code
    assert 'text = "设置"' in code
    assert "click = true" in code
    assert "optional = true" in code
