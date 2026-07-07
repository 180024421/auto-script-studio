"""jiaoben project_id 解析。"""

from __future__ import annotations


class _FakeCombo:
    def __init__(self, items: list[tuple[str, int]], *, index: int = -1, text: str = "") -> None:
        self._items = items
        self._index = index
        self._text = text

    def currentIndex(self) -> int:
        return self._index

    def currentData(self):
        if self._index < 0:
            return None
        return self._items[self._index][1]

    def currentText(self) -> str:
        if self._text:
            return self._text
        if 0 <= self._index < len(self._items):
            return self._items[self._index][0]
        return ""

    def count(self) -> int:
        return len(self._items)

    def itemText(self, i: int) -> str:
        return self._items[i][0]

    def itemData(self, i: int):
        return self._items[i][1]


def test_resolve_from_combo_data():
    from studio.services.jiaoben_project_id import resolve_jiaoben_project_id

    combo = _FakeCombo([("（手动输入 ID）", 0), ("Demo (#42) · com.demo", 42)], index=1)
    assert resolve_jiaoben_project_id(combo) == 42


def test_resolve_from_hash_in_text():
    from studio.services.jiaoben_project_id import resolve_jiaoben_project_id

    combo = _FakeCombo([], index=-1, text="Demo (#99) · com.demo")
    assert resolve_jiaoben_project_id(combo) == 99


def test_resolve_plain_digits():
    from studio.services.jiaoben_project_id import resolve_jiaoben_project_id

    combo = _FakeCombo([], index=-1, text="123")
    assert resolve_jiaoben_project_id(combo) == 123
