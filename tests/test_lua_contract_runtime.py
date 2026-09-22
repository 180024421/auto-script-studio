"""契约在 lupa 里跑通：PC 注册出来的 bot.* / panel.* 必须与设备端（LuaJ）返回形状一致。

设备端返回的是真 Lua 表，所以 PC 侧任何「原样返回 Python list/dict」都是 bug ——
lupa 会把它变成 POBJECT userdata，`#t` / `ipairs` / `t.field` 全部失效。这里逐条钉住。
"""

from __future__ import annotations

import pytest

lupa = pytest.importorskip("lupa")

from lupa import LuaRuntime  # noqa: E402 - 依赖缺失时整文件跳过
from studio.runtime import lua_runner  # noqa: E402
from studio.runtime.panel_state import PanelState  # noqa: E402

DETS = [
    {
        "class_name": "hand",
        "confidence": 0.91,
        "x": 10,
        "y": 20,
        "w": 30,
        "h": 40,
        "center_x": 25,
        "center_y": 40,
        "left": 10,
        "top": 20,
        "width": 30,
        "height": 40,
        "has_mask": True,
        "mask_center_x": 22,
        "mask_center_y": 33,
        "mask_area": 120,
    },
    {
        "class_name": "foot",
        "confidence": 0.5,
        "x": 1,
        "y": 2,
        "w": 3,
        "h": 4,
        "center_x": 2,
        "center_y": 4,
        "left": 1,
        "top": 2,
        "width": 3,
        "height": 4,
        "has_mask": False,
    },
]


class FakeBot:
    """只承担 PcBot 的方法面，不碰 ADB。"""

    def __init__(self) -> None:
        self.logs: list[str] = []
        self.opts_seen: dict[str, dict] = {}
        self.taps: list[tuple[int, int]] = []

    def log(self, msg: str) -> None:
        self.logs.append(str(msg))

    def toast(self, msg: str) -> None:
        self.logs.append(f"[toast] {msg}")

    def trace(self, tag: str, msg: str) -> None:
        self.logs.append(f"[trace:{tag}] {msg}")

    def delay_seconds(self, seconds: float) -> None:
        self.logs.append(f"[delay] {seconds}")

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.logs.append(f"[swipe] {x1},{y1}->{x2},{y2} {duration_ms}")

    def long_press(self, x: int, y: int, duration_ms: int = 500) -> None:
        self.logs.append(f"[longPress] {x},{y} {duration_ms}")

    def open_app(self, package_name: str) -> bool:
        return bool(package_name)

    def find_image(self, path, opts=None):
        self.opts_seen["findImage"] = dict(opts or {})
        return (100, 200)

    def find_color(self, b, g, r, opts=None):
        self.opts_seen["findColor"] = dict(opts or {})
        return (1, 2)

    def find_text(self, target, opts=None):
        self.opts_seen["findText"] = dict(opts or {})
        return (3, 4)

    def find_node(self, opts=None):
        raise RuntimeError("PC 端不支持 bot.findNode")

    def find_multi_color(self, opts=None):
        return (5, 6)

    def wait_gone_image(self, path, opts=None) -> bool:
        return True

    def wait_stable(self, opts=None) -> bool:
        return True

    def recognize_text(self, opts=None):
        return [{"text": "金币", "x": 1, "y": 2, "confidence": 0.8}]

    def recognize_digits(self, opts=None):
        return {
            "text": "123",
            "confidence": 0.9,
            "chars": [
                {"label": "1", "confidence": 0.9, "x": 0, "y": 0, "w": 4, "h": 8},
                {"label": "2", "confidence": 0.8, "x": 5, "y": 0, "w": 4, "h": 8},
            ],
        }

    def yolo_detect(self, opts=None):
        self.opts_seen["yoloDetect"] = dict(opts or {})
        return [dict(d) for d in DETS]

    def find_yolo(self, opts=None):
        return (7, 8)

    def yolo_swipe(self, opts=None) -> None:
        self.logs.append("[yoloSwipe]")


@pytest.fixture()
def env():
    """一个新的 Lua 运行时 + 契约注册好的 bot / panel。"""
    saved = PanelState.all()
    PanelState.clear_watches()
    lua_runner._WARNED_OPTS.clear()
    lua_runner._CALLBACKS.clear()
    bot = FakeBot()
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua_runner.install_bot(lua, bot)
    yield lua, bot
    PanelState.reset(saved)
    PanelState.clear_watches()
    lua_runner._WARNED_OPTS.clear()
    lua_runner._CALLBACKS.clear()


def run(lua, code):
    return lua.execute(code)


# ----------------------------------------------------------------- 返回形状


def test_registered_names_come_from_contract(env):
    lua, _ = env
    names = run(
        lua,
        "local n = {} for k in pairs(bot) do n[#n+1] = k end table.sort(n) return table.concat(n, ',')",
    )
    from studio.runtime.lua_contract import load

    expected = sorted(
        e.lua_name for e in load().values() if e.table == "bot" and (e.on_pc or e.pc_missing == "raise")
    )
    assert names.split(",") == expected


def test_yolo_detect_returns_real_table(env):
    lua, _ = env
    count, first_class, first_cx, mask_type, seen = run(
        lua,
        """
        local dets = bot.yoloDetect({ model = "models/ui.onnx" })
        local seen = 0
        for _, d in ipairs(dets) do seen = seen + 1 end
        return #dets, dets[1].class_name, dets[1].center_x, type(dets[1].has_mask), seen
        """,
    )
    assert count == 2
    assert first_class == "hand"
    assert first_cx == 25
    assert mask_type == "boolean"  # 设备端 LuaValue.valueOf(Boolean) 同形
    assert seen == 2  # ipairs 走得通 = 真 Lua 数组，不是 POBJECT userdata
    assert run(lua, "return (bot.yoloDetect({}))[1].confidence") == pytest.approx(0.91)


def test_yolo_detect_mask_fields_conditional(env):
    lua, _ = env
    assert run(lua, 'return bot.yoloDetect({})[1].mask_area') == 120
    assert run(lua, "return bot.yoloDetect({})[2].mask_center_x") is None
    assert run(lua, "return bot.yoloDetect({})[2].has_mask") is False


def test_recognize_text_rows_are_tables(env):
    lua, _ = env
    n, text = run(
        lua,
        """
        local hits = bot.recognizeText({})
        return #hits, hits[1].text
        """,
    )
    assert n == 1
    assert text == "金币"


def test_recognize_digits_nested_chars(env):
    lua, _ = env
    n, label, total = run(
        lua,
        """
        local r = bot.recognizeDigits({ roi = {1, 2, 10, 12} })
        local sum = 0
        for _, c in ipairs(r.chars) do sum = sum + c.w end
        return #r.chars, r.chars[1].label, sum
        """,
    )
    assert n == 2
    assert label == "1"
    assert total == 8
    assert run(lua, "return bot.recognizeDigits({}).text") == "123"


def test_find_image_returns_two_values(env):
    lua, _ = env
    x, y = run(lua, 'local x, y = bot.findImage("a.png", { threshold = 0.8 }) return x, y')
    assert (x, y) == (100, 200)
    assert run(lua, 'return bot.findImage("a.png") == 100') is True  # 未 marshal 成表


def test_wait_and_bool_returns(env):
    lua, _ = env
    assert run(lua, "return bot.waitStable({})") is True
    assert run(lua, 'return bot.waitGoneImage("a.png")') is True
    assert run(lua, 'return bot.openApp("com.x")') is True


# ------------------------------------------------------------------ opts 传递


def test_opts_reach_python_as_dict(env):
    lua, bot = env
    lua_code = (
        'bot.findImage("a.png", { threshold = 0.42, click = true, optional = false, '
        "tap_dx = 6, timeout = 3, scale_min = 0.5, roi = {1, 2, 3, 4} })"
    )
    run(lua, lua_code)
    opts = bot.opts_seen["findImage"]
    assert opts["threshold"] == pytest.approx(0.42)
    assert opts["roi"] == [1, 2, 3, 4]
    # 标量：lupa 已解包成 Python 值，丢掉会让 PC 静默退回默认值
    assert opts["click"] is True
    assert opts["optional"] is False
    assert opts["tap_dx"] == 6
    assert opts["timeout"] == 3
    assert opts["scale_min"] == pytest.approx(0.5)


def test_omitted_opts_become_empty_dict(env):
    lua, bot = env
    run(lua, 'bot.findImage("a.png")')
    assert bot.opts_seen["findImage"] == {}


def test_optional_trailing_args_use_pc_defaults(env):
    lua, bot = env
    run(lua, "bot.swipe(1, 2, 3, 4)")
    run(lua, "bot.longPress(5, 6)")
    assert "[swipe] 1,2->3,4 300" in bot.logs
    assert "[longPress] 5,6 500" in bot.logs


def test_missing_required_arg_raises_in_lua(env):
    lua, _ = env
    ok, err = run(lua, "return pcall(bot.findImage)")
    assert ok is False
    assert "缺少第 1 个参数 path" in str(err)


# ------------------------------------------------------- 未知 opts：告警不抛错


def test_unknown_opt_warns_once_and_is_ignored(env):
    lua, bot = env
    code = """
        bot.findImage("a.png", { not_a_key = 1 })
        bot.findImage("a.png", { not_a_key = 1 })
        return true
    """
    assert run(lua, code) is True
    warns = [line for line in bot.logs if line.startswith("[contract]")]
    assert len(warns) == 1
    assert "bot.findImage" in warns[0] and "not_a_key" in warns[0] and "契约未声明" in warns[0]
    assert bot.opts_seen["findImage"] == {"not_a_key": 1}  # 照旧透传，由 PcBot 自己忽略


def test_device_only_opt_warns_sides(env):
    lua, bot = env
    run(lua, 'bot.findImage("a.png", { step = 8 })')
    warns = [line for line in bot.logs if line.startswith("[contract]")]
    assert len(warns) == 1
    assert "仅设备端生效" in warns[0]


# ------------------------------------------------------- 设备专有名字：nil vs 报错


def test_device_only_names_nil_vs_raise(env):
    lua, _ = env
    assert run(lua, "return bot.runSaocheng == nil") is True
    assert run(lua, 'return bot.runSaocheng ~= nil') is False
    ok, err = run(lua, "return pcall(bot.listApps)")
    assert ok is False
    assert "bot.listApps 仅 APK 可用" in str(err)
    ok2, err2 = run(lua, 'return pcall(bot.read_chain, "m", 0, {})')
    assert ok2 is False
    assert "bot.read_chain 需 APK + root" in str(err2)


# --------------------------------------------------------------------- panel


def test_panel_time_range_returns_table(env):
    lua, _ = env
    PanelState.reset({"run_at": "08:00-09:30"})
    start, end = run(lua, 'local t = panel.getTimeRange("run_at") return t.start, t["end"]')
    assert (start, end) == ("08:00", "09:30")
    assert run(lua, 'return type(panel.getTimeRange("run_at"))') == "table"


def test_panel_get_set_values_and_snapshot(env):
    lua, _ = env
    PanelState.reset({"k1": "v1", "k2": "v2"})
    assert run(lua, 'return panel.get("k1")') == "v1"
    values = run(lua, 'return panel.values().k2')
    assert values == "v2"
    assert run(lua, 'return panel.snapshot().k1') == "v1"
    assert run(lua, 'return panel.isOn("nope")') is False
    assert run(lua, 'return panel.has("k", "a")') is False


def test_panel_set_from_lua_coerces_bool_like_device(env):
    """设备端 tojstring 把 Lua true 写成 "true"；PC 不能写成 Python 的 "True"。"""
    lua, _ = env
    PanelState.reset({"flag": "false"})
    assert run(lua, 'panel.set("flag", true) return panel.get("flag")') == "true"
    assert run(lua, 'return panel.is("flag", "TRUE")') is True


def test_panel_watch_and_unwatch_round_trip(env):
    lua, _ = env
    PanelState.reset({"sw": "off"})
    run(
        lua,
        """
        hits = 0
        handler = function(v) hits = hits + 1 end
        panel.watch("sw", handler)
        """,
    )
    run(lua, 'panel.set("sw", "on")')
    assert run(lua, "return hits") == 1
    # 同一函数重复注册不应叠加（设备端 PanelWatchRegistry 同样去重）
    run(lua, "panel.watch('sw', handler)")
    run(lua, 'panel.set("sw", "off")')
    assert run(lua, "return hits") == 2
    run(lua, "panel.unwatch('sw', handler)")
    run(lua, 'panel.set("sw", "on")')
    assert run(lua, "return hits") == 2


def test_panel_unwatch_all_without_callback(env):
    lua, _ = env
    PanelState.reset({"sw": "off"})
    run(lua, "hits = 0 panel.watch('sw', function(v) hits = hits + 1 end)")
    run(lua, 'panel.set("sw", "a")')
    run(lua, "panel.unwatch('sw')")
    run(lua, 'panel.set("sw", "b")')
    assert run(lua, "return hits") == 1


def test_log_and_trace_go_through_bot(env):
    lua, bot = env
    run(lua, 'bot.log("你好") bot.__logRaw("raw") bot.toast("t") bot.trace("tag", "m")')
    assert "你好" in bot.logs and "raw" in bot.logs
    assert "[toast] t" in bot.logs and "[trace:tag] m" in bot.logs


def test_mem_still_reports_unsupported(env):
    """mem.* 本轮不入契约（决策：下一子工程处理），但 PC 侧仍需可调用并给出中文报错。"""
    lua, _ = env
    ok, err = run(lua, "return pcall(mem.find_pid, 'com.x')")
    assert ok is False
    assert "mem.find_pid 需 APK + root" in str(err)
