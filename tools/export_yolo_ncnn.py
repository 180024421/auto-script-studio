#!/usr/bin/env python3
"""从 Ultralytics YOLO .pt 导出 NCNN 模型，供 APK 运行时加载。

依赖（PC 端）:
  pip install ultralytics

用法:
  python tools/export_yolo_ncnn.py --pt path/to/best.pt --out examples/demo-game/models/ui
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def export(pt: Path, out_prefix: Path, imgsz: int, half: bool) -> None:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("请先安装 ultralytics: pip install ultralytics") from exc

    pt = pt.resolve()
    if not pt.is_file():
        raise FileNotFoundError(pt)

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(pt))
    exported = model.export(format="ncnn", imgsz=imgsz, half=half)
    exported_path = Path(exported)
    # ultralytics 导出目录形如 ui_ncnn_model/
    if exported_path.is_dir():
        param_files = list(exported_path.glob("*.param"))
        bin_files = list(exported_path.glob("*.bin"))
        if not param_files or not bin_files:
            raise RuntimeError(f"NCNN 导出目录缺少 param/bin: {exported_path}")
        shutil.copy2(param_files[0], out_prefix.with_suffix(".ncnn.param"))
        shutil.copy2(bin_files[0], out_prefix.with_suffix(".ncnn.bin"))
    else:
        shutil.copy2(exported_path, out_prefix)
    print(f"已导出到 {out_prefix}.ncnn.param / .bin")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pt", type=Path, required=True, help="YOLO .pt 权重")
    p.add_argument("--out", type=Path, required=True, help="输出前缀（不含扩展名）")
    p.add_argument("--imgsz", type=int, default=320)
    p.add_argument("--half", action="store_true", help="FP16")
    args = p.parse_args()
    export(args.pt, args.out, args.imgsz, args.half)
    return 0


if __name__ == "__main__":
    sys.exit(main())
