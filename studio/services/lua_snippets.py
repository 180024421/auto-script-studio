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
    scale_min: float = 1.0,
    scale_max: float = 1.0,
    scale_step: float = 0.1,
) -> str:
    opts: list[str] = [f"threshold = {threshold}", f"timeout = {timeout}"]
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    if abs(scale_min - 1.0) > 0.001 or abs(scale_max - 1.0) > 0.001:
        opts.append(f"scale_min = {scale_min}")
        opts.append(f"scale_max = {scale_max}")
        opts.append(f"scale_step = {scale_step}")
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
    roi: Optional[Sequence[int]] = None,
    click: bool = False,
) -> str:
    safe = target.replace("\\", "\\\\").replace('"', '\\"')
    opts: list[str] = [
        f'match_mode = "{match_mode}"',
        f"timeout = {timeout}",
        f"min_confidence = {min_confidence}",
    ]
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    if click:
        opts.append("click = true")
    ol = _opts_literal(opts)
    return (
        f'local tx, ty = bot.findText("{safe}", {ol})\n'
        f"if tx then\n"
        f'  bot.log(string.format("识字命中 (%d,%d)", tx, ty))\n'
        f"end"
    )


def _yolo_opts_parts(
    model: str,
    *,
    class_name: str = "",
    conf: float = 0.35,
    timeout: float = 20.0,
    pick: str = "best_conf",
    roi: Optional[Sequence[int]] = None,
    frac: Optional[tuple[float, float]] = None,
    optional: bool = False,
    use_mask_center: bool = False,
) -> list[str]:
    safe_model = model.replace("\\", "\\\\").replace('"', '\\"')
    opts: list[str] = [
        f'model = "{safe_model}"',
        f"conf = {conf}",
        f"timeout = {timeout}",
        f'pick = "{pick}"',
    ]
    if class_name:
        safe_cls = class_name.replace("\\", "\\\\").replace('"', '\\"')
        opts.append(f'class_name = "{safe_cls}"')
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    if frac is not None:
        opts.append(f"frac = {{{frac[0]}, {frac[1]}}}")
    if optional:
        opts.append("optional = true")
    if use_mask_center:
        opts.append("use_mask_center = true")
    return opts


def yolo_detect(
    model: str,
    *,
    class_name: str = "",
    conf: float = 0.35,
    roi: Optional[Sequence[int]] = None,
    limit: int = 20,
) -> str:
    opts = _yolo_opts_parts(model, class_name=class_name, conf=conf, roi=roi)
    if limit != 20:
        opts.append(f"limit = {int(limit)}")
    ol = _opts_literal(opts)
    return (
        f"local dets = bot.yoloDetect({ol})\n"
        f"for i, d in ipairs(dets) do\n"
        f'  bot.log(string.format("[%d] %s %.2f @ (%d,%d)", i, d.class_name, d.confidence, d.center_x, d.center_y))\n'
        f"end"
    )


def find_node(
    *,
    text: str = "",
    resource_id: str = "",
    match_mode: str = "contains",
    timeout: float = 10,
    index: int = 0,
    click: bool = False,
    optional: bool = False,
) -> str:
    if not text.strip() and not resource_id.strip():
        text = "设置"
    opts: list[str] = [f"timeout = {timeout}", f"index = {index}"]
    if text.strip():
        safe = text.replace("\\", "\\\\").replace('"', '\\"')
        opts.append(f'text = "{safe}"')
    if resource_id.strip():
        safe_id = resource_id.replace("\\", "\\\\").replace('"', '\\"')
        opts.append(f'id = "{safe_id}"')
    if match_mode and text.strip():
        opts.append(f'match_mode = "{match_mode}"')
    if click:
        opts.append("click = true")
    if optional:
        opts.append("optional = true")
    ol = _opts_literal(opts)
    return (
        f"local nx, ny = bot.findNode({ol})\n"
        f"if nx then\n"
        f'  bot.log(string.format("控件命中 (%d,%d)", nx, ny))\n'
        f"end"
    )


def find_yolo(
    model: str,
    *,
    class_name: str = "",
    conf: float = 0.35,
    timeout: float = 20.0,
    pick: str = "best_conf",
    roi: Optional[Sequence[int]] = None,
    frac: tuple[float, float] = (0.5, 0.5),
    tap_dx: int = 0,
    tap_dy: int = 0,
    delay_before_click: float = 0.0,
    click: bool = False,
    optional: bool = False,
    use_mask_center: bool = False,
) -> str:
    use_inline_click = click and tap_dx == 0 and tap_dy == 0 and delay_before_click <= 0
    opts = _yolo_opts_parts(
        model,
        class_name=class_name,
        conf=conf,
        timeout=timeout,
        pick=pick,
        roi=roi,
        frac=frac,
        optional=optional,
        use_mask_center=use_mask_center,
    )
    if use_inline_click:
        opts.append("click = true")
    ol = _opts_literal(opts)
    lines = [
        f"local yx, yy = bot.findYolo({ol})",
        "if yx then",
        '  bot.log(string.format("YOLO 命中 (%d,%d)", yx, yy))',
    ]
    if click and not use_inline_click:
        if delay_before_click > 0:
            lines.append(f"  bot.delay({delay_before_click})")
        tx = f"yx + {tap_dx}" if tap_dx else "yx"
        ty = f"yy + {tap_dy}" if tap_dy else "yy"
        lines.append(f"  bot.tap({tx}, {ty})")
    lines.append("end")
    return "\n".join(lines)


def yolo_swipe(
    model: str,
    *,
    class_name: str = "",
    conf: float = 0.35,
    timeout: float = 20.0,
    pick: str = "best_conf",
    roi: Optional[Sequence[int]] = None,
    frac: tuple[float, float] = (0.5, 0.5),
    direction: str = "up",
    distance: int = 400,
    duration_ms: int = 350,
    use_mask_center: bool = False,
) -> str:
    opts = _yolo_opts_parts(
        model,
        class_name=class_name,
        conf=conf,
        timeout=timeout,
        pick=pick,
        roi=roi,
        frac=frac,
        use_mask_center=use_mask_center,
    )
    opts.append(f'direction = "{direction}"')
    opts.append(f"distance = {int(distance)}")
    opts.append(f"duration_ms = {int(duration_ms)}")
    return f"bot.yoloSwipe({_opts_literal(opts)})"


def find_multi_color(
    points: Sequence[tuple[int, int, Sequence[int]]],
    *,
    tol: int = 15,
    timeout: float = 10,
    roi: Optional[Sequence[int]] = None,
    click: bool = False,
) -> str:
    """points: (dx, dy, (b,g,r)) 相对锚点偏移。"""
    pt_lines = []
    for dx, dy, bgr in points:
        b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
        pt_lines.append(f"    {{{dx}, {dy}, {{{b}, {g}, {r}}}}},")
    pts_block = "{\n" + "\n".join(pt_lines) + "\n  }"
    opts: list[str] = [f"points = {pts_block}", f"tol = {tol}", f"timeout = {timeout}"]
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    if click:
        opts.append("click = true")
    return (
        f"local mx, my = bot.findMultiColor({_opts_literal(opts)})\n"
        f"if mx then bot.log(string.format('多点找色 (%d,%d)', mx, my)) end"
    )


def wait_gone_image(
    template_path: str,
    *,
    threshold: float = 0.9,
    timeout: float = 30,
    roi: Optional[Sequence[int]] = None,
) -> str:
    opts: list[str] = [f"threshold = {threshold}", f"timeout = {timeout}"]
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    return f'bot.waitGoneImage("{template_path}", {_opts_literal(opts)})'


def wait_stable(
    *,
    timeout: float = 15,
    stable_frames: int = 3,
    diff_threshold: float = 8,
    roi: Optional[Sequence[int]] = None,
) -> str:
    opts: list[str] = [
        f"timeout = {timeout}",
        f"stable_frames = {stable_frames}",
        f"diff_threshold = {diff_threshold}",
    ]
    if roi:
        opts.append(f"roi = {{{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}}}")
    return f"bot.waitStable({_opts_literal(opts)})"


def tap(x: int, y: int) -> str:
    return f"bot.tap({int(x)}, {int(y)})"


def delay(seconds: float) -> str:
    return f"bot.delay({seconds})"


def swipe(x1: int, y1: int, x2: int, y2: int, *, duration_ms: int = 300) -> str:
    return f"bot.swipe({int(x1)}, {int(y1)}, {int(x2)}, {int(y2)}, {int(duration_ms)})"


def long_press(x: int, y: int, *, duration_ms: int = 500) -> str:
    return f"bot.longPress({int(x)}, {int(y)}, {int(duration_ms)})"


def log_message(msg: str) -> str:
    safe = msg.replace("\\", "\\\\").replace('"', '\\"')
    return f'bot.log("{safe}")'
