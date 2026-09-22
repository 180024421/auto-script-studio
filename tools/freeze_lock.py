"""重新生成 studio/requirements.lock.txt —— 只保留运行时依赖闭包。

    .venv\\Scripts\\python.exe tools/freeze_lock.py

为什么不用 `pip freeze > lock`：开发用 .venv 里同时装了 pytest/ruff（见
requirements-dev.txt），整份 freeze 会把工具链写进运行时锁文件，CI 装锁文件时
就顺带装了 dev 工具，两层依赖的边界随即失效。

锁文件的用途是「可复现环境」：CI 与给别人装机时用它；日常开发仍用
studio/requirements.txt 的范围声明。
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCK = REPO / "studio" / "requirements.lock.txt"
REQUIREMENTS = REPO / "studio" / "requirements.txt"

#: 需要进锁文件的包（直接依赖 + 其不可省略的传递依赖）
PINNED = [
    "PySide6",
    "PySide6_Essentials",
    "PySide6_Addons",
    "shiboken6",
    "opencv-python",
    "numpy",
    "pillow",
    "PyYAML",
    "lupa",
]


def installed_versions() -> dict[str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"pip freeze 失败:\n{proc.stderr.strip()}")
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "==" not in line or line.startswith("#") or line.startswith("-e"):
            continue
        name, _, version = line.partition("==")
        out[name.strip()] = version.strip()
    return out


def declared_ranges() -> list[str]:
    if not REQUIREMENTS.is_file():
        return []
    lines = []
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def main() -> int:
    versions = installed_versions()
    missing = [name for name in PINNED if name not in versions]
    if missing:
        print(f"错误: 当前环境缺 {', '.join(missing)}；请在装好依赖的 .venv 里运行本脚本", file=sys.stderr)
        return 1

    ranges = declared_ranges()
    header = [
        "# 精确锁定的 Studio 运行依赖 —— 可复现环境用",
        "#",
        f"# 由 tools/freeze_lock.py 于 {date.today().isoformat()} 生成，来源 {Path(sys.executable)}",
        "# （Python " + sys.version.split()[0] + "）",
        "# 只覆盖 studio/requirements.txt 的直接依赖及其闭包；",
        "# 开发/CI 工具在 requirements-dev.txt。",
        "#",
        "# CI 安装：pip install -r studio/requirements.lock.txt",
    ]
    if ranges:
        header.append("# 对应的范围声明: " + "; ".join(ranges))
    body = [f"{name}=={versions[name]}" for name in PINNED]
    LOCK.write_text("\n".join(header + body) + "\n", encoding="utf-8")
    print(f"已写入 {LOCK.relative_to(REPO)}（{len(body)} 个包）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
