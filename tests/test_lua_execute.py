"""lua_execute 单元测试。"""

from __future__ import annotations

from pathlib import Path

from studio.runtime.lua_execute import _parse_lua_location, format_lua_error


def test_parse_lua_location_with_path():
    loc = _parse_lua_location(
        r'[string "E:/proj/main.lua"]:12: attempt to call a nil value'
    )
    assert loc is not None
    assert loc[1] == 12
    assert "main.lua" in loc[0]


def test_format_lua_error_shows_line():
    exc = RuntimeError(r'[string "@main.lua"]:3: attempt to index a nil value')
    text = format_lua_error(exc, script_path=Path("main.lua"))
    assert "main.lua:3" in text
    assert "nil value" in text


def test_format_lua_error_stack():
    raw = (
        '[string "@main.lua"]:8: divide by zero\n'
        "stack traceback:\n"
        "\tmain.lua:8: in function 'run'\n"
        "\tmain.lua:15: in main chunk"
    )
    text = format_lua_error(RuntimeError(raw), script_path=Path("main.lua"))
    assert "main.lua:8" in text
    assert "main.lua:15" in text


def test_install_lua_logging_no_syntax_error():
    pytest = __import__("pytest")
    pytest.importorskip("lupa")
    from lupa import LuaRuntime

    from studio.runtime.lua_execute import install_lua_logging

    logs: list[str] = []
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    g["bot"] = lua.table_from({"__logRaw": lambda m: logs.append(str(m))})
    install_lua_logging(lua)
    lua.execute('bot.log("ok")')
    assert logs and "ok" in logs[0]
