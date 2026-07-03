"""PC 端 bot API：ADB 截屏/点击 + vision_pc，语义对齐 AutoScriptBridge。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

import cv2

from studio.runtime.lua_values import frac_pair, roi_tuple, table_to_dict
from studio.services import vision_pc
from studio.services.adb_service import AdbService


class PcBot:
    def __init__(
        self,
        project_dir: str | Path,
        *,
        serial: str | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir)
        self.serial = serial
        self.adb = AdbService()
        self._on_log = on_log or (lambda msg: print(msg, flush=True))
        cfg_path = self.project_dir / "project.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.is_file() else {}
        runtime = cfg.get("runtime", {})
        self.default_interval_ms = int(runtime.get("default_interval_ms", 300))
        self.default_yolo_conf = float(runtime.get("default_yolo_conf", 0.35))
        self.default_yolo_model = str(runtime.get("default_yolo_model") or "")

    def log(self, msg: str) -> None:
        self._on_log(str(msg))

    def delay_seconds(self, seconds: float) -> None:
        time.sleep(max(0.0, float(seconds)))

    def tap(self, x: int, y: int) -> None:
        self.adb.tap(self.serial, int(x), int(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.adb.swipe(self.serial, int(x1), int(y1), int(x2), int(y2), int(duration_ms))

    def long_press(self, x: int, y: int, duration_ms: int = 500) -> None:
        self.adb.swipe(self.serial, int(x), int(y), int(x), int(y), int(duration_ms))

    def _capture(self):
        png = self.adb.capture_png(self.serial)
        return vision_pc.decode_png(png)

    def _opt(self, opts: Any) -> dict[str, Any]:
        return table_to_dict(opts)

    def _float(self, opts: dict[str, Any], key: str, default: float) -> float:
        v = opts.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _int(self, opts: dict[str, Any], key: str, default: int = 0) -> int:
        v = opts.get(key, default)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _bool(self, opts: dict[str, Any], key: str, default: bool = False) -> bool:
        v = opts.get(key, default)
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return default

    def find_image(self, path: str, opts: Any = None) -> Optional[tuple[int, int]]:
        o = self._opt(opts)
        threshold = self._float(o, "threshold", 0.9)
        timeout = self._float(o, "timeout", 20.0)
        click = self._bool(o, "click", False)
        optional = self._bool(o, "optional", False)
        roi = roi_tuple(o)
        tap_dx = self._int(o, "tap_dx", 0)
        tap_dy = self._int(o, "tap_dy", 0)
        tpl_path = self.project_dir / path
        if not tpl_path.is_file():
            raise FileNotFoundError(f"模板不存在: {path}")
        template = cv2.imread(str(tpl_path))
        if template is None:
            raise RuntimeError(f"无法读取模板: {path}")
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self._capture()
            m = vision_pc.match_template(frame, template, threshold=threshold, roi=roi)
            if m is not None:
                self.log(f"找图命中 {path} score={m.score:.3f}")
                cx, cy = m.center_x + tap_dx, m.center_y + tap_dy
                if click:
                    self.tap(cx, cy)
                return cx, cy
            time.sleep(self.default_interval_ms / 1000.0)
        if optional:
            return None
        raise RuntimeError(f"找图超时: {path}")

    def find_color(self, b: int, g: int, r: int, opts: Any = None) -> Optional[tuple[int, int]]:
        o = self._opt(opts)
        tol = self._int(o, "tol", 12)
        timeout = self._float(o, "timeout", 15.0)
        click = self._bool(o, "click", False)
        optional = self._bool(o, "optional", False)
        roi = roi_tuple(o)
        tap_dx = self._int(o, "tap_dx", 0)
        tap_dy = self._int(o, "tap_dy", 0)
        target = (int(b), int(g), int(r))
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self._capture()
            pt = vision_pc.find_color(frame, target, tol=tol, roi=roi)
            if pt is not None:
                self.log(f"找色命中 {pt}")
                x, y = pt[0] + tap_dx, pt[1] + tap_dy
                if click:
                    self.tap(x, y)
                return x, y
            time.sleep(self.default_interval_ms / 1000.0)
        if optional:
            return None
        raise RuntimeError(f"找色超时: {target}")

    def find_text(self, target: str, opts: Any = None) -> Optional[tuple[int, int]]:
        o = self._opt(opts)
        mode = str(o.get("match_mode") or "contains")
        timeout = self._float(o, "timeout", 20.0)
        min_conf = self._float(o, "min_confidence", 0.5)
        click = self._bool(o, "click", False)
        optional = self._bool(o, "optional", False)
        roi = roi_tuple(o)
        index = self._int(o, "index", 0)
        tap_dx = self._int(o, "tap_dx", 0)
        tap_dy = self._int(o, "tap_dy", 0)
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self._capture()
            hits = vision_pc.recognize_text(frame, roi=roi, min_confidence=min_conf)
            matched = [h for h in hits if self._text_match(h.text, target, mode)]
            if matched:
                h = matched[index if index < len(matched) else len(matched) - 1]
                self.log(f"识字命中 {h.text}")
                x, y = h.center_x + tap_dx, h.center_y + tap_dy
                if click:
                    self.tap(x, y)
                return x, y
            time.sleep(self.default_interval_ms / 1000.0)
        if optional:
            return None
        raise RuntimeError(f"识字超时: {target}")

    def recognize_text(self, opts: Any = None) -> list[dict[str, Any]]:
        o = self._opt(opts)
        min_conf = self._float(o, "min_confidence", 0.5)
        roi = roi_tuple(o)
        limit = self._int(o, "limit", 30)
        frame = self._capture()
        hits = vision_pc.recognize_text(frame, roi=roi, min_confidence=min_conf)
        self.log(f"识字共 {len(hits)} 条")
        return [
            {"text": h.text, "x": h.center_x, "y": h.center_y, "confidence": h.confidence}
            for h in hits[:limit]
        ]

    def find_node(self, opts: Any = None) -> Optional[tuple[int, int]]:
        """PC 端无无障碍树，仅 APK 支持；optional 时返回 nil。"""
        o = self._opt(opts)
        optional = self._bool(o, "optional", False)
        text = str(o.get("text") or "").strip()
        rid = str(o.get("id") or "").strip()
        self.log(
            "PC 运行不支持 bot.findNode（需设备 APK + 无障碍），"
            f"text={text or '-'} id={rid or '-'}"
        )
        if optional:
            return None
        raise RuntimeError("PC 端不支持 bot.findNode，请在 APK 中运行或设置 optional=true")

    def yolo_detect(self, opts: Any = None) -> list[dict[str, Any]]:
        o = self._opt(opts)
        model = self._resolve_model(o)
        class_name = str(o.get("class_name") or "")
        conf = self._float(o, "conf", self.default_yolo_conf)
        roi = roi_tuple(o)
        frame = self._capture()
        return vision_pc.yolo_detect(frame, model, conf=conf, class_name=class_name, roi=roi)

    def find_yolo(self, opts: Any = None) -> Optional[tuple[int, int]]:
        o = self._opt(opts)
        model = self._resolve_model(o)
        class_name = str(o.get("class_name") or "")
        conf = self._float(o, "conf", self.default_yolo_conf)
        pick = str(o.get("pick") or "best_conf")
        timeout = self._float(o, "timeout", 20.0)
        click = self._bool(o, "click", False)
        optional = self._bool(o, "optional", False)
        roi = roi_tuple(o)
        frac = frac_pair(o)
        tap_dx = self._int(o, "tap_dx", 0)
        tap_dy = self._int(o, "tap_dy", 0)
        delay_before_click = self._float(o, "delay_before_click", 0.0)
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self._capture()
            dets = vision_pc.yolo_detect(frame, model, conf=conf, class_name=class_name, roi=roi)
            det = self._pick_yolo(dets, pick)
            if det is not None:
                self.log(f"YOLO 命中 {det['class_name']} conf={det['confidence']:.2f}")
                pt = self._yolo_click_point(det, frac)
                x, y = pt[0] + tap_dx, pt[1] + tap_dy
                if click:
                    if delay_before_click > 0:
                        self.delay_seconds(delay_before_click)
                    self.tap(x, y)
                return x, y
            time.sleep(self.default_interval_ms / 1000.0)
        if optional:
            return None
        raise RuntimeError(f"YOLO 超时: class={class_name}")

    def yolo_swipe(self, opts: Any = None) -> None:
        o = self._opt(opts)
        model = self._resolve_model(o)
        class_name = str(o.get("class_name") or "")
        conf = self._float(o, "conf", self.default_yolo_conf)
        pick = str(o.get("pick") or "best_conf")
        timeout = self._float(o, "timeout", 20.0)
        roi = roi_tuple(o)
        distance = self._int(o, "distance", 400)
        direction = str(o.get("direction") or "up").lower()
        duration_ms = self._int(o, "duration_ms", 350)
        frac = frac_pair(o)
        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = self._capture()
            dets = vision_pc.yolo_detect(frame, model, conf=conf, class_name=class_name, roi=roi)
            det = self._pick_yolo(dets, pick)
            if det is not None:
                cx, cy = self._yolo_click_point(det, frac)
                if direction == "down":
                    x2, y2 = cx, cy + distance
                elif direction == "left":
                    x2, y2 = cx - distance, cy
                elif direction == "right":
                    x2, y2 = cx + distance, cy
                else:
                    x2, y2 = cx, cy - distance
                self.log(f"YOLO 滑动 {direction} ({cx},{cy})->({x2},{y2})")
                self.swipe(cx, cy, x2, y2, duration_ms)
                return
            time.sleep(self.default_interval_ms / 1000.0)
        raise RuntimeError(f"YOLO 滑动超时: class={class_name}")

    def _resolve_model(self, opts: dict[str, Any]) -> str:
        for key in ("model", "model_path"):
            val = str(opts.get(key) or "").strip()
            if val:
                p = Path(val)
                if not p.is_absolute():
                    p = self.project_dir / val
                return str(p)
        if self.default_yolo_model:
            p = self.project_dir / self.default_yolo_model
            return str(p)
        raise RuntimeError("未指定 yolo 模型（opts.model 或 project.json runtime.default_yolo_model）")

    @staticmethod
    def _text_match(text: str, target: str, mode: str) -> bool:
        if mode == "equals":
            return text == target
        if mode == "startswith":
            return text.startswith(target)
        return target in text

    @staticmethod
    def _pick_yolo(dets: list[dict[str, Any]], policy: str) -> dict[str, Any] | None:
        if not dets:
            return None
        pol = policy.lower()
        if pol == "largest":
            return max(dets, key=lambda d: int(d.get("w", 0)) * int(d.get("h", 0)))
        if pol == "nearest":
            return dets[0]
        return max(dets, key=lambda d: float(d.get("confidence", 0)))

    @staticmethod
    def _yolo_click_point(det: dict[str, Any], frac: tuple[float, float]) -> tuple[int, int]:
        fx = max(0.0, min(1.0, frac[0]))
        fy = max(0.0, min(1.0, frac[1]))
        x = int(det["x"]) + int(int(det["w"]) * fx)
        y = int(det["y"]) + int(int(det["h"]) * fy)
        return x, y
