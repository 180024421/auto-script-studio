"""ADB 动作录制 → Lua 脚本片段。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class RecordedAction:
    kind: Literal["tap", "swipe", "delay", "find_yolo"]
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    duration_ms: int = 300
    seconds: float = 0.5
    model: str = ""
    class_name: str = ""
    conf: float = 0.35
    use_mask_center: bool = False


@dataclass
class ActionRecorder:
    actions: list[RecordedAction] = field(default_factory=list)
    recording: bool = False

    def start(self) -> None:
        self.recording = True
        self.actions.clear()

    def stop(self) -> None:
        self.recording = False

    def tap(self, x: int, y: int) -> None:
        if not self.recording:
            return
        self.actions.append(RecordedAction(kind="tap", x1=x, y1=y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 350) -> None:
        if not self.recording:
            return
        self.actions.append(
            RecordedAction(kind="swipe", x1=x1, y1=y1, x2=x2, y2=y2, duration_ms=duration_ms)
        )

    def delay(self, seconds: float) -> None:
        if not self.recording:
            return
        self.actions.append(RecordedAction(kind="delay", seconds=seconds))

    def find_yolo(
        self,
        model: str,
        class_name: str = "",
        conf: float = 0.35,
        *,
        use_mask_center: bool = False,
    ) -> None:
        if not self.recording:
            return
        self.actions.append(
            RecordedAction(
                kind="find_yolo",
                model=model,
                class_name=class_name,
                conf=conf,
                use_mask_center=use_mask_center,
            )
        )

    def to_lua(self) -> str:
        lines = ["-- 录制动作", "bot.log('执行录制动作')"]
        for a in self.actions:
            if a.kind == "tap":
                lines.append(f"bot.tap({a.x1}, {a.y1})")
            elif a.kind == "swipe":
                lines.append(f"bot.swipe({a.x1}, {a.y1}, {a.x2}, {a.y2}, {a.duration_ms})")
            elif a.kind == "delay":
                lines.append(f"bot.delay({a.seconds})")
            elif a.kind == "find_yolo":
                safe_model = a.model.replace("\\", "/").replace('"', '\\"')
                opts = [f'model = "{safe_model}"', f"conf = {a.conf}", "click = true", "optional = true"]
                if a.class_name:
                    safe_cls = a.class_name.replace('"', '\\"')
                    opts.append(f'class_name = "{safe_cls}"')
                if a.use_mask_center:
                    opts.append("use_mask_center = true")
                lines.append(f"bot.findYolo({{ {', '.join(opts)} }})")
        return "\n".join(lines) + "\n"
