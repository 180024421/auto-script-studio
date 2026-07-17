"""将本地脚本工程推送到已安装 APK 的 files/project_overlay（调试热替换）。"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


_SKIP_NAMES = {".git", ".publish-staging", "__pycache__", ".idea", "node_modules"}


def _adb(adb_path: str, serial: str | None, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [adb_path]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=check,
    )


def _package_id(project_dir: Path) -> str:
    cfg = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    pkg = str(cfg.get("package_id") or "").strip()
    if not pkg:
        raise ValueError("project.json 缺少 package_id")
    return pkg


def _copy_project_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    def ignore(directory: str, names: list[str]) -> set[str]:
        return {n for n in names if n in _SKIP_NAMES or n.endswith(".pyc")}

    for item in src.iterdir():
        if item.name in _SKIP_NAMES:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=ignore)
        else:
            shutil.copy2(item, target)


def push_project_overlay(
    project_dir: Path,
    *,
    adb_path: str = "adb",
    serial: str | None = None,
    package_id: str | None = None,
) -> str:
    """
    推送工程到设备端 ``files/project_overlay``。

    需要：已安装对应包名的 **debug** APK（``run-as`` 可用），否则会失败并提示改用完整打包。
    推送后请在手机端重新打开悬浮窗 / 重启脚本以加载新资源。
    """
    project_dir = project_dir.resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"不是有效工程目录: {project_dir}")
    pkg = package_id or _package_id(project_dir)

    # 探测 run-as
    probe = _adb(adb_path, serial, "shell", "run-as", pkg, "ls", "files", check=False)
    if probe.returncode != 0:
        detail = (probe.stderr or probe.stdout or "").strip()
        raise RuntimeError(
            f"无法 run-as {pkg}（通常需要 debug 安装包）。\n"
            f"{detail}\n"
            "请先「打包并安装」debug APK，或改用完整打包。"
        )

    with tempfile.TemporaryDirectory(prefix="ass_overlay_") as tmp:
        staging = Path(tmp) / "project_overlay"
        _copy_project_tree(project_dir, staging)
        remote_sd = f"/sdcard/Download/ass_overlay_{pkg.replace('.', '_')}"
        _adb(adb_path, serial, "shell", "rm", "-rf", remote_sd, check=False)
        _adb(adb_path, serial, "push", str(staging), remote_sd)

        script = (
            f"rm -rf files/project_overlay && "
            f"mkdir -p files && "
            f"cp -r {remote_sd} files/project_overlay && "
            f"rm -rf {remote_sd}"
        )
        apply = _adb(adb_path, serial, "shell", "run-as", pkg, "sh", "-c", script, check=False)
        if apply.returncode != 0:
            raise RuntimeError(
                f"写入 project_overlay 失败:\n{(apply.stderr or apply.stdout or '').strip()}"
            )

    return (
        f"已推送到 {pkg}/files/project_overlay。\n"
        "请在手机端关闭并重新打开悬浮窗，或重启脚本以加载新 Lua/layout/图片。"
    )
