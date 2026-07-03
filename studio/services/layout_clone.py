"""布局深拷贝 — 替代 json.loads(json.dumps(...))。"""

from __future__ import annotations

import copy
from typing import Any


def clone_layout(layout: dict[str, Any] | None) -> dict[str, Any]:
    if not layout:
        return {}
    return copy.deepcopy(layout)


def clone_widget(widget: dict[str, Any] | None) -> dict[str, Any]:
    if not widget:
        return {}
    return copy.deepcopy(widget)


def clone_list(items: list[Any] | None) -> list[Any]:
    if not items:
        return []
    return copy.deepcopy(items)
