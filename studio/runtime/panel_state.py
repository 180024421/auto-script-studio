"""PC 端浮动面板表单状态（与 Android OverlayWidgetStore / Lua panel.* 对齐）。"""



from __future__ import annotations



import json

from pathlib import Path

from typing import Any, Callable



_listeners: list[Callable[[], None]] = []

_watches: dict[str, list[Callable[[str], None]]] = {}





class PanelState:

    _values: dict[str, str] = {}



    @classmethod

    def reset(cls, defaults: dict[str, str] | None = None) -> None:

        cls._values = dict(defaults or {})

        cls._notify()



    @classmethod

    def get(cls, widget_id: str) -> str:

        return cls._values.get(widget_id, "")



    @classmethod

    def set(cls, widget_id: str, value: str) -> None:

        old = cls._values.get(widget_id)

        cls._values[widget_id] = value

        cls._notify()

        if old != value:

            for fn in list(cls._watches.get(widget_id, [])):

                fn(value)



    @classmethod

    def watch(cls, widget_id: str, callback: Callable[[str], None]) -> None:

        wid = str(widget_id)

        cls._watches.setdefault(wid, [])

        if callback not in cls._watches[wid]:

            cls._watches[wid].append(callback)



    @classmethod

    def unwatch(cls, widget_id: str, callback: Callable[[str], None] | None = None) -> None:

        wid = str(widget_id)

        if callback is None:

            cls._watches.pop(wid, None)

            return

        if wid in cls._watches:

            cls._watches[wid] = [fn for fn in cls._watches[wid] if fn is not callback]

            if not cls._watches[wid]:

                del cls._watches[wid]



    @classmethod

    def clear_watches(cls) -> None:

        cls._watches.clear()



    @classmethod

    def all(cls) -> dict[str, str]:

        return dict(cls._values)



    @classmethod

    def is_on(cls, widget_id: str) -> bool:

        return cls.get(widget_id).strip().lower() in ("true", "1", "yes", "on")



    @classmethod

    def time_range(cls, widget_id: str) -> tuple[str, str]:

        raw = cls.get(widget_id).strip()

        if raw and "-" in raw:

            start, end = raw.split("-", 1)

            return start.strip(), end.strip()

        return "09:00", "18:00"



    @classmethod

    def snapshot(cls) -> dict[str, str]:

        return dict(cls.all())



    @classmethod

    def is_value(cls, widget_id: str, expected: str) -> bool:

        return cls.get(widget_id).strip().lower() == expected.strip().lower()



    @classmethod

    def has_option(cls, widget_id: str, option: str) -> bool:

        needle = option.strip().lower()

        if not needle:

            return False

        parts = [p.strip().lower() for p in cls.get(widget_id).split(",") if p.strip()]

        return needle in parts



    @classmethod

    def sidecar_path(cls, project_dir: Path) -> Path:

        return Path(project_dir) / ".studio" / "panel-state.json"



    @classmethod

    def save_sidecar(cls, project_dir: Path) -> None:

        path = cls.sidecar_path(project_dir)

        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(json.dumps(cls.all(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



    @classmethod

    def load_sidecar(cls, project_dir: Path) -> bool:

        path = cls.sidecar_path(project_dir)

        if not path.is_file():

            return False

        data = json.loads(path.read_text(encoding="utf-8"))

        if isinstance(data, dict):

            cls.reset({str(k): str(v) for k, v in data.items()})

            return True

        return False



    @classmethod

    def seed_from_layout(cls, layout: dict[str, Any]) -> None:

        defaults: dict[str, str] = {}



        def walk(widgets: list[dict[str, Any]]) -> None:

            for w in widgets:

                wtype = w.get("type", "")

                wid = w.get("id", "")

                if wtype in (
                    "input", "select", "radio", "multiselect",
                    "switch", "time_range", "slider", "stepper", "textarea",
                ) and wid:

                    if wtype == "switch":
                        raw = w.get("default", False)
                        defaults[wid] = (
                            "true"
                            if str(raw).lower() in ("true", "1", "yes", "on")
                            else "false"
                        )
                    elif wtype == "time_range":
                        defaults[wid] = str(w.get("default", "")) or (
                            f"{w.get('default_start', '09:00')}-{w.get('default_end', '18:00')}"
                        )
                    elif wtype in ("slider", "stepper"):
                        defaults[wid] = str(w.get("default", w.get("min", 0)))
                    else:
                        defaults[wid] = str(w.get("default", ""))

                elif wtype == "tabs":

                    for tab in w.get("tabs") or []:

                        walk(tab.get("widgets") or [])



        if layout.get("screens"):
            from studio.services.screen_layout import flatten_all_widgets

            walk(flatten_all_widgets(layout))
        else:
            widgets = layout.get("widgets") or layout.get("buttons") or []
            walk(widgets)

        cls.reset(defaults)



    @classmethod

    def add_listener(cls, fn: Callable[[], None]) -> None:

        if fn not in _listeners:

            _listeners.append(fn)



    @classmethod

    def remove_listener(cls, fn: Callable[[], None]) -> None:

        if fn in _listeners:

            _listeners.remove(fn)



    @classmethod

    def _notify(cls) -> None:

        for fn in list(_listeners):

            fn()



    @classmethod

    def format_summary(cls) -> str:

        if not cls._values:

            return "（在预览中操作表单，此处显示 panel.get 将读到的值）"

        return "  |  ".join(f"{k}={v}" for k, v in cls._values.items())

