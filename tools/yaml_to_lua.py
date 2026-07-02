"""YAML actions 转 Lua 片段（迁移旧 YAML 工程用）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def action_to_lua(action: dict) -> str:
    kind = str(action.get("type", "")).lower()
    if kind == "tap":
        return f"bot.tap({action.get('x', 0)}, {action.get('y', 0)})"
    if kind == "swipe":
        return (
            f"bot.swipe({action.get('x1', 0)}, {action.get('y1', 0)}, "
            f"{action.get('x2', 0)}, {action.get('y2', 0)}, {action.get('duration_ms', 300)})"
        )
    if kind == "human_delay":
        lo = action.get("min", action.get("seconds", 1))
        hi = action.get("max", lo)
        return f"bot.delay(({lo} + {hi}) / 2)"
    if kind == "template":
        path = action.get("path", action.get("template", "image/tpl.png"))
        opts = {
            "threshold": action.get("threshold", 0.9),
            "timeout": action.get("timeout", 20),
            "click": action.get("click", False),
            "optional": action.get("optional", False),
        }
        opts_s = ", ".join(f"{k} = {v!r}" if isinstance(v, str) else f"{k} = {v}" for k, v in opts.items())
        return f"local x, y = bot.findImage({path!r}, {{ {opts_s} }})"
    if kind == "color":
        bgr = action.get("bgr", [0, 0, 0])
        opts = {
            "tol": action.get("tol", 12),
            "timeout": action.get("timeout", 15),
            "click": action.get("click", False),
        }
        opts_s = ", ".join(f"{k} = {v}" for k, v in opts.items())
        return f"bot.findColor({bgr[0]}, {bgr[1]}, {bgr[2]}, {{ {opts_s} }})"
    if kind == "text":
        target = action.get("text", "")
        opts = {
            "timeout": action.get("timeout", 20),
            "click": action.get("click", False),
            "match_mode": action.get("match_mode", "contains"),
        }
        opts_s = ", ".join(f"{k} = {v!r}" if isinstance(v, str) else f"{k} = {v}" for k, v in opts.items())
        return f"bot.findText({target!r}, {{ {opts_s} }})"
    if kind == "yolo":
        opts = {k: v for k, v in action.items() if k != "type"}
        opts_s = ", ".join(
            f"{k} = {v!r}" if isinstance(v, str) else f"{k} = {v}" for k, v in opts.items()
        )
        return f"bot.findYolo({{ {opts_s} }})"
    return f"-- 未转换: {kind} {action}"


def convert_yaml_file(path: Path) -> str:
    if yaml is None:
        raise RuntimeError("需要 PyYAML: pip install pyyaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    lines = ["-- 由 tools/yaml_to_lua.py 自动生成", "bot.log('脚本开始')", ""]
    flows = data.get("flows", {})
    main_steps = flows.get("main", data.get("actions", []))
    if isinstance(main_steps, list):
        for step in main_steps:
            if isinstance(step, dict):
                lines.append(action_to_lua(step))
    lines.append("")
    lines.append("bot.log('脚本完成')")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YAML actions → main.lua")
    parser.add_argument("yaml", type=Path, help="game.yaml 或 main.yaml")
    parser.add_argument("-o", "--output", type=Path, help="输出 main.lua，默认同目录")
    args = parser.parse_args(argv)
    out = args.output or args.yaml.parent / "main.lua"
    lua = convert_yaml_file(args.yaml)
    out.write_text(lua, encoding="utf-8")
    print(f"已写入: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
