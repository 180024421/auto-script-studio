"""从 Studio「发卡项目」下拉框解析 project_id。"""

from __future__ import annotations

import re
from typing import Any

_MANUAL_LABEL = "（手动输入 ID）"
_ID_IN_LABEL = re.compile(r"#(\d+)")
_ID_IN_PARENS = re.compile(r"\((\d+)\)\s*$")


def resolve_jiaoben_project_id(combo: Any) -> int:
    """解析 QComboBox 当前选中的 jiaoben 项目 ID。"""
    idx = combo.currentIndex()
    if idx >= 0:
        data = combo.itemData(idx)
        if data is not None:
            try:
                pid = int(data)
                if pid > 0:
                    return pid
            except (TypeError, ValueError):
                pass

    text = combo.currentText().strip()
    if not text or text == _MANUAL_LABEL:
        return 0
    if text.isdigit():
        return int(text)

    for pattern in (_ID_IN_LABEL, _ID_IN_PARENS):
        m = pattern.search(text)
        if m:
            return int(m.group(1))

    for i in range(combo.count()):
        if combo.itemText(i) == text:
            try:
                pid = int(combo.itemData(i) or 0)
                if pid > 0:
                    return pid
            except (TypeError, ValueError):
                pass
    return 0
