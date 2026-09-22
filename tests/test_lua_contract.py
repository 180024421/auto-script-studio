"""`contract/lua_api.json` 自身：加载、结构自校验与返回 marshal（不依赖 lupa / 设备端）。

契约是 bot.* / panel.* 的单一来源，这里守住它「像样」：形状合法、设备专有名字可判定、
marshal 能把 Python 返回值转成两端一致的 Lua 形状。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from studio.runtime.lua_contract import (
    CONTRACT_PATH,
    ContractError,
    _entry,
    coerce,
    load,
    marshal,
    validate,
)


class FakeLua:
    """无 lupa 环境下断言返回形状：记录 table_from 收到的 Python 值。"""

    def __init__(self) -> None:
        self.tables: list[object] = []

    def table_from(self, value):
        self.tables.append(value)
        return value


@pytest.fixture(scope="module")
def entries() -> dict:
    return load()


def test_contract_file_is_where_runner_expects():
    assert CONTRACT_PATH.is_file()
    assert CONTRACT_PATH.name == "lua_api.json"


def test_load_returns_every_entry(entries):
    assert len(entries) >= 38
    assert all(name.startswith(("bot.", "panel.")) for name in entries)
    # 工具箱与文档里的每个名字都得能查到
    assert "bot.findImage" in entries and "panel.getTimeRange" in entries


def test_entry_metadata(entries):
    find_image = entries["bot.findImage"]
    assert find_image.pc == "find_image"
    assert find_image.table == "bot"
    assert find_image.lua_name == "findImage"
    assert find_image.opts_index == 1
    # step 是设备端模板扫描步长，PC 全像素匹配 → 只应出现在 apk 侧
    assert "step" in find_image.side_opts("apk")
    assert "step" not in find_image.side_opts("pc")
    assert find_image.side_opts("pc")["threshold"].default == 0.9


def test_defaults_are_declared_either_literal_or_from_config(entries):
    for name, entry in entries.items():
        for opt in entry.opts:
            assert not (opt.has_default and opt.default_from), f"{name}.{opt.key} 二者只能选一"


def test_device_only_names_are_classified(entries):
    saocheng = entries["bot.runSaocheng"]
    assert not saocheng.on_pc and saocheng.pc_missing == "nil"
    assert not saocheng.pc_error
    list_apps = entries["bot.listApps"]
    assert not list_apps.on_pc and list_apps.pc_missing == "raise"
    assert "APK" in list_apps.pc_error and list_apps.pc_error.startswith("bot.listApps")
    read_chain = entries["bot.read_chain"]
    assert read_chain.pc_missing == "raise"
    assert read_chain.pc_error.startswith("bot.read_chain")


def test_log_raw_is_internal(entries):
    raw = entries["bot.__logRaw"]
    assert raw.internal and raw.on_pc and not raw.on_apk


def _api(payload, name):
    return payload["api"][name]


def _bad_version(r):
    r["version"] = 2


def _unknown_side(r):
    _api(r, "bot.tap")["availability"] = ["pc", "web"]


def _pc_without_method(r):
    del _api(r, "bot.tap")["pc"]


def _device_only_with_pc(r):
    _api(r, "bot.listApps")["pc"] = "list_apps"


def _raise_without_message(r):
    del _api(r, "bot.listApps")["pc_error"]


def _bad_pc_missing(r):
    _api(r, "bot.runSaocheng")["pc_missing"] = "maybe"


def _bad_arg_type(r):
    _api(r, "bot.tap")["args"][0]["type"] = "float"


def _optional_not_last(r):
    _api(r, "bot.swipe")["args"][0]["optional"] = True


def _opts_without_carrier(r):
    _api(r, "bot.tap")["opts"] = {"x": {"type": "int"}}


def _camel_case_opt(r):
    _api(r, "bot.findImage")["opts"]["thresholdX"] = {"type": "int"}


def _unknown_opt_type(r):
    _api(r, "bot.findImage")["opts"]["threshold"]["type"] = "float64"


def _sides_both_ends(r):
    _api(r, "bot.findColor")["opts"]["tol"]["sides"] = ["pc", "apk"]


def _default_and_default_from(r):
    _api(r, "bot.findImage")["opts"]["threshold"]["default_from"] = "x"


def _tuple_without_items(r):
    del _api(r, "bot.findImage")["returns"]["items"]


def _array_of_without_fields(r):
    del _api(r, "bot.listApps")["returns"]["item_fields"]


def _table_with_item_fields(r):
    _api(r, "panel.values")["returns"]["item_fields"] = ["a"]


def _internal_without_underscore(r):
    _api(r, "bot.log")["internal"] = True


def _return_kind_outside_vocab(r):
    _api(r, "bot.tap")["returns"]["kind"] = "void"


def _opts_key_not_snake(r):
    _api(r, "bot.waitStable")["opts"]["Timeout"] = {"type": "number"}


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_bad_version, "version"),
        (_unknown_side, "未知端"),
        (_pc_without_method, "必须给出 pc"),
        (_device_only_with_pc, "不应有 pc 字段"),
        (_raise_without_message, "需要 pc_error 文案"),
        (_bad_pc_missing, "pc_missing"),
        (_bad_arg_type, "不在词表"),
        (_optional_not_last, "只有末位参数可标 optional"),
        (_opts_without_carrier, "名为 opts 的表参数"),
        (_camel_case_opt, "snake_case"),
        (_unknown_opt_type, "不在词表"),
        (_sides_both_ends, "两端齐全"),
        (_default_and_default_from, "互斥"),
        (_tuple_without_items, "tuple 返回需要 items"),
        (_array_of_without_fields, "array_of 返回需要 item_fields"),
        (_table_with_item_fields, "不应带 item_fields"),
        (_internal_without_underscore, "下划线"),
        (_return_kind_outside_vocab, "不在词表"),
        (_opts_key_not_snake, "snake_case"),
    ],
    ids=lambda fn: getattr(fn, "__name__", ""),
)
def test_validate_rejects_broken_shapes(mutate, expected):
    raw = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    payload = copy.deepcopy(raw)
    mutate(payload)
    issues = validate(payload)
    assert any(expected in msg for msg in issues), f"{mutate.__name__} 未被发现：{issues}"


def test_duplicate_json_keys_rejected(tmp_path: Path):
    bad = tmp_path / "dup.json"
    bad.write_text(
        '{"version":1,"api":{"bot.tap":{"pc":"tap","availability":["pc","apk"],'
        '"args":[],"returns":{"kind":"none"}},'
        '"bot.tap":{"pc":"tap2","availability":["pc"],"args":[],'
        '"returns":{"kind":"none"}}}}',
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="重复键"):
        load(bad, use_cache=False)


def test_missing_contract_file_rejected(tmp_path: Path):
    with pytest.raises(ContractError, match="缺少契约文件"):
        load(tmp_path / "nope.json", use_cache=False)


# ------------------------------------------------------------------- marshal


def test_marshal_scalar_kinds(entries):
    lua = FakeLua()
    assert marshal(lua, None, entries["bot.tap"].returns) is None
    assert marshal(lua, 1, entries["bot.openApp"].returns) is True
    assert marshal(lua, "", entries["panel.get"].returns) == ""
    assert marshal(lua, 3, entries["bot.read_chain"].returns) == 3


def test_marshal_tuple_gives_multiple_returns(entries):
    lua = FakeLua()
    spec = entries["bot.findImage"].returns
    assert marshal(lua, (10, 20), spec) == (10, 20)
    assert marshal(lua, None, spec) is None
    assert marshal(lua, (10.7, 20.2), spec) == (10, 20)
    with pytest.raises(ContractError, match="契约要求 2"):
        marshal(lua, (10,), spec)


def test_marshal_named_fields_from_positional_tuple(entries):
    lua = FakeLua()
    spec = entries["panel.getTimeRange"].returns
    assert marshal(lua, ("08:00", "09:30"), spec) == {"start": "08:00", "end": "09:30"}
    with pytest.raises(ContractError, match="契约要求字段"):
        marshal(lua, ("08:00",), spec)


def test_marshal_array_of_builds_lua_tables(entries):
    lua = FakeLua()
    spec = entries["bot.yoloDetect"].returns
    rows = [{"class_name": "hand", "has_mask": True}, {"class_name": "foot"}]
    out = marshal(lua, rows, spec)
    assert out == rows
    # 递归 marshal：每一行与外层数组都走 table_from，而不是原样丢给 Lua
    assert lua.tables == [rows[0], rows[1], rows]


def test_marshal_empty_list_still_becomes_a_table(entries):
    lua = FakeLua()
    marshal(lua, [], entries["bot.recognizeText"].returns)
    assert lua.tables == [[]]


def test_marshal_none_returns_nil_not_empty_table(entries):
    lua = FakeLua()
    assert marshal(lua, None, entries["bot.recognizeText"].returns) is None


# --------------------------------------------------------------------- coerce


@pytest.mark.parametrize(
    ("value", "atype", "expected"),
    [
        ("12", "int", 12),
        (12.9, "int", 12),
        (0, "bool", False),
        (1, "bool", True),
        ("7", "number", "7"),
        (True, "string", "true"),
        (False, "string", "false"),
        ("x", "string", "x"),
        ({"a": 1}, "table", {"a": 1}),
    ],
)
def test_coerce(value, atype, expected):
    assert coerce(value, atype) == expected


def test_entry_helper_rejects_non_object():
    with pytest.raises(ContractError, match="不是对象"):
        _entry("bot.x", "nope")
