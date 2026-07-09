#!/usr/bin/env python3
"""从 adb-ide 训练的 YOLO seg/detect 权重导入 auto-script-studio 工程。

adb-ide 训练产物通常为 runs/<name>/weights/best.pt（imgsz 常为 640）。
APK 端为几十毫秒级推理，建议导出 imgsz=320 的固定 shape ONNX。

用法:
  python tools/import_adb_ide_yolo.py --project examples/demo-game \\
      --pt D:/yolo/runs/my_seg/weights/best.pt --name ui-seg

  python tools/import_adb_ide_yolo.py --project examples/demo-game \\
      --run D:/yolo/runs/my_seg --imgsz 320 --preset yolo_seg_fast
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio.services.adb_ide_import import import_adb_ide_yolo  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="adb-ide YOLO → auto-script-studio ONNX")
    p.add_argument("--project", type=Path, required=True, help="auto-script 工程目录")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pt", type=Path, help="best.pt 路径")
    src.add_argument("--run", type=Path, help="Ultralytics 训练 run 目录（含 weights/best.pt）")
    p.add_argument("--name", type=str, default="", help="输出模型 stem，默认取 run 名")
    p.add_argument("--imgsz", type=int, default=320, help="移动端导出尺寸（默认 320，几十 ms 级）")
    p.add_argument("--preset", type=str, default="yolo_seg_fast", help="project.json 性能预设，空则跳过")
    p.add_argument("--no-default", action="store_true", help="不写入 default_yolo_model")
    args = p.parse_args()

    pt_or_run = args.pt or args.run
    assert pt_or_run is not None
    result = import_adb_ide_yolo(
        args.project.resolve(),
        pt_or_run,
        out_name=args.name.strip() or None,
        imgsz=args.imgsz,
        set_default=not args.no_default,
        apply_preset=args.preset.strip() or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
