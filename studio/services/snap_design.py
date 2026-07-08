"""自由布局设计坐标 8px 网格吸附。"""

from __future__ import annotations

SNAP_GRID = 8


def snap_design(v: int, *, grid: int = SNAP_GRID) -> int:
    if grid <= 1:
        return int(v)
    return int(round(v / grid) * grid)
