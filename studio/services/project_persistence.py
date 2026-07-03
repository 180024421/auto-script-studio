"""Studio 工程持久化：最近工程记录、ZIP 导入导出。"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any

_CONFIG_VERSION = 1
_MAX_RECENT = 12

_EXPORT_SKIP_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", "node_modules", ".venv"})
_EXPORT_SKIP_SUFFIXES = frozenset({".pyc", ".pyo"})


def studio_config_dir() -> Path:
    override = os.environ.get("AUTO_SCRIPT_STUDIO_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".auto-script-studio"


def config_path() -> Path:
    return studio_config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.is_file():
        return {"version": _CONFIG_VERSION, "last_project": "", "recent": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": _CONFIG_VERSION, "last_project": "", "recent": []}
    if not isinstance(data, dict):
        return {"version": _CONFIG_VERSION, "last_project": "", "recent": []}
    data.setdefault("version", _CONFIG_VERSION)
    data.setdefault("last_project", "")
    data.setdefault("recent", [])
    return data


def save_config(cfg: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _CONFIG_VERSION,
        "last_project": str(cfg.get("last_project") or ""),
        "recent": [str(p) for p in cfg.get("recent") or []],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_valid_project(path: Path) -> bool:
    try:
        return path.is_dir() and (path / "project.json").is_file()
    except OSError:
        return False


def remember_project(project_dir: Path, *, max_recent: int = _MAX_RECENT) -> None:
    resolved = project_dir.resolve()
    if not is_valid_project(resolved):
        return
    key = str(resolved)
    cfg = load_config()
    recent = [p for p in cfg.get("recent") or [] if p and p != key]
    recent.insert(0, key)
    cfg["last_project"] = key
    cfg["recent"] = recent[:max_recent]
    save_config(cfg)


def get_last_project() -> Path | None:
    cfg = load_config()
    raw = str(cfg.get("last_project") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if is_valid_project(path) else None


def get_recent_projects(*, limit: int = _MAX_RECENT) -> list[Path]:
    cfg = load_config()
    out: list[Path] = []
    for raw in cfg.get("recent") or []:
        path = Path(str(raw))
        if is_valid_project(path) and path not in out:
            out.append(path)
        if len(out) >= limit:
            break
    return out


def _should_export(rel: Path) -> bool:
    parts = rel.parts
    if parts and parts[0] in _EXPORT_SKIP_DIRS:
        return False
    if any(part in _EXPORT_SKIP_DIRS for part in parts):
        return False
    if rel.suffix.lower() in _EXPORT_SKIP_SUFFIXES:
        return False
    return True


def export_project_zip(project_dir: Path, zip_path: Path) -> None:
    root = project_dir.resolve()
    if not is_valid_project(root):
        raise ValueError(f"不是有效的脚本工程: {root}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = root.name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(root.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root)
            if not _should_export(rel):
                continue
            arcname = f"{prefix}/{rel}".replace("\\", "/")
            zf.write(file_path, arcname=arcname)


def _find_project_root(directory: Path) -> Path | None:
    if is_valid_project(directory):
        return directory
    children = [p for p in directory.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if len(children) == 1 and is_valid_project(children[0]):
        return children[0]
    for child in children:
        if is_valid_project(child):
            return child
    return None


def import_project_zip(zip_path: Path, dest_dir: Path) -> Path:
    if not zip_path.is_file():
        raise ValueError(f"ZIP 文件不存在: {zip_path}")
    dest_dir = dest_dir.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [n for n in zf.namelist() if n and not n.endswith("/")]
        if not names:
            raise ValueError("ZIP 文件为空")
        top_levels = {n.split("/")[0] for n in names if "/" in n}
        single_root = len(top_levels) == 1 and all("/" in n for n in names)
        if single_root:
            root_name = next(iter(top_levels))
            target = dest_dir / root_name
            if target.exists() and any(target.iterdir()):
                raise ValueError(f"目标目录非空: {target}")
            target.mkdir(parents=True, exist_ok=True)
            zf.extractall(dest_dir)
            project = _find_project_root(target)
        else:
            if any(dest_dir.iterdir()):
                raise ValueError(f"目标目录非空: {dest_dir}")
            zf.extractall(dest_dir)
            project = _find_project_root(dest_dir)
    if project is None:
        raise ValueError("ZIP 中未找到含 project.json 的脚本工程")
    return project
