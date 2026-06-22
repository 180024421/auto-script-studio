"""生成可插入 main.lua 的 bot API 片段。"""

from __future__ import annotations

from typing import Optional, Sequence


def _opts_literal(parts: list[str]) -> str:
    if not parts:
        return "{}"
    return "{ " + ", ".join(parts) + " }"


def find_color(
    bgr: Sequence[int],
    *,
    tol: int = 15,
    timeout: float = 10,
    roi: Optional[Sequence[int]] = None,
    click: bool = False,
) -> str:
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    opts: list[str] = [f"tol = {tol}", f"timeout = {timeout}"]
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    if click:
        opts.append("click = true")
    return f"bot.findColor({b}, {g}, {r}, {_opts_literal(opts)})"


def find_image(
    template_path: str,
    *,
    threshold: float = 0.88,
    timeout: float = 15,
    roi: Optional[Sequence[int]] = None,
    click: bool = False,
) -> str:
    opts: list[str] = [f"threshold = {threshold}", f"timeout = {timeout}"]
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    if click:
        opts.append("click = true")
    ol = _opts_literal(opts)
    return (
        f'local x, y = bot.findImage("{template_path}", {ol})\n'
        f"if x then\n"
        f'  bot.log(string.format("找图命中 (%d,%d)", x, y))\n'
        f"end"
    )


def find_text(
    target: str,
    *,
    match_mode: str = "contains",
    timeout: float = 12,
    min_confidence: float = 0.5,
    click: bool = False,
) -> str:
    safe = target.replace("\\", "\\\\").replace('"', '\\"')
    opts: list[str] = [
        f'match_mode = "{match_mode}"',
        f"timeout = {timeout}",
        f"min_confidence = {min_confidence}",
    ]
    if click:
        opts.append("click = true")
    ol = _opts_literal(opts)
    return (
        f'local tx, ty = bot.findText("{safe}", {ol})\n'
        f"if tx then\n"
        f'  bot.log(string.format("识字命中 (%d,%d)", tx, ty))\n'
        f"end"
    )


def find_yolo(
    model: str,
    *,
    class_name: str = "",
    conf: float = 0.35,
    timeout: float = 20,
    pick: str = "best_conf",
    click: bool = False,
) -> str:
    opts: list[str] = [
        f'model = "{model}"',
        f"conf = {conf}",
        f"timeout = {timeout}",
        f'pick = "{pick}"',
    ]
    if class_name:
        opts.append(f'class_name = "{class_name}"')
    if click:
        opts.append("click = true")
    ol = _opts_literal(opts)
    return (
        f"local yx, yy = bot.findYolo({ol})\n"
        f"if yx then\n"
        f'  bot.log(string.format("YOLO 命中 (%d,%d)", yx, yy))\n'
        f"end"
    )


def tap(x: int, y: int) -> str:
    return f"bot.tap({int(x)}, {int(y)})"


def delay(seconds: float) -> str:
    return f"bot.delay({seconds})"
