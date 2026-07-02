"""Auto Script Studio — PC 开发助手入口（独立，不依赖 adb-ide）。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from studio.ui.main_window import run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
