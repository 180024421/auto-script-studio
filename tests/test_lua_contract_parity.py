"""契约 ↔ 设备端 Kotlin / PC 端 Python / 工具箱 / 文档 的对账守卫。

CI 里唯一的入口就是这个文件（无需新增 workflow 步骤）：`tools/lua_contract_check.py`
解析 `LuaBindings.kt` + `AutoScriptBridge.kt` 与 `pc_bot.py` + `panel_state.py`，
与契约双向比对，并检查工具箱按钮、可插入 Lua 片段与 docs/LUA.md。

除「当前全绿」外，还各留一条**变异测试**证明守卫不是空转：契约少一条 `sides`、
设备端改一个名字、契约写错 pc 方法名，都必须让 CI 变红。解析器对不上源码结构时应抛
`ParityError`（fail-closed），而不是静默跳过。
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studio.runtime.lua_contract import CONTRACT_PATH, _entry  # noqa: E402
from tools import lua_contract_check as check  # noqa: E402


def _entries_from(payload: dict) -> dict:
    return {str(k): _entry(str(k), v) for k, v in payload["api"].items()}


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_all_five_checks_are_clean(raw):
    issues = check.all_issues(_entries_from(raw))
    assert issues == [], "契约与设备端/PC 端/工具箱/文档不一致：\n  - " + "\n  - ".join(issues)


def test_device_names_match_contract_exactly(raw):
    entries = _entries_from(raw)
    bindings = check.LUA_BINDINGS.read_text(encoding="utf-8")
    bridge = check.BRIDGE.read_text(encoding="utf-8")
    device = check.device_bindings(bindings, bridge)
    contract = {e.name for e in entries.values() if e.on_apk}
    assert device and contract <= set(device)
    assert set(device) <= contract


def test_checker_covers_panel_table_too(raw):
    entries = _entries_from(raw)
    device = check.device_bindings(
        check.LUA_BINDINGS.read_text(encoding="utf-8"),
        check.BRIDGE.read_text(encoding="utf-8"),
    )
    panel_names = {n for n in device if n.startswith("panel.")}
    assert panel_names
    assert panel_names == {
        e.name for e in entries.values() if e.on_apk and e.table == "panel"
    }


# --------------------------------------------------------------- 变异测试


def test_dropping_a_sides_record_turns_ci_red(raw):
    """契约里删掉 `step` 的 apk-only 标记 → 变成「两端都支持」→ PC 读不到，红。"""
    payload = copy.deepcopy(raw)
    del payload["api"]["bot.findImage"]["opts"]["step"]["sides"]
    issues = check.all_issues(_entries_from(payload))
    assert any("step" in msg for msg in issues), issues


def test_adding_an_invented_opt_turns_ci_red(raw):
    payload = copy.deepcopy(raw)
    payload["api"]["bot.findImage"]["opts"]["nonexistent_key"] = {"type": "int"}
    issues = check.all_issues(_entries_from(payload))
    assert any("nonexistent_key" in msg for msg in issues), issues


def test_undeclared_pc_opt_key_turns_ci_red(raw):
    """pc_bot.wait_stable 实际读 stable_samples；契约漏声明它就红。"""
    payload = copy.deepcopy(raw)
    del payload["api"]["bot.waitStable"]["opts"]["stable_samples"]
    issues = check.all_issues(_entries_from(payload))
    assert any("stable_samples" in msg for msg in issues), issues


def test_wrong_pc_method_name_turns_ci_red(raw):
    payload = copy.deepcopy(raw)
    payload["api"]["bot.findImage"]["pc"] = "find_image_v2"
    issues = check.all_issues(_entries_from(payload))
    assert any("find_image_v2" in msg for msg in issues), issues


def test_device_rename_turns_ci_red(raw, tmp_path: Path, monkeypatch):
    """设备端把 findImage 改名而契约没跟着改 → 双向都要报。"""
    src = check.LUA_BINDINGS.read_text(encoding="utf-8")
    assert 'bot.set("findImage"' in src
    renamed = src.replace('bot.set("findImage"', 'bot.set("findImageV2"')
    moved = tmp_path / "LuaBindings.kt"
    moved.write_text(renamed, encoding="utf-8")
    monkeypatch.setattr(check, "LUA_BINDINGS", moved)
    issues = check.check_device(_entries_from(raw))
    assert any("契约标了 apk 可用，但设备端未注册：bot.findImage" in m for m in issues), issues
    assert any("设备端注册了，但契约没有" in m and "findImageV2" in m for m in issues), issues


def test_unparseable_kotlin_fails_closed():
    """绑定指向一个不存在的类时抛 ParityError，而不是安静返回「没问题」。"""
    src = check.LUA_BINDINGS.read_text(encoding="utf-8")
    broken = src.replace(
        'bot.set("findImage", FindImageFn(bridge))',
        'bot.set("findImage", FindImageFnX(bridge))',
    )
    assert broken != src, "设备端注册行写法变了，本测试需同步"
    with pytest.raises(check.ParityError, match="找不到 class"):
        check.device_bindings(broken, check.BRIDGE.read_text(encoding="utf-8"))


# ----------------------------------------------------- 手写桩不得回潮


def test_runner_has_no_handwritten_api_stubs():
    src = (ROOT / "studio/runtime/lua_runner.py").read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in src.splitlines()
        if 'raise RuntimeError("bot.' in line or 'raise RuntimeError("panel.' in line
    ]
    assert not offenders, f"lua_runner.py 里又出现手写 API 桩：{offenders}"


def test_contract_is_the_only_place_with_apk_only_messages():
    src = (ROOT / "studio/runtime/lua_runner.py").read_text(encoding="utf-8")
    # 逐函数的报错文案已进契约，只剩 pc_error 缺失时的一处 generic fallback
    assert src.count("仅 APK 可用") == 1, src.count("仅 APK 可用")
