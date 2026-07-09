"""打包前工程预检。"""

from __future__ import annotations

from pathlib import Path

from packager.pack_metadata import read_project_cfg
from studio.services.layout_defaults import load_layout
from studio.services.layout_validate import validate_layout


def validate_before_pack(project_dir: Path) -> tuple[list[str], list[str]]:
    """返回 (errors, warnings)。"""
    project_dir = project_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        cfg = read_project_cfg(project_dir)
    except FileNotFoundError:
        return (["缺少 project.json"], [])
    except Exception as exc:
        return ([f"project.json 无效: {exc}"], [])

    name = str(cfg.get("name") or "").strip()
    pkg = str(cfg.get("package_id") or "").strip()
    if not name:
        errors.append("未填写软件名称")
    if not pkg:
        errors.append("未填写包名 package_id")

    jiaoben = cfg.get("jiaoben") or {}
    if not int(jiaoben.get("project_id") or 0):
        warnings.append("未配置 jiaoben.project_id（仅热更新发版需要，本地打包可忽略）")

    runtime = cfg.get("runtime") or {}
    model = str(runtime.get("default_yolo_model") or "").strip()
    yolo_imgsz = int((runtime.get("perf") or {}).get("yolo_imgsz") or 320)
    models_dir = project_dir / "models"
    if models_dir.is_dir():
        pt_files = list(models_dir.glob("*.pt"))
        onnx_files = list(models_dir.glob("*.onnx"))
        for pt in pt_files:
            if not pt.with_suffix(".onnx").is_file() and not (models_dir / f"{pt.stem}.onnx").is_file():
                errors.append(
                    f"models/{pt.name} 无对应 ONNX，APK 无法加载。"
                    " 请 Studio「从 adb-ide 导入」或 export_yolo_onnx.py"
                )
        if pt_files and not onnx_files and not errors:
            warnings.append("models/ 仅有 .pt，打包后 YOLO 不可用，请导出 ONNX")
        if onnx_files and not model:
            warnings.append("models/ 下有 ONNX 但未设置 runtime.default_yolo_model")
        if model and not (project_dir / model).is_file() and not (models_dir / Path(model).name).is_file():
            errors.append(f"YOLO 模型不存在: {model}")
        try:
            from studio.services.onnx_inspect import inspect_onnx, validate_onnx_for_pack

            for onnx in onnx_files:
                o_err, o_warn = validate_onnx_for_pack(onnx, yolo_imgsz=yolo_imgsz)
                errors.extend(o_err)
                warnings.extend(o_warn)
                info = inspect_onnx(onnx)
                if info.get("task") == "segment":
                    warnings.append(f"检测到 seg 模型: {onnx.name}")
        except ImportError:
            pass
    elif model:
        errors.append(f"YOLO 模型路径无效: {model}")

    entry = str(cfg.get("entry") or "main.lua")
    if not (project_dir / entry).is_file():
        errors.append(f"入口脚本不存在: {entry}")

    layout_path = project_dir / "ui" / "layout.json"
    if layout_path.is_file():
        try:
            layout = load_layout(project_dir)
            for msg in validate_layout(layout):
                errors.append(f"layout: {msg}")
        except Exception as exc:
            errors.append(f"ui/layout.json 无效: {exc}")

    return (errors, warnings)
