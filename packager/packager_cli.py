"""将脚本工程打包为 Android APK。"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "android-runtime"
ASSETS = RUNTIME / "app" / "src" / "main" / "assets" / "project"
PROPS = RUNTIME / "packager" / "project.properties"
GRADLEW = RUNTIME / "gradlew.bat"


from packager.compile_project import cleanup_staging, prepare_staging_dir, resolve_runtime_entry


def validate_project(project_dir: Path) -> dict:
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
    return cfg


def sync_assets(project_dir: Path) -> None:
    staging, _ = prepare_staging_dir(project_dir)
    try:
        if ASSETS.exists():
            shutil.rmtree(ASSETS)
        shutil.copytree(staging, ASSETS)
    finally:
        cleanup_staging(staging)


def write_gradle_props(cfg: dict) -> None:
    lines = [
        f"applicationId={cfg['package_id']}",
        f"versionCode={cfg.get('version_code', 1)}",
        f"versionName={cfg.get('version_name', '1.0.0')}",
        f"appName={cfg.get('name', 'Auto Script')}",
    ]
    PROPS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_gradle(release: bool) -> Path:
    if not GRADLEW.is_file():
        raise FileNotFoundError(
            f"未找到 gradlew.bat，请在 {RUNTIME} 执行 gradle wrapper 或安装 Android Studio"
        )
    task = "assembleRelease" if release else "assembleDebug"
    cmd = [str(GRADLEW), f":app:{task}", "--no-daemon"]
    print("执行:", " ".join(cmd))
    subprocess.run(cmd, cwd=RUNTIME, check=True)
    variant = "release" if release else "debug"
    apk = RUNTIME / "app" / "build" / "outputs" / "apk" / variant / f"app-{variant}.apk"
    if not apk.is_file():
        raise FileNotFoundError(f"Gradle 完成但未找到 APK: {apk}")
    return apk


def build(project_dir: Path, output: Path, release: bool = False) -> Path:
    cfg = validate_project(project_dir)
    sync_assets(project_dir)
    write_gradle_props(cfg)
    apk = run_gradle(release)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(apk, output)
    print(f"已输出: {output} ({output.stat().st_size // 1024} KB)")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auto Script Studio 打包器")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="打包脚本工程为 APK")
    p_build.add_argument("project", type=Path, help="脚本工程目录")
    p_build.add_argument("-o", "--output", type=Path, required=True, help="输出 APK 路径")
    p_build.add_argument("--release", action="store_true", help="Release 构建")

    p_validate = sub.add_parser("validate", help="校验工程")
    p_validate.add_argument("project", type=Path)

    args = parser.parse_args(argv)
    if args.cmd == "validate":
        cfg = validate_project(args.project)
        print("OK:", cfg.get("name"), cfg.get("package_id"))
        return 0
    if args.cmd == "build":
        build(args.project, args.output, release=args.release)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
