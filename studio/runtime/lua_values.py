"""Lua 表与 Python 值互转（lupa）。"""

from __future__ import annotations

from typing import Any


def table_to_dict(value: Any) -> dict[str, Any]:
    """将 Lua opts 表或 Python dict 转为普通 dict。"""
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        from lupa import lua_type
    except ImportError:
        return {}
    if lua_type(value) != "table":
        return {}
    out: dict[str, Any] = {}
    for key, val in value.items():
        out[str(key)] = lua_to_python(val)
    return out


def lua_to_python(value: Any) -> Any:
    if value is None:
        return None
    try:
        from lupa import lua_type
    except ImportError:
        return value
    lt = lua_type(value)
    if lt is None or lt == "nil":
        return None
    if lt == "boolean":
        return bool(value)
    if lt == "number":
        return float(value) if isinstance(value, float) else int(value) if float(value).is_integer() else float(value)
    if lt == "string":
        return str(value)
    if lt == "table":
        return _table_to_value(value)
    return value


def _table_to_value(table: Any) -> Any:
    try:
        from lupa import lua_type
    except ImportError:
        return table
    length = len(table)
    if length > 0:
        items = [lua_to_python(table[i]) for i in range(1, length + 1)]
        # 纯数组表
        if all(isinstance(k, int) or str(k).isdigit() for k in table.keys()):
            keys = list(table.keys())
            if len(keys) == length:
                return items
        return items
    return table_to_dict(table)


def roi_tuple(opts: dict[str, Any]) -> tuple[int, int, int, int] | None:
    roi = opts.get("roi")
    if roi is None:
        return None
    if isinstance(roi, (list, tuple)) and len(roi) == 4:
        return int(roi[0]), int(roi[1]), int(roi[2]), int(roi[3])
    if isinstance(roi, dict):
        return (
            int(roi["x"]),
            int(roi["y"]),
            int(roi["w"]),
            int(roi["h"]),
        )
    return None


def frac_pair(opts: dict[str, Any]) -> tuple[float, float]:
    frac = opts.get("frac")
    if isinstance(frac, (list, tuple)) and len(frac) == 2:
        return float(frac[0]), float(frac[1])
    return 0.5, 0.5
