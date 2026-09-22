"""在 PC 上通过 lupa 运行工程 main.lua（ADB + vision_pc）。

`bot.*` / `panel.*` 的注册、参数强转与返回 marshal 全部由 `contract/lua_api.json` 驱动
（读契约与 marshal 在 `studio.runtime.lua_contract`）。本文件不再手写函数名表、
返回形状，也不再为设备专有名字逐个写报错桩 —— 那些信息都在契约里。
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ensure_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


# 未知 opts 键只告警一次：同一脚本循环调用不该刷屏（设备端同样静默忽略）。
_WARNED_OPTS: set[tuple[str, str]] = set()
# panel.watch 的 Lua 回调身份表：widget_id -> {tostring(fn): 已注册的 Python 包装}
_CALLBACKS: dict[str, dict[str, Callable[[str], None]]] = {}


def _lua_fn_identity(lua, fn) -> str:
    """lupa 每次把同一个 Lua 函数交回来都是不同代理对象，只能用 tostring 认身份。"""
    return str(lua.globals()["tostring"](fn))


def _warn_unknown_opt(log: Callable[[str], None], entry, key: str) -> None:
    if (entry.name, key) in _WARNED_OPTS:
        return
    _WARNED_OPTS.add((entry.name, key))
    declared = {o.key for o in entry.opts}
    why = "契约未声明该键" if key not in declared else "该键仅设备端生效"
    log(f"[contract] {entry.name} 忽略未知 opts.{key}（{why}）")


def _make_missing_stub(entry):
    """契约里 pc_missing=raise 的设备专有名字：注册但调用即中文报错。"""

    message = entry.pc_error or f"{entry.name} 仅 APK 可用（PC 联调不支持）"

    def _fn(*_args):
        raise RuntimeError(message)

    return _fn


def _make_binding(lua, host, entry, log: Callable[[str], None], to_opts: Callable[[object], dict]):
    """按契约条目生成一个 Lua 可调用对象：强转入参 → 调 PC 方法 → marshal 返回。"""
    from studio.runtime.lua_contract import coerce, marshal

    method = getattr(host, entry.pc, None)
    if method is None or not callable(method):

        def _unwired(*_args):
            host_name = host.__name__ if isinstance(host, type) else type(host).__name__
            raise RuntimeError(f"{entry.name} 需要 Studio 实现 {host_name}.{entry.pc}")

        return _unwired

    arg_specs = tuple(entry.args)
    opts_at = entry.opts_index
    legal = set(entry.side_opts("pc"))

    def _call(*args):
        positional: list = []
        for i, spec in enumerate(arg_specs):
            if i >= len(args):
                if spec.name == "opts":
                    # opts 表在两端都可省略（设备端读不到即为空表）
                    positional.append({})
                    continue
                if spec.optional:
                    break
                raise RuntimeError(f"{entry.name} 缺少第 {i + 1} 个参数 {spec.name}")
            value = args[i]
            if i == opts_at:
                opts = to_opts(value)
                for key in sorted(opts):
                    if key not in legal:
                        _warn_unknown_opt(log, entry, str(key))
                positional.append(opts)
            elif value is None and spec.optional:
                break
            else:
                positional.append(coerce(value, spec.type))
        result = method(*positional)
        return marshal(lua, result, entry.returns)

    return _call


def install_bot(lua, bot) -> None:
    """把契约里 availability 含 pc 的名字注册成 Lua 全局 bot / panel 表。"""
    from studio.runtime.lua_contract import load
    from studio.runtime.lua_values import table_to_dict
    from studio.runtime.panel_state import PanelState

    entries = load()
    g = lua.globals()

    def _log(msg) -> None:
        bot.log(str(msg))

    def _build(table_name: str, host, overrides: dict[str, Callable]) -> dict:
        members = dict(overrides)
        for name, entry in sorted(entries.items()):
            if entry.table != table_name or entry.lua_name in overrides:
                continue
            if entry.on_pc:
                members[entry.lua_name] = _make_binding(lua, host, entry, _log, table_to_dict)
            elif entry.pc_missing == "raise":
                # pc_missing=nil 的名字不注册：保留 `if bot.runSaocheng then` 的降级惯例
                members[entry.lua_name] = _make_missing_stub(entry)
        missing = set(overrides) - {e.lua_name for e in entries.values() if e.table == table_name}
        if missing:
            raise RuntimeError(f"契约里没有这些名字，override 表已失效：{sorted(missing)}")
        return members

    bot_table = lua.table_from(_build("bot", bot, {}))
    g["bot"] = bot_table

    def _panel_watch(widget_id, fn):
        wid = str(widget_id)
        key = _lua_fn_identity(lua, fn)
        registered = _CALLBACKS.setdefault(wid, {})
        if key in registered:
            return

        def _callback(value):
            fn(value)

        registered[key] = _callback
        PanelState.watch(wid, _callback)

    def _panel_unwatch(widget_id, fn=None):
        wid = str(widget_id)
        if fn is None:
            _CALLBACKS.pop(wid, None)
            PanelState.unwatch(wid)
            return
        callback = _CALLBACKS.get(wid, {}).pop(_lua_fn_identity(lua, fn), None)
        if callback is None:
            return
        PanelState.unwatch(wid, callback)

    g["panel"] = lua.table_from(
        _build(
            "panel",
            PanelState,
            {"watch": _panel_watch, "unwatch": _panel_unwatch},
        )
    )

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
    from studio.runtime.panel_state import PanelState
    from studio.runtime.pc_bot import PcBot
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
    _CALLBACKS.clear()
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
