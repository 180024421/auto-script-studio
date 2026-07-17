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


def find_multi_point_color(
    bgr: np.ndarray,
    points: list[tuple[int, int, tuple[int, int, int]]],
    tol: int = 12,
    roi: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[int, int]]:
    x1, y1, x2, y2 = _roi_bounds(bgr, roi)
    for y in range(y1, y2):
        for x in range(x1, x2):
            ok = True
            for dx, dy, (tb, tg, tr) in points:
                sx, sy = x + dx, y + dy
                if sx < 0 or sy < 0 or sx >= bgr.shape[1] or sy >= bgr.shape[0]:
                    ok = False
                    break
                b, g, r = [int(v) for v in bgr[sy, sx]]
                if abs(b - tb) > tol or abs(g - tg) > tol or abs(r - tr) > tol:
                    ok = False
                    break
            if ok:
                return x, y
    return None


def match_template(
    screen_bgr: np.ndarray,
    template_bgr: np.ndarray,
    threshold: float = 0.9,
    roi: Optional[Tuple[int, int, int, int]] = None,
    scale_min: float = 1.0,
    scale_max: float = 1.0,
    scale_step: float = 0.1,
) -> Optional[MatchResult]:
    scales = _scale_list(scale_min, scale_max, scale_step)
    best: MatchResult | None = None
    for scale in scales:
        tpl = template_bgr
        if abs(scale - 1.0) > 0.01:
            nh = max(1, int(template_bgr.shape[0] * scale))
            nw = max(1, int(template_bgr.shape[1] * scale))
            tpl = cv2.resize(template_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
        m = _match_template_single(screen_bgr, tpl, threshold, roi)
        if m is not None and (best is None or m.score > best.score):
            best = m
    return best


def _scale_list(min_s: float, max_s: float, step: float) -> list[float]:
    lo = max(0.5, min(min_s, max_s))
    hi = min(2.0, max(min_s, max_s))
    st = max(0.05, step)
    if hi - lo < 0.01:
        return [lo]
    out: list[float] = []
    s = lo
    while s <= hi + 1e-6:
        out.append(round(s, 2))
        s += st
    return out or [1.0]


def _match_template_single(
    screen_bgr: np.ndarray,
    template_bgr: np.ndarray,
    threshold: float,
    roi: Optional[Tuple[int, int, int, int]],
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
        masks = r.masks
        for i, box in enumerate(r.boxes or []):
            cls_id = int(box.cls[0])
            name = str(names.get(cls_id, cls_id))
            if class_name and class_name not in name:
                continue
            xyxy = box.xyxy[0].tolist()
            bx1, by1, bx2, by2 = [int(v) for v in xyxy]
            item: dict = {
                "class_name": name,
                "confidence": float(box.conf[0]),
                "x": bx1 + x1,
                "y": by1 + y1,
                "w": bx2 - bx1,
                "h": by2 - by1,
                "center_x": (bx1 + bx2) // 2 + x1,
                "center_y": (by1 + by2) // 2 + y1,
                "has_mask": False,
            }
            if masks is not None:
                try:
                    xy = masks.xy[i]
                    if xy is not None and len(xy) > 0:
                        pts = np.asarray(xy, dtype=np.float32)
                        item["has_mask"] = True
                        item["mask_center_x"] = int(pts[:, 0].mean()) + x1
                        item["mask_center_y"] = int(pts[:, 1].mean()) + y1
                        if masks.data is not None and i < len(masks.data):
                            mask = masks.data[i].detach().cpu().numpy()
                            item["mask_area"] = int((mask > 0.5).sum())
                        else:
                            item["mask_area"] = 0
                except (IndexError, TypeError, ValueError):
                    pass
            out.append(item)
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


def recognize_digits(
    bgr: np.ndarray,
    model_path: str,
    *,
    roi: Optional[Tuple[int, int, int, int]] = None,
    min_confidence: float = 0.5,
    max_gap: int = 3,
) -> dict:
    """游戏 HUD 数字 ONNX（与 APK DigitRecognizer / game-digit-trainer 契约一致）。"""
    try:
        import onnxruntime as ort  # type: ignore
    except ImportError as exc:
        raise RuntimeError("recognizeDigits 需要 onnxruntime：pip install onnxruntime") from exc

    x1, y1, x2, y2 = _roi_bounds(bgr, roi)
    crop = bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return {"text": "", "confidence": 0.0, "chars": []}

    onnx_p = Path(model_path)
    if onnx_p.suffix.lower() != ".onnx":
        cand = Path(str(model_path) + ".onnx")
        onnx_p = cand if cand.is_file() else onnx_p
    if not onnx_p.is_file():
        raise FileNotFoundError(f"数字模型不存在: {model_path}")

    labels_p = onnx_p.with_suffix(".labels")
    if labels_p.is_file():
        labels = [ln.strip() for ln in labels_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    else:
        labels = [str(i) for i in range(10)]

    manifest = {"width": 32, "height": 32, "invert": False, "binarize": "otsu"}
    for mp in (onnx_p.with_name("manifest.json"), onnx_p.with_suffix(".manifest.json")):
        if mp.is_file():
            import json

            data = json.loads(mp.read_text(encoding="utf-8"))
            inp = data.get("input") or {}
            prep = data.get("preprocess") or {}
            manifest["width"] = int(inp.get("width") or data.get("input_width") or 32)
            manifest["height"] = int(inp.get("height") or data.get("input_height") or 32)
            manifest["invert"] = bool(prep.get("invert", False))
            manifest["binarize"] = str(prep.get("binarize") or "otsu")
            if data.get("classes"):
                labels = list(data["classes"])
            break

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if manifest["binarize"] == "otsu":
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif manifest["binarize"] == "adaptive":
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5
        )
    else:
        binary = gray
    if manifest["invert"]:
        binary = 255 - binary
    if float(np.mean(binary)) > 127:
        binary = 255 - binary

    # 投影切字
    col = (binary > 0).sum(axis=0)
    gaps: list[tuple[int, int]] = []
    in_gap = False
    start = 0
    for i, v in enumerate(col):
        if v == 0:
            if not in_gap:
                in_gap = True
                start = i
        elif in_gap:
            gaps.append((start, i))
            in_gap = False
    if in_gap:
        gaps.append((start, len(col)))
    cuts = [0]
    for a, b in gaps:
        if b - a >= max_gap:
            mid = (a + b) // 2
            if mid > cuts[-1]:
                cuts.append(mid)
    cuts.append(len(col))
    boxes: list[tuple[int, int, int, int]] = []
    for i in range(len(cuts) - 1):
        xa, xb = cuts[i], cuts[i + 1]
        if xb - xa < 2:
            continue
        strip = binary[:, xa:xb]
        rows = np.where(strip.max(axis=1) > 0)[0]
        if len(rows) == 0:
            continue
        ya, yb = int(rows[0]), int(rows[-1]) + 1
        boxes.append((xa, ya, xb - xa, yb - ya))
    if not boxes:
        boxes = [(0, 0, binary.shape[1], binary.shape[0])]

    cache = getattr(recognize_digits, "_sess", {})
    sess = cache.get(str(onnx_p))
    if sess is None:
        sess = ort.InferenceSession(str(onnx_p), providers=["CPUExecutionProvider"])
        cache[str(onnx_p)] = sess
        recognize_digits._sess = cache  # type: ignore[attr-defined]
    in_name = sess.get_inputs()[0].name
    tw, th = int(manifest["width"]), int(manifest["height"])

    def _disp(lab: str) -> str:
        return {"wan": "万", "yi": "亿", "comma": ",", "slash": "/", "percent": "%", "colon": ":"}.get(lab, lab)

    chars: list[dict] = []
    parts: list[str] = []
    confs: list[float] = []
    for bx, by, bw, bh in boxes:
        patch = binary[by : by + bh, bx : bx + bw]
        resized = cv2.resize(patch, (tw, th), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        tensor = resized.reshape(1, 1, th, tw)
        logits = sess.run(None, {in_name: tensor})[0][0]
        idx = int(np.argmax(logits))
        exp = np.exp(logits - logits.max())
        conf = float(exp[idx] / exp.sum())
        lab = labels[idx] if idx < len(labels) else str(idx)
        confs.append(conf)
        chars.append(
            {
                "label": lab,
                "confidence": conf,
                "x": int(bx + x1),
                "y": int(by + y1),
                "w": int(bw),
                "h": int(bh),
            }
        )
        parts.append(_disp(lab) if conf >= min_confidence else "?")
    mean = float(sum(confs) / len(confs)) if confs else 0.0
    return {"text": "".join(parts), "confidence": mean, "chars": chars}
