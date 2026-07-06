"""jiaoben 脚本发版 API 客户端（Studio 用）。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def _api_base(cfg: dict) -> str:
    jiaoben = cfg.get("jiaoben") or {}
    license_cfg = cfg.get("license") or {}
    base = str(jiaoben.get("api_base") or license_cfg.get("api_base") or "").strip().rstrip("/")
    return base


def list_projects(cfg: dict, *, token: str = "") -> list[dict[str, Any]]:
    base = _api_base(cfg)
    if not base:
        return []
    prefix = base if base.endswith("/api") else f"{base}/api"
    url = f"{prefix}/script/update/projects"
    req = urllib.request.Request(url)
    if token:
        req.add_header("X-Script-Update-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return []
    if isinstance(data, list):
        return data
    return data.get("data") or data.get("projects") or []


def fetch_projects_for_combo(cfg: dict) -> list[tuple[int, str]]:
    rows = list_projects(cfg)
    out: list[tuple[int, str]] = []
    for row in rows:
        pid = int(row.get("project_id") or row.get("projectId") or 0)
        if pid <= 0:
            continue
        name = str(row.get("project_name") or row.get("projectName") or pid)
        pkg = str(row.get("app_package") or row.get("appPackage") or "")
        label = f"{name} (#{pid})" + (f" · {pkg}" if pkg else "")
        out.append((pid, label))
    return out
