"""工程内 YOLO 模型与类别名解析。"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

YOLO_EXTS = (".onnx", ".pt")


def models_dir(project_dir: Path) -> Path:
    return project_dir / "models"


def normalize_detection(det: dict) -> dict[str, int | float | str]:
    """统一 bot.yoloDetect 返回结构（PC / 文档 / Lua 片段一致）。"""
    x = int(det.get("x", 0))
    y = int(det.get("y", 0))
    w = int(det.get("w", 0))
    h = int(det.get("h", 0))
    cx = int(det.get("center_x", x + w // 2))
    cy = int(det.get("center_y", y + h // 2))
    return {
        "class_name": str(det.get("class_name") or ""),
        "confidence": float(det.get("confidence", 0.0)),
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "center_x": cx,
        "center_y": cy,
    }


def normalize_detections(dets: Iterable[dict]) -> list[dict[str, int | float | str]]:
    return [normalize_detection(d) for d in dets]

def list_yolo_models(project_dir: Path) -> list[Path]:
    """列出工程 models/ 下可用 .onnx / .pt（优先 onnx）。"""
    root = project_dir / "models"
    if not root.is_dir():
        return []
    onnx = sorted(root.rglob("*.onnx"))
    pt = sorted(root.rglob("*.pt"))
    seen: set[Path] = set()
    out: list[Path] = []
    for path in onnx + pt:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def model_rel_path(project_dir: Path, model_path: Path) -> str:
    try:
        return model_path.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return model_path.name


def labels_path_for(model_path: Path) -> Path:
    return model_path.with_suffix(".labels")


def load_class_names(model_path: Path) -> list[str]:
    """从 .labels 或 Ultralytics .pt 元数据读取类别名。"""
    labels = labels_path_for(model_path)
    if labels.is_file():
        return [ln.strip() for ln in labels.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if model_path.suffix.lower() != ".pt":
        return []
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        log.debug("ultralytics 未安装，无法从 .pt 读取类别")
        return []
    try:
        names = YOLO(str(model_path)).names or {}
        return [str(names[i]) for i in sorted(names.keys())]
    except Exception as exc:
        log.warning("读取 YOLO 类别失败 %s: %s", model_path, exc)
        return []


def merge_class_names_from_detections(
    known: Iterable[str],
    detections: Iterable[dict],
) -> list[str]:
    """检测到的类名合并进下拉列表（去重保序）。"""
    out: list[str] = []
    seen: set[str] = set()
    for name in known:
        n = str(name).strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    for det in detections:
        n = str(det.get("class_name") or "").strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def default_model_path(project_dir: Path) -> Path | None:
    models = list_yolo_models(project_dir)
    if not models:
        return None
    cfg = project_dir / "project.json"
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            rel = str((data.get("runtime") or {}).get("default_yolo_model") or "").strip()
            if rel:
                candidate = project_dir / rel
                if candidate.is_file():
                    return candidate
                for p in models:
                    if model_rel_path(project_dir, p) == rel or p.stem == Path(rel).stem:
                        return p
        except Exception:
            pass
    onnx_first = [p for p in models if p.suffix.lower() == ".onnx"]
    return onnx_first[0] if onnx_first else models[0]


def read_default_model_rel(project_dir: Path) -> str:
    cfg = project_dir / "project.json"
    if not cfg.is_file():
        return ""
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        return str((data.get("runtime") or {}).get("default_yolo_model") or "").strip()
    except Exception:
        return ""


def set_default_model(project_dir: Path, rel: str) -> None:
    cfg = project_dir / "project.json"
    data: dict = {}
    if cfg.is_file():
        data = json.loads(cfg.read_text(encoding="utf-8"))
    runtime = dict(data.get("runtime") or {})
    runtime["default_yolo_model"] = rel.strip()
    data["runtime"] = runtime
    cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def import_models(project_dir: Path, sources: list[Path]) -> list[Path]:
    """复制 .onnx / .pt 及同 stem 的 .labels 到工程 models/。"""
    dest_root = models_dir(project_dir)
    dest_root.mkdir(parents=True, exist_ok=True)
    imported: list[Path] = []
    for src in sources:
        src = Path(src)
        if not src.is_file() or src.suffix.lower() not in YOLO_EXTS:
            continue
        out = dest_root / src.name
        shutil.copy2(src, out)
        imported.append(out)
        labels = src.with_suffix(".labels")
        if labels.is_file():
            shutil.copy2(labels, out.with_suffix(".labels"))
    return imported


def delete_models(paths: list[Path]) -> int:
    count = 0
    for path in paths:
        p = Path(path)
        if p.is_file():
            p.unlink(missing_ok=True)
            count += 1
        labels = labels_path_for(p)
        if labels.is_file():
            labels.unlink(missing_ok=True)
    return count


def export_models(paths: list[Path], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    exported: list[Path] = []
    for path in paths:
        p = Path(path)
        if not p.is_file():
            continue
        out = dest_dir / p.name
        shutil.copy2(p, out)
        exported.append(out)
        labels = labels_path_for(p)
        if labels.is_file():
            shutil.copy2(labels, dest_dir / labels.name)
    return exported


def save_labels(model_path: Path, class_names: list[str]) -> Path:
    labels = labels_path_for(model_path)
    text = "\n".join(n.strip() for n in class_names if n.strip()) + "\n"
    labels.write_text(text, encoding="utf-8")
    return labels
