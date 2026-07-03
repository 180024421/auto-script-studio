"""PC Lua 执行：带脚本名/行号的 load 与错误格式化。"""

from __future__ import annotations

import re
from pathlib import Path

_LUA_ERR_HEAD = re.compile(
    r'^(?:\[(?:string\s+)?)?"?@?(?P<file>[^"\]]+)"?\]?:?(?P<line>\d+):?\s*(?P<msg>.*)$'
)
_LUA_STACK = re.compile(r"^\s*(?P<file>[^\]:]+):(?P<line>\d+):\s+in\s+(?P<ctx>.+)$")


def chunk_name_for(script_path: Path) -> str:
    """Lua load 用 chunk 名，错误信息会带 @文件:行号。"""
    try:
        return f"@{script_path.resolve()}"
    except OSError:
        return f"@{script_path.name}"


def format_lua_error(exc: BaseException, *, script_path: Path | None = None) -> str:
    """将 lupa / Python 异常格式化为可定位的日志块。"""
    raw = str(exc).strip() or repr(exc)
    lines: list[str] = ["[Lua 错误]"]

    body = raw.splitlines()
    head = _parse_lua_location(body[0])
    if head:
        file_part, line_no, msg = head
        lines.append(f"  位置: {_display_path(file_part, script_path)}:{line_no}")
        if msg:
            lines.append(f"  原因: {msg}")
    else:
        lines.append(f"  {body[0]}")

    for part in body[1:]:
        part = part.strip()
        if not part:
            continue
        m = _LUA_STACK.match(part)
        if m:
            display = _display_path(m.group("file"), script_path)
            lines.append(f"  → {display}:{m.group('line')} in {m.group('ctx')}")
        elif part.startswith("stack traceback:"):
            lines.append("  堆栈:")
        else:
            lines.append(f"    {part}")

    return "\n".join(lines)


def _display_path(file_part: str, script_path: Path | None) -> str:
    text = file_part.lstrip("@").strip('"')
    if script_path is not None:
        try:
            if Path(text).resolve() == script_path.resolve():
                return script_path.name
        except OSError:
            if text.replace("\\", "/").endswith(script_path.name):
                return script_path.name
    name = text.replace("\\", "/").split("/")[-1]
    return name or text


def _parse_lua_location(line: str) -> tuple[str, int, str] | None:
    text = line.strip()
    m = _LUA_ERR_HEAD.match(text)
    if not m:
        return None
    msg = (m.group("msg") or "").strip()
    return m.group("file"), int(m.group("line")), msg


def execute_lua_chunk(lua, code: str, chunkname: str) -> None:
    """以 chunk 名 load 并 xpcall，错误信息含 Lua 行号。"""
    loader = lua.eval(
        """
        function(src, name)
            local fn, err = load(src, name, "t")
            if not fn then
                error(err, 0)
            end
            return fn
        end
        """
    )
    runner = lua.eval(
        """
        function(fn)
            local ok, err = xpcall(fn, debug.traceback)
            if not ok then
                error(err, 0)
            end
        end
        """
    )
    fn = loader(code, chunkname)
    runner(fn)


def install_lua_logging(lua) -> None:
    """bot.log / print 输出带 [文件:行号] 前缀（依赖 bot.__logRaw）。"""

    def py_print(*args) -> None:
        g = lua.globals()
        log_raw = g["bot"]["__logRaw"]
        text = "\t".join("nil" if a is None else str(a) for a in args)
        log_raw(f"[print] {text}")

    g = lua.globals()
    g["print"] = py_print
    lua.execute(
        r"""
bot.log = function(msg)
    local info = debug.getinfo(2, "Sl")
    local line = info and info.currentline or "?"
    local src = info and info.short_src or "lua"
    if string.sub(src, 1, 1) == "@" then
        src = string.sub(src, 2)
    end
    local last = 1
    for i = 1, #src do
        local c = string.sub(src, i, i)
        if c == "/" or c == "\\" then
            last = i + 1
        end
    end
    src = string.sub(src, last)
    bot.__logRaw(string.format("[%s:%s] %s", src, line, tostring(msg)))
end
"""
    )
