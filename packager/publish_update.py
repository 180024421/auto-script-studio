"""发布脚本热更新包（zip + manifest.json），供 SCC 或静态服务器托管。"""

from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path

from packager.compile_project import cleanup_staging, prepare_staging_dir
from packager.pack_metadata import read_project_cfg


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def build_update_zip(project_dir: Path, out_dir: Path, *, bump_version: int | None = None) -> tuple[Path, Path, dict]:
    """
    打包工程为热更新 zip，并生成 manifest.json。

    返回 (zip_path, manifest_path, manifest_dict)
    """
    project_dir = project_dir.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    staging, apk_cfg = prepare_staging_dir(project_dir)
    try:
        cfg = read_project_cfg(project_dir)
        version_code = bump_version or int(cfg.get("version_code", 1)) + 1
        version_name = str(cfg.get("version_name", "1.0.0"))
        package_id = str(cfg.get("package_id", "com.autoscript.demo"))

        zip_name = f"{package_id.replace('.', '_')}_v{version_code}.zip"
        zip_path = out_dir / zip_name
        if zip_path.is_file():
            zip_path.unlink()

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in staging.rglob("*"):
                if fp.is_file():
                    zf.write(fp, fp.relative_to(staging).as_posix())

        sha = _sha256_file(zip_path)
        manifest = {
            "package_id": package_id,
            "version_code": version_code,
            "version_name": version_name,
            "zip_url": zip_name,
            "sha256": sha,
            "file_size": zip_path.stat().st_size,
            "published_at": datetime.now().isoformat(timespec="seconds"),
            "changelog": "",
        }
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return zip_path, manifest_path, manifest
    finally:
        cleanup_staging(staging)


def _unwrap_publish_manifest(data: dict) -> dict:
    """兼容 GlobalResponseWrapper 与 @RawResponse 两种响应。"""
    if isinstance(data.get("manifest"), dict):
        return data["manifest"]
    inner = data.get("data")
    if isinstance(inner, dict):
        if isinstance(inner.get("manifest"), dict):
            return inner["manifest"]
        if "version_code" in inner:
            return inner
    if "version_code" in data:
        return data
    return data


def publish_to_jiaoben(
    project_dir: Path,
    api_base: str,
    *,
    bump_version: int | None = None,
    changelog: str = "",
    min_apk_version: int = 1,
    publish_token: str = "",
    project_id: int | None = None,
) -> dict:
    """上传 zip 到 run-jane-script jiaoben 并发版。"""
    import urllib.request
    import urllib.error

    out_dir = project_dir / ".publish-staging"
    zip_path, _manifest_path, manifest = build_update_zip(project_dir, out_dir, bump_version=bump_version)
    cfg = read_project_cfg(project_dir)
    jiaoben_cfg = cfg.get("jiaoben") or {}
    resolved_project_id = project_id
    if resolved_project_id is None:
        resolved_project_id = int(jiaoben_cfg.get("project_id") or 0) or None
    base = api_base.strip().rstrip("/")
    if base.endswith("/api"):
        url = f"{base}/script/update/publish"
    else:
        url = f"{base}/api/script/update/publish"
    boundary = "----AutoScriptPublish"
    body = bytearray()
    fields = {
        "app": manifest["package_id"],
        "version_code": str(manifest["version_code"]),
        "version_name": manifest.get("version_name", ""),
        "min_apk_version": str(min_apk_version),
        "changelog": changelog,
    }
    if resolved_project_id:
        fields["project_id"] = str(resolved_project_id)
    for key, val in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        body.extend(f"{val}\r\n".encode())
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{zip_path.name}"\r\n'.encode()
    )
    body.extend(b"Content-Type: application/zip\r\n\r\n")
    body.extend(zip_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    req = urllib.request.Request(url, data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if publish_token:
        req.add_header("X-Script-Update-Token", publish_token)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"发版失败 HTTP {exc.code}: {detail}") from exc
    return _unwrap_publish_manifest(data)


def write_back_version(
    project_dir: Path,
    version_code: int,
    *,
    version_name: str | None = None,
) -> dict:
    """热更新发版成功后写回 project.json 版本号。"""
    project_dir = project_dir.resolve()
    path = project_dir / "project.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["version_code"] = int(version_code)
    if version_name is not None and str(version_name).strip():
        cfg["version_name"] = str(version_name).strip()
    elif int(cfg.get("version_code", 1)) != int(version_code):
        cfg["version_name"] = f"1.0.{max(0, int(version_code) - 1)}"
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cfg


def publish_for_scc(project_dir: Path, scc_packages_dir: Path, package_key: str, *, note: str = "") -> dict:
    """
    发布到 SCC packages/<package_key>/apk_updates/ 并返回 manifest（zip_url 为 SCC API 路径）。
    """
    scc_packages_dir = scc_packages_dir.resolve()
    update_dir = scc_packages_dir / package_key / "apk_updates"
    zip_path, manifest_path, manifest = build_update_zip(project_dir, update_dir)
    manifest["zip_url"] = f"/api/apk-projects/{package_key}/update.zip"
    manifest["manifest_url"] = f"/api/apk-projects/{package_key}/manifest.json"
    manifest["note"] = note
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    project_json = read_project_cfg(project_dir)
    project_json.setdefault("update", {})
    project_json["update"]["enabled"] = True
    project_json["update"]["manifest_url"] = manifest["manifest_url"]
    hint_path = project_dir / "project.json.scc-update-hint.json"
    hint_path.write_text(json.dumps(project_json["update"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
