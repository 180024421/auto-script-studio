"""将 sibling 项目 adb-ide 加入 Python 路径，复用其 IDE 与 automation 能力。"""

from __future__ import annotations

import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
REPO_ROOT = STUDIO_ROOT.parent
ADB_IDE_ROOT = REPO_ROOT.parent / "adb-ide"


def ensure_adb_ide_path() -> Path:
    if not ADB_IDE_ROOT.is_dir():
        raise RuntimeError(
            "未找到 adb-ide 项目。\n"
            f"请将 adb-ide 放在: {ADB_IDE_ROOT}\n"
            "（与 auto-script-studio 同级目录，例如 E:\\xiangmu\\adb-ide）"
        )
    path = str(ADB_IDE_ROOT.resolve())
    if path not in sys.path:
        sys.path.insert(0, path)
    return ADB_IDE_ROOT
