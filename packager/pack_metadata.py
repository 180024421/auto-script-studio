"""应用名 / 包名 / 图标 — 读写 project.json 与 Gradle 属性。"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

_PKG_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def escape_gradle_property(value: str) -> str:
    """Java Properties 加载非 ASCII 须 \\uXXXX 转义。"""
    out: list[str] = []
    for ch in value:
        if ord(ch) > 127 or ch in ("\\", "\n", "\r", "\t"):
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def read_project_cfg(project_dir: Path) -> dict:
    path = project_dir / "project.json"
    if not path.is_file():
        raise FileNotFoundError(f"缺少 project.json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_icon_file(project_dir: Path, icon_text: str) -> Path | None:
    text = (icon_text or "").strip()
    if not text:
        return None
    for candidate in (Path(text), project_dir / text):
        if candidate.is_file():
            return candidate.resolve()
    return None


def validate_pack_fields(name: str, package_id: str, project_dir: Path, icon_text: str = "") -> str | None:
    if not name.strip():
        return "请填写软件名称"
    if not _PKG_RE.match(package_id.strip()):
        return (
            "包名格式不正确，示例：com.example.myscript\n"
            "须为小写字母、数字、下划线，并以点分段。"
        )
    icon_path = resolve_icon_file(project_dir, icon_text)
    if icon_text.strip() and icon_path is None:
        return f"图标文件不存在：{icon_text.strip()}"
    return None


def save_pack_metadata(
    project_dir: Path,
    *,
    name: str,
    package_id: str,
    icon_text: str = "",
    jiaoben_project_id: int | None = None,
) -> dict:
    """写入 project.json，自定义图标复制为工程内 icon.png。"""
    project_dir = project_dir.resolve()
    err = validate_pack_fields(name, package_id, project_dir, icon_text)
    if err:
        raise ValueError(err)

    cfg = read_project_cfg(project_dir)
    cfg["name"] = name.strip()
    cfg["package_id"] = package_id.strip()

    icon_path = resolve_icon_file(project_dir, icon_text)
    if icon_path is not None:
        dest = project_dir / "icon.png"
        if icon_path != dest.resolve():
            shutil.copy2(icon_path, dest)
        cfg["icon"] = "icon.png"
    else:
        cfg.pop("icon", None)

    if jiaoben_project_id is not None:
        cfg.setdefault("jiaoben", {})
        pid = int(jiaoben_project_id)
        if pid > 0:
            cfg["jiaoben"]["project_id"] = pid
        else:
            cfg["jiaoben"].pop("project_id", None)
    license_cfg = cfg.get("license") or {}
    if license_cfg.get("api_base"):
        cfg.setdefault("jiaoben", {})
        cfg["jiaoben"]["api_base"] = license_cfg.get("api_base")

    cfg_path = project_dir / "project.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cfg


def write_gradle_props(cfg: dict, props_path: Path, signing: dict | None = None) -> None:
    license_cfg = cfg.get("license") or {}
    jiaoben_cfg = cfg.get("jiaoben") or {}
    jiaoben_base = str(
        jiaoben_cfg.get("api_base") or license_cfg.get("api_base") or "http://111.229.202.251:8687"
    ).strip()
    jiaoben_project_id = int(jiaoben_cfg.get("project_id") or 0)
    lines = [
        f"applicationId={cfg['package_id']}",
        f"versionCode={cfg.get('version_code', 1)}",
        f"versionName={cfg.get('version_name', '1.0.0')}",
        f"appName={escape_gradle_property(str(cfg.get('name', 'Auto Script')))}",
        f"jiaobenApiBase={jiaoben_base}",
        f"jiaobenProjectId={jiaoben_project_id}",
    ]
    if signing:
        ks = signing.get("keystore")
        if ks:
            lines.append(f"signingStoreFile={Path(ks).resolve()}")
            lines.append(f"signingStorePassword={signing.get('ks_pass', '')}")
            lines.append(f"signingKeyAlias={signing.get('key_alias', '')}")
            lines.append(
                f"signingKeyPassword={signing.get('key_pass', signing.get('ks_pass', ''))}"
            )
    props_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
