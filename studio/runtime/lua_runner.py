"""在 PC 上通过 lupa 运行工程 main.lua（ADB + vision_pc）。"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ensure_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def install_bot(lua, bot) -> None:
    from studio.runtime.lua_values import table_to_dict
    from studio.runtime.panel_state import PanelState

    def _ret_point(pt):
        if pt is None:
            return None
        return pt[0], pt[1]

    def delay(seconds):
        bot.delay_seconds(seconds)

    def tap(x, y):
        bot.tap(int(x), int(y))

    def swipe(x1, y1, x2, y2, duration_ms=300):
        bot.swipe(int(x1), int(y1), int(x2), int(y2), int(duration_ms or 300))

    def long_press(x, y, duration_ms=500):
        bot.long_press(int(x), int(y), int(duration_ms or 500))

    def find_image(path, opts=None):
        return _ret_point(bot.find_image(str(path), table_to_dict(opts)))

    def find_color(b, g, r, opts=None):
        return _ret_point(bot.find_color(int(b), int(g), int(r), table_to_dict(opts)))

    def find_text(target, opts=None):
        return _ret_point(bot.find_text(str(target), table_to_dict(opts)))

    def find_node(opts=None):
        return _ret_point(bot.find_node(table_to_dict(opts)))

    def recognize_text(opts=None):
        return bot.recognize_text(table_to_dict(opts))

    def recognize_digits(opts=None):
        if hasattr(bot, "recognize_digits"):
            return bot.recognize_digits(table_to_dict(opts))
        raise RuntimeError(
            "bot.recognizeDigits 需 Bot 实现 recognize_digits；"
            "请将 game-digit-trainer 导出包放到工程 models/ 并更新 Studio"
        )

    def yolo_detect(opts=None):
        return bot.yolo_detect(table_to_dict(opts))

    def find_yolo(opts=None):
        return _ret_point(bot.find_yolo(table_to_dict(opts)))

    def yolo_swipe(opts=None):
        bot.yolo_swipe(table_to_dict(opts))

    def log(msg):
        bot.log(str(msg))

    def log_raw(msg):
        bot.log(str(msg))

    def toast(msg):
        bot.toast(str(msg))

    def open_app(package_name):
        return bool(bot.open_app(str(package_name)))

    def list_apps():
        raise RuntimeError("bot.listApps 仅 APK 可用（PC 联调不支持）")

    def reload_panel():
        raise RuntimeError("bot.reloadPanel 仅 APK 可用（PC 联调不支持）")

    def read_chain(*_a, **_k):
        raise RuntimeError("bot.read_chain 需 APK + root（PC 联调不支持）")

    def load_bases(*_a, **_k):
        raise RuntimeError("bot.load_bases 需 APK + root（PC 联调不支持）")

    def set_memory_pid(*_a, **_k):
        raise RuntimeError("bot.set_memory_pid 需 APK + root（PC 联调不支持）")

    def set_pointer_size(*_a, **_k):
        raise RuntimeError("bot.set_pointer_size 需 APK + root（PC 联调不支持）")

    bot_table = lua.table_from(
        {
            "delay": delay,
            "tap": tap,
            "swipe": swipe,
            "longPress": long_press,
            "findImage": find_image,
            "findColor": find_color,
            "findText": find_text,
            "findNode": find_node,
            "recognizeText": recognize_text,
            "recognizeDigits": recognize_digits,
            "yoloDetect": yolo_detect,
            "findYolo": find_yolo,
            "yoloSwipe": yolo_swipe,
            "waitGoneImage": lambda path, opts=None: bot.wait_gone_image(str(path), table_to_dict(opts)),
            "waitStable": lambda opts=None: bot.wait_stable(table_to_dict(opts)),
            "findMultiColor": lambda opts=None: _ret_point(bot.find_multi_color(table_to_dict(opts))),
            "trace": lambda tag, msg: bot.trace(str(tag), str(msg)),
            "toast": toast,
            "openApp": open_app,
            "log": log,
            "__logRaw": log_raw,
            "listApps": list_apps,
            "reloadPanel": reload_panel,
            "read_chain": read_chain,
            "load_bases": load_bases,
            "set_memory_pid": set_memory_pid,
            "set_pointer_size": set_pointer_size,
        }
    )
    g = lua.globals()
    g["bot"] = bot_table

    def _mem_unsupported(name: str):
        def _fn(*_a, **_k):
            raise RuntimeError(f"{name} 需 APK + root（PC 联调不支持）")

        return _fn

    g["mem"] = lua.table_from(
        {
            "find_pid": _mem_unsupported("mem.find_pid"),
            "search": _mem_unsupported("mem.search"),
            "refine": _mem_unsupported("mem.refine"),
            "read_cached": _mem_unsupported("mem.read_cached"),
            "get_address": _mem_unsupported("mem.get_address"),
            "candidates": _mem_unsupported("mem.candidates"),
            "clear": _mem_unsupported("mem.clear"),
            "lock": _mem_unsupported("mem.lock"),
            "aob_scan": _mem_unsupported("mem.aob_scan"),
            "read": _mem_unsupported("mem.read"),
            "list_modules": _mem_unsupported("mem.list_modules"),
            "read_chain": _mem_unsupported("mem.read_chain"),
            "load_bases": _mem_unsupported("mem.load_bases"),
        }
    )

    def panel_get(widget_id):
        return PanelState.get(str(widget_id))

    def panel_set(widget_id, value):
        PanelState.set(str(widget_id), str(value))

    def panel_is(widget_id, expected):
        return PanelState.is_value(str(widget_id), str(expected))

    def panel_has(widget_id, option):
        return PanelState.has_option(str(widget_id), str(option))

    def panel_values():
        return dict(PanelState.all())

    def panel_watch(widget_id, fn):
        PanelState.watch(str(widget_id), lambda v: fn(v))

    def panel_unwatch(widget_id, fn=None):
        if fn is None:
            PanelState.unwatch(str(widget_id))
        else:
            PanelState.unwatch(str(widget_id), lambda v: fn(v))

    def panel_is_on(widget_id):
        return PanelState.is_on(str(widget_id))

    def panel_get_time_range(widget_id):
        start, end = PanelState.time_range(str(widget_id))
        return start, end

    def panel_snapshot():
        return PanelState.snapshot()

    g["panel"] = lua.table_from(
        {
            "get": panel_get,
            "set": panel_set,
            "is": panel_is,
            "has": panel_has,
            "values": panel_values,
            "watch": panel_watch,
            "unwatch": panel_unwatch,
            "isOn": panel_is_on,
            "getTimeRange": panel_get_time_range,
            "snapshot": panel_snapshot,
        }
    )

    pkg = g["package"]
    if pkg is not None:
        loaded = pkg["loaded"]
        if loaded is not None:
            loaded["autoscript"] = bot_table


def run_project(project_dir: Path, *, serial: str | None = None) -> int:
    _ensure_path()
    try:
        from lupa import LuaRuntime
    except ImportError as exc:
        print("需要 lupa：pip install lupa>=2.0", file=sys.stderr)
        raise SystemExit(1) from exc

    from studio.runtime.lua_execute import (
        chunk_name_for,
        execute_lua_chunk,
        format_lua_error,
        install_lua_logging,
    )
    from studio.runtime.pc_bot import PcBot
    from studio.runtime.panel_state import PanelState
    from studio.services.layout_defaults import load_layout

    project_dir = Path(project_dir)
    cfg_path = project_dir / "project.json"
    if not cfg_path.is_file():
        print(f"缺少 project.json: {project_dir}", file=sys.stderr)
        return 1
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    entry = cfg.get("entry", "main.lua")
    script_path = project_dir / entry
    if not script_path.is_file():
        print(f"缺少脚本: {script_path}", file=sys.stderr)
        return 1

    def emit(line: str) -> None:
        print(line, flush=True)

    bot = PcBot(project_dir, serial=serial, on_log=emit)
    PanelState.clear_watches()
    if not PanelState.load_sidecar(project_dir):
        PanelState.seed_from_layout(load_layout(project_dir))
    lua = LuaRuntime(unpack_returned_tuples=True)
    install_bot(lua, bot)
    install_lua_logging(lua)
    code = script_path.read_text(encoding="utf-8")
    chunk = chunk_name_for(script_path)
    line_count = code.count("\n") + (1 if code else 0)
    emit(f"[lua_runner] 设备: {serial or bot.adb.default_serial() or '（无）'}")
    emit(f"[lua_runner] 脚本: {script_path} ({line_count} 行)")
    emit(f"[lua_runner] chunk: {chunk}")
    emit("[lua_runner] ----- 开始执行 -----")
    try:
        execute_lua_chunk(lua, code, chunk)
    except Exception as exc:
        emit(format_lua_error(exc, script_path=script_path))
        tb = traceback.format_exc()
        for line in tb.strip().splitlines():
            emit(line)
        emit("[lua_runner] ----- 执行失败 -----")
        return 1
    emit("[lua_runner] ----- 执行完成 -----")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PC 运行 Lua 脚本（ADB + lupa）")
    parser.add_argument("project_dir", help="含 project.json 的工程目录")
    parser.add_argument("--serial", default=None, help="ADB 设备 serial")
    args = parser.parse_args(argv)
    return run_project(Path(args.project_dir), serial=args.serial)


if __name__ == "__main__":
    raise SystemExit(main())
