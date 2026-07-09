"""YOLO seg 字段与掩码质心工具测试。"""

from __future__ import annotations

import math

from studio.services.yolo_models import normalize_detection, normalize_detections


def test_normalize_detection_with_mask():
    d = normalize_detection(
        {
            "class_name": "hand",
            "confidence": 0.91,
            "x": 10,
            "y": 20,
            "w": 30,
            "h": 40,
            "has_mask": True,
            "mask_center_x": 25,
            "mask_center_y": 38,
            "mask_area": 120,
        }
    )
    assert d["has_mask"] is True
    assert d["mask_center_x"] == 25
    assert d["mask_center_y"] == 38
    assert d["mask_area"] == 120


def test_normalize_detection_without_mask():
    d = normalize_detection({"class_name": "a", "confidence": 0.5, "x": 0, "y": 0, "w": 10, "h": 10})
    assert d["has_mask"] is False
    assert "mask_center_x" not in d


def test_mask_centroid_decode_smoke():
    """与 OnnxYoloDetector.decodeMaskCentroid 同算法的 Python 参考实现冒烟。"""

    def sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    imgsz = 320
    nm = 2
    mh = mw = 4
    proto = [0.0] * (nm * mh * mw)
    proto[0 * mh * mw + 2 * mw + 2] = 5.0
    coeffs = [1.0, 0.0]
    logits = []
    for i in range(mh * mw):
        s = sum(coeffs[k] * proto[k * mh * mw + i] for k in range(nm))
        logits.append(sigmoid(s))

    cx_img, cy_img, w_img, h_img = 160.0, 160.0, 80.0, 80.0
    bx1 = int(cx_img - w_img / 2)
    by1 = int(cy_img - h_img / 2)
    bx2 = int(cx_img + w_img / 2)
    by2 = int(cy_img + h_img / 2)
    count = 0
    sum_x = sum_y = 0
    for py in range(by1, by2 + 1):
        sy = min(mh - 1, py * mh // imgsz)
        for px in range(bx1, bx2 + 1):
            sx = min(mw - 1, px * mw // imgsz)
            if logits[sy * mw + sx] >= 0.5:
                sum_x += px
                sum_y += py
                count += 1
    assert count > 0
    assert normalize_detections([{"class_name": "x", "confidence": 1.0, "x": 0, "y": 0, "w": 1, "h": 1}])
