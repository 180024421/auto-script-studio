"""布局编辑撤销 / 重做栈。"""

from __future__ import annotations

from typing import Any

from studio.services.layout_clone import clone_layout


class LayoutHistory:
    def __init__(self, *, max_depth: int = 40) -> None:
        self._max = max_depth
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def push(self, layout: dict[str, Any]) -> None:
        snap = clone_layout(layout)
        if self._undo and self._undo[-1] == snap:
            return
        self._undo.append(snap)
        if len(self._undo) > self._max:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self) -> bool:
        return len(self._undo) > 1

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self, current: dict[str, Any]) -> dict[str, Any] | None:
        if len(self._undo) < 2:
            return None
        self._redo.append(clone_layout(current))
        self._undo.pop()
        return clone_layout(self._undo[-1])

    def redo(self) -> dict[str, Any] | None:
        if not self._redo:
            return None
        snap = self._redo.pop()
        self._undo.append(clone_layout(snap))
        return clone_layout(snap)
