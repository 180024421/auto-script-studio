"""本机界面片段库（跨工程复用一屏控件）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from studio.services.layout_clone import clone_list


def snippets_root() -> Path:
    root = Path.home() / ".autoscript-studio" / "screen-snippets"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_name(name: str) -> str:
    raw = (name or "").strip() or "未命名界面"
    slug = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", raw, flags=re.UNICODE)
    return slug[:64] or "snippet"


def list_snippets() -> list[dict[str, Any]]:
    """返回 [{name, title, widget_count, path}, ...]，按修改时间倒序。"""
    items: list[dict[str, Any]] = []
    for path in snippets_root().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        widgets = data.get("widgets") or []
        items.append(
            {
                "name": path.stem,
                "title": str(data.get("title") or path.stem),
                "widget_count": len(widgets),
                "path": str(path),
                "mtime": path.stat().st_mtime,
            }
        )
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def save_screen_snippet(name: str, screen: dict[str, Any]) -> Path:
    payload = {
        "version": 1,
        "title": str(screen.get("title") or name).strip() or name,
        "widgets": clone_list(screen.get("widgets") or []),
    }
    path = snippets_root() / f"{_safe_name(name)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_screen_snippet(name: str) -> dict[str, Any] | None:
    path = snippets_root() / f"{_safe_name(name)}.json"
    if not path.is_file():
        # 也允许直接传 stem
        path = snippets_root() / f"{name}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {
        "title": str(data.get("title") or path.stem),
        "widgets": clone_list(data.get("widgets") or []),
    }


def delete_snippet(name: str) -> bool:
    path = snippets_root() / f"{_safe_name(name)}.json"
    if not path.is_file():
        path = snippets_root() / f"{name}.json"
    if path.is_file():
        path.unlink()
        return True
    return False
