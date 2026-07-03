"""工程识图素材目录：配置、列举、保存截图/模板。"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

DEFAULT_IMAGE_REL = "image"
_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})
_SETTINGS_NAME = "images.json"


def settings_path(project_dir: Path) -> Path:
    return Path(project_dir) / ".studio" / _SETTINGS_NAME


def default_settings() -> dict[str, Any]:
    return {
        "image_dir": DEFAULT_IMAGE_REL,
    }


def load_image_settings(project_dir: Path) -> dict[str, Any]:
    path = settings_path(project_dir)
    if not path.is_file():
        return default_settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_settings()
    if not isinstance(data, dict):
        return default_settings()
    out = default_settings()
    if isinstance(data.get("image_dir"), str) and data["image_dir"].strip():
        out["image_dir"] = data["image_dir"].strip()
    return out


def save_image_settings(project_dir: Path, settings: dict[str, Any]) -> None:
    path = settings_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "image_dir": str(settings.get("image_dir") or DEFAULT_IMAGE_REL).strip() or DEFAULT_IMAGE_REL,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_image_dir(project_dir: Path, settings: dict[str, Any] | None = None) -> Path:
    cfg = settings if settings is not None else load_image_settings(project_dir)
    raw = str(cfg.get("image_dir") or DEFAULT_IMAGE_REL).strip() or DEFAULT_IMAGE_REL
    path = Path(raw)
    if path.is_absolute():
        return path
    return (Path(project_dir) / raw).resolve()


def image_rel_path(project_dir: Path, file_path: Path, settings: dict[str, Any] | None = None) -> str:
    """返回脚本中使用的相对路径，如 image/foo.png。"""
    project = Path(project_dir).resolve()
    resolved = Path(file_path).resolve()
    try:
        rel = resolved.relative_to(project)
        return rel.as_posix()
    except ValueError:
        img_dir = resolve_image_dir(project, settings)
        try:
            rel = resolved.relative_to(img_dir)
            cfg = settings if settings is not None else load_image_settings(project)
            base = str(cfg.get("image_dir") or DEFAULT_IMAGE_REL).strip().replace("\\", "/")
            return f"{base}/{rel.as_posix()}"
        except ValueError:
            return resolved.name


def list_images(project_dir: Path, settings: dict[str, Any] | None = None) -> list[Path]:
    img_dir = resolve_image_dir(project_dir, settings)
    if not img_dir.is_dir():
        return []
    files: list[Path] = []
    for path in img_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTS and is_valid_image_file(path):
            files.append(path)
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def is_valid_image_file(path: Path) -> bool:
    """校验图片能否被 OpenCV 解码（跳过损坏的 png 占位文件）。"""
    try:
        if not path.is_file() or path.stat().st_size < 32:
            return False
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return False
        return cv2.imdecode(data, cv2.IMREAD_COLOR) is not None
    except OSError:
        return False


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^\w\-.]+", "_", name.strip())
    return stem or "image"


def next_capture_filename(prefix: str = "screen") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{_safe_stem(prefix)}_{ts}.png"


def save_bgr_image(project_dir: Path, bgr: np.ndarray, filename: str) -> Path:
    settings = load_image_settings(project_dir)
    img_dir = resolve_image_dir(project_dir, settings)
    img_dir.mkdir(parents=True, exist_ok=True)
    name = filename if filename.lower().endswith(".png") else f"{filename}.png"
    out = img_dir / name
    if not cv2.imwrite(str(out), bgr):
        raise RuntimeError(f"保存图片失败: {out}")
    return out


def unique_dest_path(img_dir: Path, filename: str) -> Path:
    """目标目录内不重名的保存路径。"""
    safe = Path(filename).name
    dest = img_dir / safe
    if not dest.exists():
        return dest
    stem = Path(safe).stem
    ext = Path(safe).suffix or ".png"
    for i in range(1, 9999):
        candidate = img_dir / f"{stem}_{i}{ext}"
        if not candidate.exists():
            return candidate
    raise ValueError(f"无法生成不重名文件: {filename}")


def import_images(project_dir: Path, sources: list[Path | str]) -> list[Path]:
    """将外部图片复制到工程附件目录。"""
    settings = load_image_settings(project_dir)
    img_dir = resolve_image_dir(project_dir, settings)
    img_dir.mkdir(parents=True, exist_ok=True)
    imported: list[Path] = []
    for raw in sources:
        src = Path(raw)
        if not src.is_file():
            continue
        if src.suffix.lower() not in _IMAGE_EXTS:
            continue
        if not is_valid_image_file(src):
            continue
        dest = unique_dest_path(img_dir, src.name)
        shutil.copy2(src, dest)
        imported.append(dest)
    return imported


def delete_image_file(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink()
            return True
    except OSError:
        return False
    return False


def delete_images(paths: list[Path]) -> int:
    return sum(1 for p in paths if delete_image_file(p))


def delete_all_images(project_dir: Path) -> int:
    paths = list_images(project_dir)
    return delete_images(paths)


def export_images(sources: list[Path], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    for src in sources:
        if not src.is_file():
            continue
        out = unique_dest_path(dest_dir, src.name)
        shutil.copy2(src, out)
        exported.append(out)
    return exported
