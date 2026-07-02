"""APK 图标与悬浮球猫咪图处理。"""

from __future__ import annotations

import shutil
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ICON = ROOT / "images" / "jimeng.png"
GENERATED_RES = ROOT / "android-runtime" / "packager" / "generated-res"

# Android mipmap 尺寸
MIPMAP_SIZES: dict[str, int] = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

THEME_BLUE = (37, 99, 235)
LAUNCHER_BG = (37, 99, 235)


def resolve_icon_source(project_dir: Path, cfg: dict) -> Path:
    rel = (cfg.get("icon") or "").strip()
    if rel:
        for candidate in (project_dir / rel, Path(rel)):
            if candidate.is_file():
                return candidate.resolve()
    if DEFAULT_ICON.is_file():
        return DEFAULT_ICON
    raise FileNotFoundError(
        f"未找到应用图标：工程内 icon 无效，且默认图不存在 {DEFAULT_ICON}"
    )


def flood_remove_outer_white(img: Image.Image, *, threshold: int = 245) -> Image.Image:
    """仅抠掉与边缘连通的近白色背景，保留猫咪白色身体。"""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    pixels = rgba.load()
    visited = [[False] * w for _ in range(h)]

    def is_bg(x: int, y: int) -> bool:
        r, g, b, _a = pixels[x, y]
        return r >= threshold and g >= threshold and b >= threshold

    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(x, y) and not visited[x][y]:
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(x, y) and not visited[x][y]:
                q.append((x, y))

    while q:
        x, y = q.popleft()
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        if visited[x][y] or not is_bg(x, y):
            continue
        visited[x][y] = True
        r, g, b, _a = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        q.append((x + 1, y))
        q.append((x - 1, y))
        q.append((x, y + 1))
        q.append((x, y - 1))
    return rgba


def style_ball_icon(img: Image.Image) -> Image.Image:
    """悬浮球：透明底 + 主题蓝描边 + 半透明白身，尽量不挡画面。"""
    cut = flood_remove_outer_white(img)
    w, h = cut.size
    pixels = cut.load()
    tr, tg, tb = THEME_BLUE
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum < 96:
                pixels[x, y] = (tr, tg, tb, int(a * 0.92))
            elif lum < 200:
                pixels[x, y] = (210, 225, 255, int(a * 0.55))
            else:
                pixels[x, y] = (255, 255, 255, int(a * 0.42))
    return cut


def _fit_inside(canvas: int, img: Image.Image, padding: float = 0.12) -> Image.Image:
    side = int(canvas * (1 - padding * 2))
    fitted = img.copy()
    fitted.thumbnail((side, side), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ox = (canvas - fitted.width) // 2
    oy = (canvas - fitted.height) // 2
    out.paste(fitted, (ox, oy), fitted)
    return out


def make_launcher_icon(img: Image.Image, size: int) -> Image.Image:
    """桌面图标：圆角蓝底 + 居中猫咪。"""
    cut = flood_remove_outer_white(img)
    canvas = Image.new("RGBA", (size, size), LAUNCHER_BG + (255,))
    draw = ImageDraw.Draw(canvas)
    radius = max(8, size // 5)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=LAUNCHER_BG + (255,))
    mascot = _fit_inside(size, cut, padding=0.14)
    canvas.alpha_composite(mascot)
    return canvas


def prepare_pack_icons(
    project_dir: Path,
    cfg: dict,
    runtime_root: Path,
    staging_dir: Path,
) -> Path:
    """
    生成 mipmap 启动图标 + 写入 staging/ui/ball.png。
    返回实际使用的源图路径。
    """
    src = resolve_icon_source(project_dir, cfg)
    base = Image.open(src)

    gen_res = runtime_root / "packager" / "generated-res"
    if gen_res.exists():
        shutil.rmtree(gen_res)
    for density, px in MIPMAP_SIZES.items():
        folder = gen_res / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        make_launcher_icon(base, px).save(folder / "ic_launcher.png", optimize=True)

    ui_dir = staging_dir / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    ball = style_ball_icon(base)
    ball_side = 256
    ball_fitted = _fit_inside(ball_side, ball, padding=0.06)
    ball_fitted.save(ui_dir / "ball.png", optimize=True)
    return src


def default_icon_path() -> Path:
    return DEFAULT_ICON
