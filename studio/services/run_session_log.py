"""脚本运行会话归档 — 每次 PC 运行 / 热替换 / 打包留下一个独立日志文件。

``studio.log`` 是**应用级**滚动日志；排查「这个脚本跑到第 40 分钟为什么挂了」需要的是
**单次运行**的完整输出。这里把 ``script_run_log`` 看到的每一行同时落到::

    <仓库>/.studio/logs/runs/20260922-213105-pc-demo-game.log

文件头部记录工程路径、运行目标、设备序列号、Python 版本，结尾记录退出码与耗时，
中间是与运行日志窗口逐行一致的内容。默认保留最近 50 个会话文件。

所有写盘操作都是 best-effort：日志失败绝不影响脚本运行。
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from studio.services.app_log import get_logger, log_dir

__all__ = ["RunSession", "prune_sessions", "start_session"]

KEEP_SESSIONS = 50
log = get_logger("run_session")


class RunSession:
    """一次脚本运行的落盘句柄。关闭后 ``write`` 变成空操作。"""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.started_at = time.time()
        self._fh = None
        self._closed = path is None
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._fh = path.open("w", encoding="utf-8", errors="replace")
            except Exception as exc:
                log.warning("会话日志不可用（%s）: %s", type(exc).__name__, exc)
                self._fh = None
                self._closed = True

    @property
    def is_open(self) -> bool:
        return self._fh is not None and not self._closed

    def write(self, line: str = "") -> None:
        """写入一行（带 ``HH:MM:SS.mmm`` 前缀，便于和卡住的时间点对齐）。"""
        if not self.is_open or self._fh is None:
            return
        try:
            now = datetime.now()
            stamp = f"{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}"
            self._fh.write(f"{stamp}  {line}\n")
            self._fh.flush()
        except Exception as exc:  # 磁盘满 / 文件被外部删除
            self._closed = True
            log.warning("会话日志写入中断: %s", exc)

    def finish(self, note: str = "") -> None:
        """写结尾摘要并关闭。"""
        elapsed = time.time() - self.started_at
        self.write("─" * 60)
        self.write(f"{note}（耗时 {elapsed:.1f}s）" if note else f"结束（耗时 {elapsed:.1f}s）")
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
        self._fh = None
        self._closed = True

    def lines(self) -> int:  # pragma: no cover - 诊断辅助
        if self.path is None or not self.path.is_file():
            return 0
        try:
            return sum(1 for _ in self.path.open("r", encoding="utf-8", errors="ignore"))
        except Exception:
            return 0


def _safe_token(value: str, default: str = "run") -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in value.strip())
    return cleaned.strip("-")[:48] or default


def sessions_dir(root: Path | str | None = None) -> Path:
    return log_dir(root) / "runs"


def start_session(
    mode: str,
    project_dir: Path | str | None,
    *,
    root: Path | str | None = None,
    device: str = "",
    script: str = "",
    header_lines: tuple[str, ...] | None = None,
) -> RunSession:
    """开启一次会话归档。``mode`` 如 ``pc`` / ``push`` / ``pack``。"""
    project_path = Path(project_dir).resolve() if project_dir else None
    name = _safe_token(project_path.name if project_path else mode, "project")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = sessions_dir(root) / f"{stamp}-{_safe_token(mode)}-{name}.log"

    session = RunSession(path)
    session.write(f"# auto-script-studio 运行会话 — mode={mode}")
    session.write(f"# started  : {datetime.now().isoformat(timespec='seconds')}")
    session.write(f"# project  : {project_path or '(未打开工程)'}")
    if script:
        session.write(f"# script   : {script}")
    session.write(f"# device   : {device or '(无)'}")
    session.write(f"# python   : {sys.version.split()[0]} ({sys.executable})")
    session.write(f"# cwd      : {os.getcwd()}")
    for line in header_lines or ():
        session.write(f"# {line}")
    session.write("")
    log.info("运行会话开始 mode=%s file=%s", mode, path)
    return session


def prune_sessions(keep: int = KEEP_SESSIONS, root: Path | str | None = None) -> int:
    """只保留最近 ``keep`` 个会话文件，返回删除数。"""
    folder = sessions_dir(root)
    if not folder.is_dir():
        return 0
    try:
        files = sorted(
            (p for p in folder.glob("*.log") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception as exc:
        log.warning("会话目录枚举失败: %s", exc)
        return 0
    removed = 0
    for old in files[max(keep, 0):]:
        try:
            old.unlink()
            removed += 1
        except Exception:
            pass
    if removed:
        log.info("清理旧运行会话日志 %d 个", removed)
    return removed
