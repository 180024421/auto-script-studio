"""打包前工程预检。"""

from __future__ import annotations

from pathlib import Path

from packager.pack_metadata import read_project_cfg


def validate_before_pack(project_dir: Path) -> list[str]:
    """返回警告/错误列表，空表示通过。"""
    project_dir = project_dir.resolve()
    issues: list[str] = []
    try:
        cfg = read_project_cfg(project_dir)
    except FileNotFoundError:
        return ["缺少 project.json"]
    except Exception as exc:
        return [f"project.json 无效: {exc}"]

    name = str(cfg.get("name") or "").strip()
    pkg = str(cfg.get("package_id") or "").strip()
    if not name:
        issues.append("未填写软件名称")
    if not pkg:
        issues.append("未填写包名 package_id")

    jiaoben = cfg.get("jiaoben") or {}
    if not int(jiaoben.get("project_id") or 0):
        issues.append("未配置 jiaoben.project_id（热更新发版归属）")

    runtime = cfg.get("runtime") or {}
    model = str(runtime.get("default_yolo_model") or "").strip()
    models_dir = project_dir / "models"
    if models_dir.is_dir():
        onnx_files = list(models_dir.glob("*.onnx"))
        if onnx_files and not model:
            issues.append("models/ 下有 ONNX 但未设置 runtime.default_yolo_model")
        if model and not (project_dir / model).is_file() and not (models_dir / Path(model).name).is_file():
            issues.append(f"YOLO 模型不存在: {model}")
    elif model:
        issues.append(f"YOLO 模型路径无效: {model}")

    entry = str(cfg.get("entry") or "main.lua")
    if not (project_dir / entry).is_file():
        issues.append(f"入口脚本不存在: {entry}")

    return issues
