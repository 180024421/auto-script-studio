"""pytest 共享配置 — 统一 Qt/无头环境与可选依赖跳过。

解决的问题：
1. ``QT_QPA_PLATFORM`` 未设置时，导入 ``QtWidgets`` 的测试在 Linux/CI runner 上会
   因找不到 X display 而失败（而不是被识别为「缺依赖」）。
2. 各测试文件处理「可选依赖缺失」的写法不一致：有的 ``pytest.importorskip``，
   有的在模块顶层裸 ``import PySide6``（收集阶段直接 ImportError）。这里统一在
   收集前判定并跳过整个文件，测试文件本身无需再写 skip 样板。

新增可选依赖只需往 ``OPTIONAL_DEPS`` 里加一项。
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# 无显示环境（Linux CI / SSH）下让 Qt 走 offscreen 平台插件
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# 测试期间不往仓库 .studio/logs 写应用日志
os.environ.setdefault("STUDIO_NO_LOG", "1")

# 依赖缺失 → 跳过引用它的测试文件。键是 import 名，值是测试源码里的匹配标记。
OPTIONAL_DEPS: dict[str, str] = {
    "PySide6": "PySide6",
}

_qapp = None  # 会话级 QApplication，pytest_configure 中创建


def _available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except Exception:
        return False


def _missing_marker(test_file: Path) -> str | None:
    """该测试文件引用了哪个不可用依赖的标记（无则 None）。"""
    try:
        text = test_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for module, marker in OPTIONAL_DEPS.items():
        if marker in text and not _available(module):
            return module
    return None


#: pytest 在收集前读取；条目相对于本 conftest 所在目录。
collect_ignore: list[str] = []
_skipped_for_missing: list[tuple[str, str]] = []
for _file in sorted(TESTS_DIR.glob("test_*.py")):
    _missing = _missing_marker(_file)
    if _missing is not None:
        collect_ignore.append(_file.name)
        _skipped_for_missing.append((_file.name, _missing))


def pytest_configure(config) -> None:
    """整个会话共享一个 QApplication。

    Qt 的文字/字体绘制（``drawText`` / ``QFontMetrics``）在没有 application 实例时
    会**永久阻塞**而不是报错——Windows + PySide6 6.11 实测：``paint_layout_overlay``
    卡在 ``drawText`` 再不返回。任何绘制类测试都需要它先存在。
    """
    global _qapp
    if not _available("PySide6"):
        return
    from PySide6.QtWidgets import QApplication

    _qapp = QApplication.instance() or QApplication([])


def pytest_unconfigure(config) -> None:  # pragma: no cover - 进程退出前清理
    global _qapp
    _qapp = None


def pytest_report_header(config) -> str:  # pragma: no cover - 仅输出诊断信息
    qt = "可用" if _available("PySide6") else "缺失"
    lupa = "可用" if _available("lupa") else "缺失"
    lines = [
        f"auto-script-studio: PySide6={qt} lupa={lupa} "
        f"QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM')}"
    ]
    if _skipped_for_missing:
        detail = "、".join(f"{name}（缺 {dep}）" for name, dep in _skipped_for_missing)
        lines.append(f"跳过需要未安装依赖的测试文件: {detail}")
    return "\n".join(lines)
