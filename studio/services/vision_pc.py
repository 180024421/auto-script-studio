"""PC 端视觉能力（与 APK 运行时语义对齐，用于抓抓调试）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from studio.services.yolo_models import normalize_detections


@dataclass
class MatchResult:
    center_x: int
    center_y: int
    score: float
    x: int
    y: int
    w: int
    h: int


@dataclass
class TextHit:
    text: str
    center_x: int
    center_y: int
    confidence: float
    x: int = 0
    y: int = 0
    width: int = 40
    height: int = 20


def decode_png(png_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("无法解码截图 PNG")
    return img


def imread_bgr(path: str | Path) -> Optional[np.ndarray]:
    """读取 BGR 图（支持中文路径，避免 cv2.imread 失败）。"""
    p = Path(path)
    if not p.is_file():
        return None
    data = np.fromfile(p, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def find_color(
    bgr: np.ndarray,
    target_bgr: Tuple[int, int, int],
    tol: int = 12,
    roi: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[int, int]]:
    x1, y1, x2, y2 = _roi_bounds(bgr, roi)
    crop = bgr[y1:y2, x1:x2]
    tb, tg, tr = target_bgr
    diff = np.abs(crop.astype(np.int16) - np.array([tb, tg, tr], dtype=np.int16))
    mask = (diff[:, :, 0] <= tol) & (diff[:, :, 1] <= tol) & (diff[:, :, 2] <= tol)
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(x1 + xs[0]), int(y1 + ys[0])


def match_template(
    screen_bgr: np.ndarray,
    template_bgr: np.ndarray,
    threshold: float = 0.9,
    roi: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[MatchResult]:
    x1, y1, x2, y2 = _roi_bounds(screen_bgr, roi)
    source = screen_bgr[y1:y2, x1:x2]
    th, tw = template_bgr.shape[:2]
    if tw > source.shape[1] or th > source.shape[0]:
        return None
    result = cv2.matchTemplate(source, template_bgr, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val < threshold:
        return None
    tx, ty = max_loc
    return MatchResult(
        center_x=x1 + tx + tw // 2,
        center_y=y1 + ty + th // 2,
        score=float(max_val),
        x=x1 + tx,
        y=y1 + ty,
        w=tw,
        h=th,
    )


def recognize_text(
    bgr: np.ndarray,
    roi: Optional[Tuple[int, int, int, int]] = None,
    min_confidence: float = 0.5,
) -> List[TextHit]:
    x1, y1, x2, y2 = _roi_bounds(bgr, roi)
    crop = bgr[y1:y2, x1:x2]
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError as exc:
        raise RuntimeError("识字需要 PaddleOCR：pip install paddleocr paddlepaddle") from exc

    ocr = getattr(recognize_text, "_ocr", None)
    if ocr is None:
        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        recognize_text._ocr = ocr  # type: ignore[attr-defined]

    raw = ocr.ocr(crop, cls=True)
    hits: List[TextHit] = []
    for block in raw or []:
        for item in block or []:
            box, (text, conf) = item
            if conf < min_confidence:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            bw = max(1, int(x_max - x_min))
            bh = max(1, int(y_max - y_min))
            cx = int((x_min + x_max) / 2) + x1
            cy = int((y_min + y_max) / 2) + y1
            hits.append(
                TextHit(
                    text=str(text),
                    center_x=cx,
                    center_y=cy,
                    confidence=float(conf),
                    x=int(x_min) + x1,
                    y=int(y_min) + y1,
                    width=bw,
                    height=bh,
                )
            )
    return hits


def filter_text_hits(
    hits: List[TextHit],
    target: str,
    *,
    match_mode: str = "contains",
) -> List[TextHit]:
    needle = target.strip()
    if not needle:
        return hits
    out: List[TextHit] = []
    for h in hits:
        if match_mode == "exact":
            if h.text == needle:
                out.append(h)
        elif needle in h.text:
            out.append(h)
    return out


def find_text(
    bgr: np.ndarray,
    target: str,
    *,
    match_mode: str = "contains",
    roi: Optional[Tuple[int, int, int, int]] = None,
    min_confidence: float = 0.5,
) -> List[TextHit]:
    hits = recognize_text(bgr, roi=roi, min_confidence=min_confidence)
    return filter_text_hits(hits, target, match_mode=match_mode)


def yolo_detect(
    bgr: np.ndarray,
    model_path: str,
    conf: float = 0.35,
    class_name: str = "",
    roi: Optional[Tuple[int, int, int, int]] = None,
) -> List[dict]:
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("YOLO 需要 ultralytics：pip install ultralytics") from exc

    x1, y1, x2, y2 = _roi_bounds(bgr, roi)
    crop = bgr[y1:y2, x1:x2]
    model = getattr(yolo_detect, "_cache", {}).get(model_path)
    if model is None:
        model = YOLO(model_path)
        cache = getattr(yolo_detect, "_cache", {})
        cache[model_path] = model
        yolo_detect._cache = cache  # type: ignore[attr-defined]

    results = model.predict(crop, conf=conf, verbose=False)
    out: List[dict] = []
    for r in results:
        names = r.names or {}
        for box in r.boxes or []:
            cls_id = int(box.cls[0])
            name = str(names.get(cls_id, cls_id))
            if class_name and class_name not in name:
                continue
            xyxy = box.xyxy[0].tolist()
            bx1, by1, bx2, by2 = [int(v) for v in xyxy]
            out.append(
                {
                    "class_name": name,
                    "confidence": float(box.conf[0]),
                    "x": bx1 + x1,
                    "y": by1 + y1,
                    "w": bx2 - bx1,
                    "h": by2 - by1,
                    "center_x": (bx1 + bx2) // 2 + x1,
                    "center_y": (by1 + by2) // 2 + y1,
                }
            )
    return normalize_detections(out)


def _roi_bounds(img: np.ndarray, roi: Optional[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
    h, w = img.shape[:2]
    if roi is None:
        return 0, 0, w, h
    x, y, rw, rh = roi
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(w, x + rw)
    y2 = min(h, y + rh)
    return x1, y1, x2, y2
