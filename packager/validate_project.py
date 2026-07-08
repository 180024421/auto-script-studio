"""打包器校验增强。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from packager.compile_project import resolve_runtime_entry

_IMAGE_REF = re.compile(r"""findImage\s*\(\s*['"]([^'"]+)['"]""")
_ONNX_REF = re.compile(r"""models/[^'"]+\.onnx""")


def _collect_lua_sources(project_dir: Path, cfg: dict) -> list[Path]:
    files = []
    entry = project_dir / cfg.get("entry", "main.lua")
    if entry.is_file():
        files.append(entry)
    lib_dir = project_dir / "lib"
    if lib_dir.is_dir():
        files.extend(sorted(lib_dir.glob("*.lua")))
    return files


def validate_assets(project_dir: Path, cfg: dict) -> list[str]:
    warnings: list[str] = []
    errors: list[str] = []
    project_dir = project_dir.resolve()

    for lua in _collect_lua_sources(project_dir, cfg):
        text = lua.read_text(encoding="utf-8")
        for m in _IMAGE_REF.finditer(text):
            rel = m.group(1)
            if not (project_dir / rel).is_file():
                errors.append(f"引用的模板图不存在: {rel} (来自 {lua.name})")

    for onnx in project_dir.glob("models/**/*.onnx"):
        labels = onnx.with_suffix(".labels")
        if not labels.is_file():
            labels2 = onnx.parent / (onnx.stem + ".labels")
            if not labels2.is_file():
                warnings.append(f"YOLO 模型缺少 .labels: {onnx.relative_to(project_dir)}")

    layout = project_dir / "ui" / "layout.json"
    if layout.is_file():
        try:
            import json

            data = json.loads(layout.read_text(encoding="utf-8"))
            version = int(data.get("version", 1))
            if version < 3 and "buttons" not in data and not data.get("widgets"):
                warnings.append("ui/layout.json 缺少 widgets/buttons")
            try:
                from studio.services.layout_validate import validate_layout

                for msg in validate_layout(data):
                    errors.append(f"layout: {msg}")
            except ImportError:
                pass
        except json.JSONDecodeError as exc:
            errors.append(f"ui/layout.json JSON 无效: {exc}")

    return errors, warnings


def validate_project_full(project_dir: Path) -> dict:
    project_dir = project_dir.resolve()
    cfg_path = project_dir / "project.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"缺少 project.json: {cfg_path}")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    dev_entry = cfg.get("entry", "main.lua")
    if not (project_dir / dev_entry).is_file():
        raise FileNotFoundError(f"入口脚本不存在: {project_dir / dev_entry}")
    if not cfg.get("package_id"):
        raise ValueError("project.json 缺少 package_id")
    resolve_runtime_entry(project_dir, cfg)
    errors, warnings = validate_assets(project_dir, cfg)
    if errors:
        raise ValueError("校验失败:\n" + "\n".join(f"  - {e}" for e in errors))
    return {"cfg": cfg, "warnings": warnings}
