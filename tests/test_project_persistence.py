"""project_persistence 单元测试。"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from studio.services.project_persistence import (
    export_project_zip,
    get_last_project,
    get_recent_projects,
    import_project_zip,
    is_valid_project,
    load_config,
    remember_project,
    save_config,
    studio_config_dir,
)


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTO_SCRIPT_STUDIO_CONFIG", str(tmp_path))
    return tmp_path


def _make_project(root: Path, name: str = "demo") -> Path:
    project = root / name
    project.mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"name": name, "package_id": "com.test.app", "entry": "main.lua"}),
        encoding="utf-8",
    )
    (project / "main.lua").write_text("print('hi')\n", encoding="utf-8")
    ui = project / "ui"
    ui.mkdir()
    (ui / "layout.json").write_text('{"enabled": true, "widgets": []}\n', encoding="utf-8")
    studio = project / ".studio"
    studio.mkdir()
    (studio / "panel-state.json").write_text('{"w_1": "on"}\n', encoding="utf-8")
    return project


def test_is_valid_project(tmp_path: Path):
    project = _make_project(tmp_path)
    assert is_valid_project(project)
    assert not is_valid_project(tmp_path / "missing")


def test_remember_and_restore_recent(config_home: Path, tmp_path: Path):
    p1 = _make_project(tmp_path, "a")
    p2 = _make_project(tmp_path, "b")
    remember_project(p1)
    remember_project(p2)
    assert get_last_project() == p2.resolve()
    recent = get_recent_projects()
    assert recent[0] == p2.resolve()
    assert p1.resolve() in recent
    cfg = load_config()
    assert cfg["last_project"] == str(p2.resolve())


def test_export_and_import_roundtrip(tmp_path: Path):
    project = _make_project(tmp_path, "src")
    (project / "image").mkdir()
    (project / "image" / "a.png").write_bytes(b"png")
    zip_path = tmp_path / "out.zip"
    export_project_zip(project, zip_path)
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
    assert "src/project.json" in names
    assert "src/main.lua" in names
    assert "src/ui/layout.json" in names
    assert "src/.studio/panel-state.json" in names

    dest = tmp_path / "imported"
    imported = import_project_zip(zip_path, dest)
    assert is_valid_project(imported)
    assert json.loads((imported / "project.json").read_text(encoding="utf-8"))["name"] == "src"
    assert (imported / "main.lua").read_text(encoding="utf-8").startswith("print")
    assert (imported / ".studio" / "panel-state.json").is_file()


def test_import_single_root_folder(tmp_path: Path):
    project = _make_project(tmp_path, "bundle")
    zip_path = tmp_path / "bundle.zip"
    export_project_zip(project, zip_path)
    dest = tmp_path / "target"
    imported = import_project_zip(zip_path, dest)
    assert imported.name == "bundle"
    assert is_valid_project(imported)


def test_studio_config_dir_env(config_home: Path):
    assert studio_config_dir() == config_home
    save_config({"last_project": "/x", "recent": ["/a"]})
    assert load_config()["last_project"] == "/x"
