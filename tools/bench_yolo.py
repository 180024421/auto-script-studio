#!/usr/bin/env python3
"""YOLO ONNX 推理基准测试（PC 端，对齐 APK imgsz）。

用法:
  python tools/bench_yolo.py --onnx examples/demo-game/models/ui.onnx --imgsz 320 -n 20
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np


def bench(onnx_path: Path, imgsz: int, n: int, conf: float) -> dict:
    try:
        import onnxruntime as ort  # type: ignore
    except ImportError as exc:
        raise SystemExit("请安装 onnxruntime: pip install onnxruntime") from exc

    onnx_path = onnx_path.resolve()
    if not onnx_path.is_file():
        raise FileNotFoundError(onnx_path)

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp_name = sess.get_inputs()[0].name
    dummy = np.random.rand(1, 3, imgsz, imgsz).astype(np.float32)

    for _ in range(3):
        sess.run(None, {inp_name: dummy})

    times: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        sess.run(None, {inp_name: dummy})
        times.append((time.perf_counter() - t0) * 1000)

    times.sort()
    p50 = times[len(times) // 2]
    p90 = times[int(len(times) * 0.9)]
    return {
        "onnx": str(onnx_path),
        "imgsz": imgsz,
        "runs": n,
        "conf": conf,
        "min_ms": round(min(times), 2),
        "p50_ms": round(p50, 2),
        "p90_ms": round(p90, 2),
        "max_ms": round(max(times), 2),
        "outputs": len(sess.get_outputs()),
        "hint": "APK 端另含截屏+预处理；开启 NNAPI 通常接近或优于 PC CPU。",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--onnx", type=Path, required=True)
    p.add_argument("--imgsz", type=int, default=320)
    p.add_argument("-n", type=int, default=20, help="测试轮数")
    p.add_argument("--conf", type=float, default=0.35, help="仅写入报告")
    args = p.parse_args()
    result = bench(args.onnx, args.imgsz, args.n, args.conf)
    for k, v in result.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
