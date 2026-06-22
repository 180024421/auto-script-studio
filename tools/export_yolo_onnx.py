#!/usr/bin/env python3
"""从 Ultralytics YOLO .pt 导出 ONNX + labels，供 APK 运行时加载。

用法:
  python tools/export_yolo_onnx.py --pt path/to/best.pt --out examples/demo-game/models/ui
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def export(pt: Path, out_prefix: Path, imgsz: int) -> None:
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("请先安装 ultralytics: pip install ultralytics") from exc

    pt = pt.resolve()
    if not pt.is_file():
        raise FileNotFoundError(pt)

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(pt))
    onnx_path = model.export(format="onnx", imgsz=imgsz, simplify=True, opset=12)
    onnx_src = Path(onnx_path)
    onnx_dst = out_prefix.with_suffix(".onnx")
    shutil.copy2(onnx_src, onnx_dst)

    names = model.names or {}
    labels_dst = out_prefix.with_suffix(".labels")
    lines = [str(names[i]) for i in sorted(names.keys())]
    labels_dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已导出: {onnx_dst}")
    print(f"标签文件: {labels_dst}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pt", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="输出前缀（不含扩展名）")
    p.add_argument("--imgsz", type=int, default=320)
    args = p.parse_args()
    export(args.pt, args.out, args.imgsz)
    return 0


if __name__ == "__main__":
    sys.exit(main())
