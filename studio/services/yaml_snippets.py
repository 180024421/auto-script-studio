"""生成可插入 main.yaml 的 action 片段。"""

from __future__ import annotations

from typing import Optional, Sequence


def _indent_yaml(lines: list[str], spaces: int = 2) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in lines)


def color_action(
    name: str,
    bgr: Sequence[int],
    *,
    tol: int = 15,
    timeout: int = 10,
    roi: Optional[Sequence[int]] = None,
) -> str:
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    lines = [
        f"{name}:",
        "  type: color",
        f"  bgr: [{b}, {g}, {r}]",
        f"  tol: {tol}",
        f"  timeout: {timeout}",
    ]
    if roi:
        lines.append(f"  roi: [{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}]")
    return _indent_yaml(lines)


def template_action(
    name: str,
    template_path: str,
    *,
    threshold: float = 0.88,
    timeout: int = 15,
    roi: Optional[Sequence[int]] = None,
) -> str:
    lines = [
        f"{name}:",
        "  type: template",
        f"  template: {template_path}",
        f"  threshold: {threshold}",
        f"  timeout: {timeout}",
    ]
    if roi:
        lines.append(f"  roi: [{roi[0]}, {roi[1]}, {roi[2]}, {roi[3]}]")
    return _indent_yaml(lines)


def text_action(
    name: str,
    target: str,
    *,
    match_mode: str = "contains",
    timeout: int = 12,
    min_confidence: float = 0.5,
) -> str:
    lines = [
        f"{name}:",
        "  type: text",
        f"  target: {target}",
        f"  match_mode: {match_mode}",
        f"  timeout: {timeout}",
        f"  min_confidence: {min_confidence}",
    ]
    return _indent_yaml(lines)


def tap_action(name: str, x: int, y: int) -> str:
    lines = [
        f"{name}:",
        "  type: tap",
        f"  x: {x}",
        f"  y: {y}",
    ]
    return _indent_yaml(lines)


def flow_ref(name: str) -> str:
    return f"    - {name}"


def inline_tap(x: int, y: int) -> str:
    return _indent_yaml(
        [
            "- type: tap",
            f"  x: {x}",
            f"  y: {y}",
        ],
        spaces=4,
    )
