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
from packager.validate_project import validate_project_full


def validate_project(project_dir: Path) -> dict:
    result = validate_project_full(project_dir)
    for w in result.get("warnings", []):
        print(f"警告: {w}")
    return result["cfg"]


def sync_assets(project_dir: Path) -> None:
    staging, cfg = prepare_staging_dir(project_dir)
    try:
        from packager.icon_processor import prepare_pack_icons

        icon_src = prepare_pack_icons(project_dir, cfg, RUNTIME, staging)
        print(f"图标: {icon_src.name} → mipmap + ui/ball.png")
        if ASSETS.exists():
            shutil.rmtree(ASSETS)
        shutil.copytree(staging, ASSETS)
    finally:
        cleanup_staging(staging)


def write_gradle_props(cfg: dict, signing: dict | None = None) -> None:
    lines = [
        f"applicationId={cfg['package_id']}",
        f"versionCode={cfg.get('version_code', 1)}",
        f"versionName={cfg.get('version_name', '1.0.0')}",
        f"appName={cfg.get('name', 'Auto Script')}",
    ]
    if signing:
        ks = signing.get("keystore")
        if ks:
            lines.append(f"signingStoreFile={Path(ks).resolve()}")
            lines.append(f"signingStorePassword={signing.get('ks_pass', '')}")
            lines.append(f"signingKeyAlias={signing.get('key_alias', '')}")
            lines.append(f"signingKeyPassword={signing.get('key_pass', signing.get('ks_pass', ''))}")
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


def build(
    project_dir: Path,
    output: Path,
    release: bool = False,
    signing: dict | None = None,
) -> Path:
    cfg = validate_project(project_dir)
    sync_assets(project_dir)
    write_gradle_props(cfg, signing if release else None)
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
    p_build.add_argument("--keystore", type=Path, help="Release 签名 keystore 路径")
    p_build.add_argument("--ks-pass", type=str, default="", help="keystore 密码")
    p_build.add_argument("--key-alias", type=str, default="", help="密钥别名")
    p_build.add_argument("--key-pass", type=str, default="", help="密钥密码（默认同 ks-pass）")

    p_validate = sub.add_parser("validate", help="校验工程")
    p_validate.add_argument("project", type=Path)

    args = parser.parse_args(argv)
    if args.cmd == "validate":
        cfg = validate_project(args.project)
        print("OK:", cfg.get("name"), cfg.get("package_id"))
        return 0
    if args.cmd == "build":
        signing = None
        if args.release and args.keystore:
            signing = {
                "keystore": args.keystore,
                "ks_pass": args.ks_pass,
                "key_alias": args.key_alias,
                "key_pass": args.key_pass or args.ks_pass,
            }
        build(args.project, args.output, release=args.release, signing=signing)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
