"""浮动面板控件路径：根列表与 tabs 内嵌套。"""

from __future__ import annotations

from typing import Any

from studio.services.layout_clone import clone_layout

# 根控件: (i,)
# 标签页内: (tabs_widget_idx, tab_idx, child_idx)


def path_to_str(path: tuple[int, ...]) -> str:
    return "/".join(str(p) for p in path)


def str_to_path(s: str) -> tuple[int, ...]:
    if not s or s == "/":
        return ()
    return tuple(int(p) for p in s.split("/") if p != "")


def container_prefix(path: tuple[int, ...]) -> tuple[int, ...]:
    """返回控件所在列表的容器路径。根列表为 ()，页内为 (tabs_idx, tab_idx)。"""
    if len(path) <= 1:
        return ()
    if len(path) == 3:
        return (path[0], path[1])
    return path[:-1]


def list_index(path: tuple[int, ...]) -> int:
    return path[-1]


def get_widget_list(layout: dict[str, Any], container: tuple[int, ...]) -> list[dict[str, Any]] | None:
    widgets = layout.get("widgets") or layout.get("buttons") or []
    if not container:
        return widgets
    if len(container) != 2:
        return None
    tabs_idx, tab_idx = container
    if tabs_idx < 0 or tabs_idx >= len(widgets):
        return None
    tw = widgets[tabs_idx]
    if tw.get("type") != "tabs":
        return None
    tabs = tw.get("tabs") or []
    if tab_idx < 0 or tab_idx >= len(tabs):
        return None
    return tabs[tab_idx].setdefault("widgets", [])


def get_widget_spec(layout: dict[str, Any], path: tuple[int, ...]) -> dict[str, Any] | None:
    lst = get_widget_list(layout, container_prefix(path))
    if lst is None:
        return None
    idx = list_index(path)
    if idx < 0 or idx >= len(lst):
        return None
    return lst[idx]


def reorder_in_container(
    layout: dict[str, Any], container: tuple[int, ...], from_idx: int, to_idx: int
) -> dict[str, Any]:
    import json

    out = clone_layout(layout)
    lst = get_widget_list(out, container)
    if lst is None or from_idx == to_idx:
        return out
    if from_idx < 0 or from_idx >= len(lst) or to_idx < 0 or to_idx >= len(lst):
        return out
    item = lst.pop(from_idx)
    to_idx = max(0, min(len(lst), to_idx))
    lst.insert(to_idx, item)
    return out


def set_widget_width(layout: dict[str, Any], path: tuple[int, ...], width: int) -> dict[str, Any]:
    import json

    out = clone_layout(layout)
    spec = get_widget_spec(out, path)
    if spec is not None:
        spec["width"] = max(1, min(3, int(width)))
    return out


def remap_path_after_reorder(
    path: tuple[int, ...], container: tuple[int, ...], from_idx: int, to_idx: int
) -> tuple[int, ...]:
    if container_prefix(path) != container:
        return path
    idx = list_index(path)
    if idx == from_idx:
        new_idx = to_idx
    elif from_idx < to_idx and from_idx < idx <= to_idx:
        new_idx = idx - 1
    elif to_idx < from_idx and to_idx <= idx < from_idx:
        new_idx = idx + 1
    else:
        new_idx = idx
    return path[:-1] + (new_idx,)
