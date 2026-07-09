"""从抓抓页导出 YOLO 训练样本（detect 框 / seg 多边形）。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np


def _is_seg_task(detections: Sequence[dict[str, Any]]) -> bool:
    return any(bool(d.get("has_mask")) for d in detections)


def _bbox_to_yolo_line(cid: int, x: int, y: int, w: int, h: int, iw: int, ih: int) -> str:
    cx = (x + w / 2) / iw
    cy = (y + h / 2) / ih
    nw = w / iw
    nh = h / ih
    return f"{cid} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}"


def _mask_bbox_to_seg_polygon(
    cid: int,
    x: int,
    y: int,
    w: int,
    h: int,
    iw: int,
    ih: int,
    *,
    mask_center_x: int | None = None,
    mask_center_y: int | None = None,
) -> str:
    """无完整多边形时用掩码质心周围矩形四角近似 seg 标注。"""
    if mask_center_x is not None and mask_center_y is not None:
        cx, cy = mask_center_x, mask_center_y
        hw = max(4, w // 4)
        hh = max(4, h // 4)
        x1 = max(0, cx - hw)
        y1 = max(0, cy - hh)
        x2 = min(iw - 1, cx + hw)
        y2 = min(ih - 1, cy + hh)
    else:
        x1, y1, x2, y2 = x, y, x + w, y + h
    pts = [
        (x1 / iw, y1 / ih),
        (x2 / iw, y1 / ih),
        (x2 / iw, y2 / ih),
        (x1 / iw, y2 / ih),
    ]
    coords = " ".join(f"{px:.6f} {py:.6f}" for px, py in pts)
    return f"{cid} {coords}"


def export_yolo_sample(
    project_dir: Path,
    image_bgr: np.ndarray,
    detections: Sequence[dict[str, Any]],
    *,
    subdir: str = "dataset",
    class_names: Sequence[str] | None = None,
    force_seg: bool | None = None,
) -> Path:
    """保存 PNG + YOLO detect txt 或 seg 多边形 txt。"""
    h, w = image_bgr.shape[:2]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    root = project_dir / subdir / "images"
    lbl_root = project_dir / subdir / "labels"
    root.mkdir(parents=True, exist_ok=True)
    lbl_root.mkdir(parents=True, exist_ok=True)
    stem = f"grab_{stamp}"
    img_path = root / f"{stem}.png"
    cv2.imwrite(str(img_path), image_bgr)
    names = list(class_names or [])
    name_to_id = {n: i for i, n in enumerate(names)}
    seg_mode = force_seg if force_seg is not None else _is_seg_task(detections)
    lines: list[str] = []
    for det in detections:
        cls = str(det.get("class_name") or "")
        if cls not in name_to_id:
            name_to_id[cls] = len(name_to_id)
            names.append(cls)
        cid = name_to_id[cls]
        x = int(det.get("x", 0))
        y = int(det.get("y", 0))
        bw = int(det.get("w", 0))
        bh = int(det.get("h", 0))
        if bw <= 0 or bh <= 0:
            continue
        if seg_mode and det.get("has_mask"):
            lines.append(
                _mask_bbox_to_seg_polygon(
                    cid,
                    x,
                    y,
                    bw,
                    bh,
                    w,
                    h,
                    mask_center_x=int(det["mask_center_x"]) if det.get("mask_center_x") is not None else None,
                    mask_center_y=int(det["mask_center_y"]) if det.get("mask_center_y") is not None else None,
                )
            )
        else:
            lines.append(_bbox_to_yolo_line(cid, x, y, bw, bh, w, h))
    (lbl_root / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    meta = {
        "image": str(img_path.relative_to(project_dir)).replace("\\", "/"),
        "labels": str((lbl_root / f"{stem}.txt").relative_to(project_dir)).replace("\\", "/"),
        "class_names": names,
        "count": len(lines),
        "task": "segment" if seg_mode else "detect",
    }
    (project_dir / subdir / f"{stem}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return img_path
