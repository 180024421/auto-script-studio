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


from packager.compile_project import cleanup_staging, prepare_staging_dir
from packager.pack_metadata import read_project_cfg, write_gradle_props
from packager.validate_project import validate_project_full


def validate_project(project_dir: Path) -> dict:
    result = validate_project_full(project_dir)
    for w in result.get("warnings", []):
        print(f"警告: {w}")
    return result["cfg"]


def _normalize_pack_layout(staging: Path) -> None:
    """打包前规范化 layout：host/form 去掉 chrome 与界面内动作按钮。"""
    layout_path = staging / "ui" / "layout.json"
    if not layout_path.is_file():
        return
    data = json.loads(layout_path.read_text(encoding="utf-8"))
    from studio.services.screen_layout import (
        ensure_migrated,
        is_host_display,
        normalize_chrome_widgets,
        strip_action_widgets_from_screens,
    )

    ensure_migrated(data)
    panel = data.get("panel") or {}
    data["widgets"] = normalize_chrome_widgets(data.get("widgets") or [], panel)
    if is_host_display(panel):
        strip_action_widgets_from_screens(data)
    layout_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sync_assets(project_dir: Path) -> None:
    staging, _cfg = prepare_staging_dir(project_dir)
    cfg = read_project_cfg(project_dir)
    try:
        from packager.icon_processor import prepare_pack_icons

        icon_src = prepare_pack_icons(project_dir, cfg, RUNTIME, staging)
        print(f"图标: {icon_src} → mipmap + ui/ball.png")
        if ASSETS.exists():
            shutil.rmtree(ASSETS)
        _normalize_pack_layout(staging)
        shutil.copytree(staging, ASSETS)
    finally:
        cleanup_staging(staging)


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
    validate_project(project_dir)
    sync_assets(project_dir)
    cfg = read_project_cfg(project_dir)
    write_gradle_props(cfg, PROPS, signing if release else None)
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

    p_publish = sub.add_parser("publish-update", help="发布脚本热更新 zip + manifest.json")
    p_publish.add_argument("project", type=Path, help="脚本工程目录")
    p_publish.add_argument("-o", "--output", type=Path, required=True, help="输出目录")
    p_publish.add_argument("--bump", type=int, default=None, help="指定 version_code（默认 project+1）")
    p_publish.add_argument(
        "--scc-packages",
        type=Path,
        help="发布到 SCC packages/<id>/apk_updates/，值为 SCC packages 根目录",
    )
    p_publish.add_argument("--scc-id", type=str, default="", help="SCC 包 ID（默认用 package_id）")
    p_publish.add_argument(
        "--jiaoben",
        type=str,
        default="",
        help="发布到 run-jane-script jiaoben（填 api_base，如 http://111.229.202.251:8687）",
    )
    p_publish.add_argument("--changelog", type=str, default="", help="更新说明")
    p_publish.add_argument("--publish-token", type=str, default="", help="X-Script-Update-Token")
    p_publish.add_argument("--project-id", type=int, default=None, help="发卡项目 ID（默认读 project.json jiaoben.project_id）")

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
    if args.cmd == "publish-update":
        from packager.publish_update import build_update_zip, publish_for_scc, publish_to_jiaoben

        if args.jiaoben:
            cfg = read_project_cfg(args.project)
            api_base = args.jiaoben or str((cfg.get("license") or {}).get("api_base", ""))
            manifest = publish_to_jiaoben(
                args.project,
                api_base,
                bump_version=args.bump,
                changelog=args.changelog,
                publish_token=args.publish_token,
                project_id=args.project_id,
            )
            print("jiaoben 热更新已发布:", json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.scc_packages:
            cfg = read_project_cfg(args.project)
            key = args.scc_id or str(cfg.get("package_id", "demo"))
            manifest = publish_for_scc(args.project, args.scc_packages, key)
            print("SCC 热更新已发布:", json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        zip_path, manifest_path, manifest = build_update_zip(
            args.project, args.output, bump_version=args.bump
        )
        print(f"zip: {zip_path}")
        print(f"manifest: {manifest_path}")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
