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

    def recognize_text(opts=None):
        return bot.recognize_text(table_to_dict(opts))

    def yolo_detect(opts=None):
        return bot.yolo_detect(table_to_dict(opts))

    def find_yolo(opts=None):
        return _ret_point(bot.find_yolo(table_to_dict(opts)))

    def yolo_swipe(opts=None):
        bot.yolo_swipe(table_to_dict(opts))

    def log(msg):
        bot.log(str(msg))

    bot_table = lua.table_from(
        {
            "delay": delay,
            "tap": tap,
            "swipe": swipe,
            "longPress": long_press,
            "findImage": find_image,
            "findColor": find_color,
            "findText": find_text,
            "recognizeText": recognize_text,
            "yoloDetect": yolo_detect,
            "findYolo": find_yolo,
            "yoloSwipe": yolo_swipe,
            "log": log,
        }
    )
    g = lua.globals()
    g["bot"] = bot_table
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

    from studio.runtime.pc_bot import PcBot

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

    bot = PcBot(project_dir, serial=serial, on_log=lambda m: print(m, flush=True))
    lua = LuaRuntime(unpack_returned_tuples=True)
    install_bot(lua, bot)
    code = script_path.read_text(encoding="utf-8")
    print(f"[lua_runner] 运行 {script_path} @ {serial or 'default'}", flush=True)
    try:
        lua.execute(code)
    except Exception:
        traceback.print_exc()
        return 1
    print("[lua_runner] 完成", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PC 运行 Lua 脚本（ADB + lupa）")
    parser.add_argument("project_dir", help="含 project.json 的工程目录")
    parser.add_argument("--serial", default=None, help="ADB 设备 serial")
    args = parser.parse_args(argv)
    return run_project(Path(args.project_dir), serial=args.serial)


if __name__ == "__main__":
    raise SystemExit(main())
