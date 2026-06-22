"""Auto Script Studio — PC 开发助手入口。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        from studio.ui.studio_main_window import run_app
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        print("\n回退到简易 Studio（无 adb-ide）…", file=sys.stderr)
        from studio.ui.main_window import run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
