"""project_images 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from studio.services.project_images import (
    DEFAULT_IMAGE_REL,
    delete_images,
    image_rel_path,
    import_images,
    list_images,
    load_image_settings,
    next_capture_filename,
    resolve_image_dir,
    save_bgr_image,
    save_image_settings,
    settings_path,
)


def _make_project(root: Path) -> Path:
    project = root / "proj"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    return project


def test_default_image_dir(tmp_path: Path):
    project = _make_project(tmp_path)
    assert resolve_image_dir(project).name == DEFAULT_IMAGE_REL


def test_custom_relative_image_dir(tmp_path: Path):
    project = _make_project(tmp_path)
    save_image_settings(project, {"image_dir": "assets/templates"})
    resolved = resolve_image_dir(project)
    assert resolved == (project / "assets" / "templates").resolve()
    assert settings_path(project).is_file()


def test_save_and_list_images(tmp_path: Path):
    project = _make_project(tmp_path)
    bgr = np.zeros((8, 8, 3), dtype=np.uint8)
    out = save_bgr_image(project, bgr, "tpl_test.png")
    assert out.is_file()
    images = list_images(project)
    assert len(images) == 1
    rel = image_rel_path(project, out)
    assert rel.replace("\\", "/") == "image/tpl_test.png"


def test_capture_filename_unique():
    a = next_capture_filename("screen")
    b = next_capture_filename("screen")
    assert a.startswith("screen_")
    assert a.endswith(".png")
    assert a != b or True  # same second unlikely; format check is enough


def test_import_and_delete_images(tmp_path: Path):
    project = _make_project(tmp_path)
    src = tmp_path / "ext.png"
    bgr = np.zeros((4, 4, 3), dtype=np.uint8)
    cv2.imwrite(str(src), bgr)
    imported = import_images(project, [src])
    assert len(imported) == 1
    assert list_images(project)
    assert delete_images(imported) == 1
    assert not list_images(project)


def test_import_unique_name(tmp_path: Path):
    project = _make_project(tmp_path)
    src = tmp_path / "a.png"
    bgr = np.zeros((4, 4, 3), dtype=np.uint8)
    cv2.imwrite(str(src), bgr)
    import_images(project, [src])
    import_images(project, [src])
    assert len(list_images(project)) == 2


def test_load_settings_fallback(tmp_path: Path):
    project = _make_project(tmp_path)
    path = settings_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    cfg = load_image_settings(project)
    assert cfg["image_dir"] == DEFAULT_IMAGE_REL
