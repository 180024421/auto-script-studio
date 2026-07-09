"""ONNX 模型检查（detect / seg、输出数、体积）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_onnx(path: Path) -> dict[str, Any]:
    """检查 YOLO ONNX 模型元信息。无 onnx 库时仅返回文件大小。"""
    path = path.resolve()
    info: dict[str, Any] = {
        "path": str(path),
        "size_mb": round(path.stat().st_size / (1024 * 1024), 2) if path.is_file() else 0,
        "outputs": 0,
        "task": "unknown",
        "input_shape": None,
        "output_shapes": [],
        "ok": path.is_file(),
    }
    if not path.is_file():
        return info
    try:
        import onnx  # type: ignore

        model = onnx.load(str(path))
        outs = list(model.graph.output)
        info["outputs"] = len(outs)
        info["output_shapes"] = [_tensor_shape(o) for o in outs]
        if model.graph.input:
            info["input_shape"] = _tensor_shape(model.graph.input[0])
        if len(outs) >= 2:
            info["task"] = "segment"
        elif len(outs) == 1:
            info["task"] = "detect"
    except ImportError:
        info["task"] = "unknown (pip install onnx 可检测类型)"
    except Exception as exc:
        info["error"] = str(exc)
    return info


def _tensor_shape(tensor: Any) -> list[int | str]:
    shape: list[int | str] = []
    for d in tensor.type.tensor_type.shape.dim:
        if d.dim_value:
            shape.append(int(d.dim_value))
        elif d.dim_param:
            shape.append(str(d.dim_param))
        else:
            shape.append("?")
    return shape


def validate_onnx_for_pack(path: Path, yolo_imgsz: int = 320) -> tuple[list[str], list[str]]:
    """打包预检：返回 (errors, warnings)。"""
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        errors.append(f"ONNX 不存在: {path}")
        return errors, warnings
    info = inspect_onnx(path)
    size_mb = float(info.get("size_mb") or 0)
    if size_mb > 80:
        warnings.append(f"YOLO 模型较大 ({size_mb}MB)，低端机可能 OOM: {path.name}")
    task = str(info.get("task") or "")
    if task == "segment":
        warnings.append(f"seg 模型 {path.name}：脚本可用 use_mask_center 或 runtime.yolo_auto_mask_center")
    outputs = int(info.get("outputs") or 0)
    if outputs == 0 and "error" not in info:
        warnings.append(f"无法读取 ONNX 输出数: {path.name}（请 pip install onnx）")
    inp = info.get("input_shape")
    if isinstance(inp, list) and len(inp) >= 4:
        h = inp[2] if isinstance(inp[2], int) else None
        w = inp[3] if isinstance(inp[3], int) else None
        if h and w and h != yolo_imgsz and w != yolo_imgsz:
            warnings.append(
                f"{path.name} 输入 {h}x{w} 与 runtime.perf.yolo_imgsz={yolo_imgsz} 不一致，请重新导出或改配置"
            )
    return errors, warnings
