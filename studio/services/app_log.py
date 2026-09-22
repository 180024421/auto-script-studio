"""Studio 统一日志设施 — 落盘文件日志、级别控制、未捕获异常记录。

用法（任意模块）::

    from studio.services.app_log import get_logger

    log = get_logger(__name__)
    log.warning("adb 不可用: %s", exc)

主窗口启动时调用一次 ``setup_logging()``，日志写入 ``<仓库>/.studio/logs/studio.log``
（滚动 2MB × 5 个文件）。``.studio/`` 已在 ``.gitignore`` 中，不会产生提交噪音。

环境变量：

=================  ==============================================
``STUDIO_LOG_LEVEL``  级别，默认 ``INFO``；排查问题时用 ``DEBUG``
``STUDIO_LOG_DIR``    改写日志目录（默认 ``<仓库>/.studio/logs``）
``STUDIO_LOG_CONSOLE``  ``1`` 强制同时输出到 stderr（默认自动判断）
``STUDIO_NO_LOG``     ``1`` 完全关闭文件日志（测试用）
=================  ==============================================

设计约束：日志设施本身**永不抛异常**。它跑在 UI 线程和脚本运行回调里，
任何一次写盘失败都不应该让「点击运行」变成崩溃。
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

__all__ = [
    "get_logger",
    "install_excepthooks",
    "log_dir",
    "log_file_path",
    "setup_logging",
    "shutdown_logging",
]

ROOT_LOGGER_NAME = "studio"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5
_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"

REPO_ROOT = Path(__file__).resolve().parents[2]

_lock = threading.Lock()
_configured = False
_active_file: Path | None = None
_prev_excepthook = None
_prev_thread_hook = None


def _env_flag(name: str, default: str = "") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def log_dir(root: Path | str | None = None) -> Path:
    """日志目录。``STUDIO_LOG_DIR`` 优先，否则 ``<仓库>/.studio/logs``。"""
    env = os.environ.get("STUDIO_LOG_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    base = Path(root).resolve() if root else REPO_ROOT
    return base / ".studio" / "logs"


def log_file_path(root: Path | str | None = None) -> Path:
    return log_dir(root) / "studio.log"


def _resolve_level(level: int | str | None) -> int:
    if isinstance(level, int):
        return level
    raw = (level or os.environ.get("STUDIO_LOG_LEVEL", "") or "INFO").strip().upper()
    return getattr(logging, raw, None) or logging.INFO


def _console_ok(requested: bool | None) -> bool:
    if requested is not None:
        return requested
    if _env_flag("STUDIO_LOG_CONSOLE"):
        return True
    # pythonw.exe / 打包后的 GUI 没有可用 stderr
    stream = sys.stderr
    if stream is None or not hasattr(stream, "write"):
        return False
    try:
        return bool(getattr(stream, "isatty", lambda: False)())
    except Exception:
        return False


def setup_logging(
    root: Path | str | None = None,
    *,
    level: int | str | None = None,
    console: bool | None = None,
    force: bool = False,
) -> Path | None:
    """配置 ``studio`` 记录器。幂等；返回当前日志文件路径（禁用文件日志时返回 ``None``）。"""
    global _configured, _active_file

    with _lock:
        if _configured and not force:
            return _active_file

        logger = logging.getLogger(ROOT_LOGGER_NAME)
        level_value = _resolve_level(level)
        logger.setLevel(level_value)
        logger.propagate = False

        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

        formatter = logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        if console is None:
            console = _console_ok(None)
        if console:
            stream = logging.StreamHandler(sys.stderr)
            stream.setFormatter(formatter)
            logger.addHandler(stream)

        _active_file = None
        if not _env_flag("STUDIO_NO_LOG"):
            path = log_file_path(root)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = RotatingFileHandler(
                    path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8", delay=True
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(level_value)
                logger.addHandler(file_handler)
                _active_file = path
            except Exception as exc:  # 只读目录 / 磁盘满 → 降级为仅控制台
                logger.warning("文件日志不可用（%s）: %s", type(exc).__name__, exc)

        _configured = True
        logger.info(
            "Studio 日志启动 — level=%s file=%s python=%s",
            logging.getLevelName(level_value),
            _active_file or "(关闭)",
            sys.version.split()[0],
        )
        return _active_file


def get_logger(name: str | None = None) -> logging.Logger:
    """取 ``studio.*`` 子记录器；未 ``setup_logging`` 前也能安全调用（走 logging.lastResort）。"""
    if not name or name == ROOT_LOGGER_NAME:
        return logging.getLogger(ROOT_LOGGER_NAME)
    if name.startswith(ROOT_LOGGER_NAME + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def install_excepthooks(logger: logging.Logger | None = None) -> None:
    """把未捕获异常（含 Qt 槽函数与 QThread）写入日志文件。

    PySide6 会在打印后继续运行；这里只保证「崩过一次的地方留得下来」，
    不改变原有异常传播行为（原 hook 仍会被调用）。
    """
    global _prev_excepthook, _prev_thread_hook
    log = logger or get_logger("crash")
    if _prev_excepthook is None:
        _prev_excepthook = sys.excepthook

    def _hook(exc_type, exc, tb):
        try:
            log.critical("未捕获异常", exc_info=(exc_type, exc, tb))
        except Exception:
            pass
        try:
            if _prev_excepthook is not None:
                _prev_excepthook(exc_type, exc, tb)
        except Exception:
            pass

    sys.excepthook = _hook

    if _prev_thread_hook is None:
        _prev_thread_hook = threading.excepthook

    def _thread_hook(args):
        try:
            log.critical(
                "线程未捕获异常 (%s)",
                getattr(args.thread, "name", "?"),
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
        except Exception:
            pass
        try:
            if _prev_thread_hook is not None:
                _prev_thread_hook(args)
        except Exception:
            pass

    try:
        threading.excepthook = _thread_hook
    except Exception:
        pass


def shutdown_logging() -> None:
    """退出时刷新并关闭文件句柄（避免最后几行丢在缓冲区）。

    之后可再次 ``setup_logging()``（同一进程内重开主窗口、或测试用例之间）。
    """
    global _configured, _active_file
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(logger.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
        logger.removeHandler(handler)
    _configured = False
    _active_file = None
