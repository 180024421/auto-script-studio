"""adb-ide 训练权重 → auto-script-studio ONNX 导入。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def resolve_best_pt(pt_or_run: Path) -> Path:
    """解析 adb-ide / Ultralytics 训练产物为 best.pt。"""
    p = Path(pt_or_run).expanduser().resolve()
    if p.is_file():
        if p.suffix.lower() != ".pt":
            raise ValueError(f"不是 .pt 权重: {p}")
        return p
    if not p.is_dir():
        raise FileNotFoundError(p)
    direct = p / "weights" / "best.pt"
    if direct.is_file():
        return direct
    for cand in sorted(p.rglob("weights/best.pt")):
        return cand
    raise FileNotFoundError(f"未找到 weights/best.pt: {p}")


def read_names_from_data_yaml(run_dir: Path) -> list[str]:
    """从训练 run 旁 data.yaml 读取 names（可选）。"""
    run_dir = Path(run_dir).resolve()
    candidates = [run_dir / "data.yaml", run_dir.parent / "data.yaml"]
    for parent in run_dir.parents:
        candidates.append(parent / "data.yaml")
        if len(candidates) > 8:
            break
    for yaml_path in candidates:
        if not yaml_path.is_file():
            continue
        try:
            import yaml  # type: ignore
        except ImportError:
            log.debug("未安装 pyyaml，跳过 data.yaml 读取")
            return []
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("读取 data.yaml 失败 %s: %s", yaml_path, exc)
            continue
        names = data.get("names") if isinstance(data, dict) else None
        if isinstance(names, dict):
            return [str(names[k]) for k in sorted(names.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x))]
        if isinstance(names, list):
            return [str(n) for n in names]
    return []


def export_pt_to_onnx(pt: Path, out_prefix: Path, imgsz: int, *, dynamic: bool = False) -> tuple[Path, str, list[str]]:
    """导出 ONNX + labels，返回 (onnx_path, task, class_names)。"""
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("请先安装 ultralytics: pip install ultralytics") from exc

    pt = pt.resolve()
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(pt))
    task = str(getattr(model, "task", "") or "detect")
    export_kw: dict[str, Any] = {
        "format": "onnx",
        "imgsz": imgsz,
        "simplify": True,
        "opset": 12,
        "dynamic": dynamic,
    }
    onnx_path = Path(model.export(**export_kw))
    onnx_dst = out_prefix.with_suffix(".onnx")
    if onnx_dst.resolve() != onnx_path.resolve():
        onnx_dst.write_bytes(onnx_path.read_bytes())

    names = model.names or {}
    class_names = [str(names[i]) for i in sorted(names.keys())]
    labels_dst = out_prefix.with_suffix(".labels")
    labels_dst.write_text("\n".join(class_names) + "\n", encoding="utf-8")
    return onnx_dst, task, class_names


def import_adb_ide_yolo(
    project_dir: Path,
    pt_or_run: Path,
    *,
    out_name: str | None = None,
    imgsz: int = 320,
    set_default: bool = True,
    apply_preset: str | None = "yolo_seg_fast",
) -> dict[str, Any]:
    """导入 adb-ide 权重到工程 models/，并可选应用 seg 极速预设。"""
    project_dir = Path(project_dir).resolve()
    best_pt = resolve_best_pt(pt_or_run)
    run_dir = best_pt.parent.parent if best_pt.parent.name == "weights" else best_pt.parent
    stem = (out_name or run_dir.name or best_pt.stem).strip()
    if not stem:
        stem = "yolo"
    out_prefix = project_dir / "models" / stem

    yaml_names = read_names_from_data_yaml(run_dir)
    onnx_path, task, pt_names = export_pt_to_onnx(best_pt, out_prefix, imgsz)
    class_names = yaml_names or pt_names
    if class_names:
        out_prefix.with_suffix(".labels").write_text("\n".join(class_names) + "\n", encoding="utf-8")

    rel = f"models/{onnx_path.name}"
    cfg_path = project_dir / "project.json"

    if apply_preset:
        from studio.services.runtime_presets import apply_preset as _apply

        _apply(project_dir, apply_preset)

    if set_default or task == "segment":
        data: dict = {}
        if cfg_path.is_file():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        runtime = dict(data.get("runtime") or {})
        if set_default:
            runtime["default_yolo_model"] = rel
        if task == "segment":
            runtime["yolo_auto_mask_center"] = True
        data["runtime"] = runtime
        cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "onnx": str(onnx_path),
        "labels": str(out_prefix.with_suffix(".labels")),
        "task": task,
        "class_count": len(class_names),
        "imgsz": imgsz,
        "default_model": rel if set_default else None,
        "preset": apply_preset,
        "source_pt": str(best_pt),
        "hint": (
            f"adb-ide 训练 imgsz 常为 640；已按 {imgsz} 导出供移动端几十 ms 推理。"
            " 若精度不足可试 --imgsz 416。"
        ),
    }
