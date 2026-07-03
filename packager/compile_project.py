"""打包前：将 Lua / YAML 等工程整理为 APK assets。"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

_SKIP = {"__pycache__", ".git", ".venv", "venv", "dist", "build", ".idea", "node_modules"}


def _detect_language(entry: str) -> str:
    ext = Path(entry).suffix.lower()
    return {
        ".yaml": "yaml",
        ".yml": "yaml",
        ".py": "python",
        ".lua": "lua",
    }.get(ext, "unknown")


def is_lua_project(cfg: dict) -> bool:
    lang = (cfg.get("script_language") or "auto").lower()
    entry = cfg.get("entry", "main.lua")
    if lang == "lua":
        return True
    if lang in ("yaml", "yml"):
        return False
    return str(entry).lower().endswith(".lua")


def resolve_runtime_entry(project_dir: Path, cfg: dict) -> Path:
    """APK 内实际执行的入口文件。"""
    project_dir = project_dir.resolve()
    entry = cfg.get("entry", "main.lua")
    entry_path = project_dir / entry
    if not entry_path.is_file():
        raise FileNotFoundError(f"入口脚本不存在: {entry_path}")

    if is_lua_project(cfg):
        return entry_path

    pack_entry = (cfg.get("pack_entry") or "").strip()
    if pack_entry:
        path = project_dir / pack_entry
        if not path.is_file():
            raise FileNotFoundError(f"pack_entry 不存在: {path}")
        return path

    for name in ("game.yaml", "main.yaml"):
        p = project_dir / name
        if p.is_file():
            return p

    if entry_path.suffix.lower() in (".yaml", ".yml"):
        return entry_path

    lang = cfg.get("script_language") or _detect_language(entry)
    if lang == "python":
        raise FileNotFoundError(
            "Python 工程打包需 game.yaml；建议改用 Lua 入口 main.lua。"
        )
    raise FileNotFoundError(f"找不到可打包的运行时入口（entry={entry}）")


# 兼容旧 import
resolve_runtime_yaml = resolve_runtime_entry


def prepare_staging_dir(project_dir: Path) -> tuple[Path, dict]:
    project_dir = project_dir.resolve()
    cfg_path = project_dir / "project.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"缺少 project.json: {cfg_path}")

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    runtime_entry = resolve_runtime_entry(project_dir, cfg)
    dev_entry = cfg.get("entry", runtime_entry.name)

    staging = Path(tempfile.mkdtemp(prefix="auto-script-pack-"))

    def _ignore(_dir: str, names: list[str]) -> set[str]:
        return {n for n in names if n in _SKIP}

    shutil.copytree(project_dir, staging, dirs_exist_ok=True, ignore=_ignore)

    apk_cfg = dict(cfg)
    apk_cfg["entry"] = runtime_entry.name
    apk_cfg.setdefault("script_language", "lua" if is_lua_project(cfg) else _detect_language(dev_entry))
    apk_cfg["dev_entry"] = dev_entry
    if is_lua_project(cfg):
        apk_cfg["script_language"] = "lua"
    elif "pack_entry" not in apk_cfg and runtime_entry.name != dev_entry:
        apk_cfg["pack_entry"] = runtime_entry.name

    (staging / "project.json").write_text(
        json.dumps(apk_cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return staging, apk_cfg


def cleanup_staging(staging: Path | None) -> None:
    if staging and staging.is_dir() and staging.name.startswith("auto-script-pack-"):
        shutil.rmtree(staging, ignore_errors=True)
