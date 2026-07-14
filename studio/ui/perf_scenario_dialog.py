"""性能场景向导 — 按使用场景写入 project.json runtime。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from studio.services.runtime_presets import PRESETS, SCENARIO_HINTS


class PerfScenarioDialog(QDialog):
    def __init__(self, parent, current_key: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("性能场景向导")
        self.setMinimumSize(520, 360)
        self._selected_key = current_key or "yolo_fast"

        root = QVBoxLayout(self)
        root.addWidget(
            QLabel(
                "选择最接近你脚本场景的配置，将写入 project.json 的 runtime 段。"
                "打包前可在设置页查看摘要，真机运行后可在 APK 设置页看耗时统计。"
            )
        )
        root.addWidget(QLabel("场景列表"))
        self.list = QListWidget()
        for key, preset in PRESETS.items():
            hint = SCENARIO_HINTS.get(key, "")
            item = QListWidgetItem(f"{preset['label']}\n{hint}")
            item.setData(256, key)
            self.list.addItem(item)
            if key == self._selected_key:
                self.list.setCurrentItem(item)
        self.list.currentItemChanged.connect(self._on_pick)
        root.addWidget(self.list, 1)

        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setStyleSheet("color:#64748B;padding:8px;background:#F8FAFC;border-radius:8px;")
        root.addWidget(self.detail)
        self._refresh_detail()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_pick(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        self._selected_key = str(current.data(256) or "yolo_fast")
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        preset = PRESETS.get(self._selected_key, {})
        runtime = preset.get("runtime") or {}
        perf = runtime.get("perf") or {}
        lines = [
            f"input_mode: {runtime.get('input_mode', '（不变）')}",
            f"screenshot_mode: {runtime.get('screenshot_mode', '（不变）')}",
            f"yolo_imgsz: {perf.get('yolo_imgsz', 320)}",
            f"yolo_nnapi: {perf.get('yolo_nnapi', True)}",
            f"capture_cache_ttl_ms: {perf.get('capture_cache_ttl_ms', 80)}",
        ]
        if perf.get("yolo_seg_fast"):
            lines.append("yolo_seg_fast: true（seg 专用）")
        if perf.get("yolo_warmup"):
            lines.append("yolo_warmup: true")
        self.detail.setText("\n".join(lines))

    def selected_key(self) -> str:
        item = self.list.currentItem()
        if item is None:
            return self._selected_key
        return str(item.data(256) or self._selected_key)
