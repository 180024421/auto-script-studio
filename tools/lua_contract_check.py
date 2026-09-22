"""把契约 `contract/lua_api.json` 与实现、文档逐处对账：设备端 Kotlin、PC 端 Python、工具箱、docs。

这是「契约单源」的守门员：Kotlin 侧不引入代码生成，改为在此解析
`LuaBindings.kt` + `AutoScriptBridge.kt`；PC 侧解析 `pc_bot.py` + `panel_state.py`；
再检查工具箱按钮、可插入 Lua 片段与 `docs/LUA.md`，全部与契约双向比对。
解析不出来时**报错而不是跳过**（fail-closed），否则守卫会静默失效。

由 `tests/test_lua_contract_parity.py` 调用，因此 CI 无需新增步骤。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
_LUA_DIR = REPO_ROOT / "android-runtime/script/src/main/java/com/autoscript/script/lua"
LUA_BINDINGS = _LUA_DIR / "LuaBindings.kt"
BRIDGE = _LUA_DIR / "AutoScriptBridge.kt"

# bot.set("findImage", FindImageFn(bridge)) / panel.set("get", object : ...)
_SET_RE = re.compile(r'\b(?:bot|panel)\.set\("([A-Za-z_][A-Za-z0-9_]*)"\s*,\s*([A-Za-z_][A-Za-z0-9_]*)')
_LUAOPTS_READERS = ("str", "int", "float", "bool")
# 这三个 reader 读的键写死在 LuaOpts.kt 里
_LUAOPTS_IMPLIED = {"roi": "roi", "frac": "frac", "colorPoints": "points"}
_OPTS_FUN_RE = re.compile(r"\bfun\s+(\w+)\s*\([^)]*opts:\s*Map<String[^)]*\)")
_CALL_NAME_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_BRIDGE_CALL_RE = re.compile(r"\bbridge\.(\w+)\s*\(")
_ROW_SET_RE = re.compile(r'\bt\.set\("([A-Za-z_][A-Za-z0-9_]*)"')
_LUA_API_TOKEN_RE = re.compile(r"\b(bot|panel)\.([A-Za-z_][A-Za-z0-9_]*)")
_TABLE_OPEN = "val bot = LuaTable()"
_PANEL_OPEN = "val panel = LuaTable()"

# 调用 lua_snippets 片段生成器时，按参数名给的占位实参
_DUMMY_ARGS: dict[str, Any] = {
    "bgr": (255, 0, 0),
    "template_path": "image/tpl.png",
    "target": "目标文字",
    "model": "models/ui.onnx",
    "points": [(0, 0, (255, 0, 0)), (6, 4, (0, 255, 0))],
    "roi": (0, 0, 640, 480),
    "frac": (0.5, 0.5),
    "x": 10,
    "y": 20,
    "x1": 10,
    "y1": 20,
    "x2": 30,
    "y2": 40,
    "msg": "hello",
    "seconds": 1,
    "path": "image/tpl.png",
}


class ParityError(RuntimeError):
    """源码结构与解析器假设不再吻合（改名、括号不配平、找不到函数等）。"""


# ------------------------------------------------------------------ Kotlin 扫描


def _skip_string(text: str, i: int) -> int:
    quote = text[i]
    i += 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return i


def _skip_noise(text: str, i: int) -> int:
    """跳过字符串字面量与行注释，返回下一个真实字符的下标。"""
    while i < len(text):
        if text[i] in '"\'':
            i = _skip_string(text, i)
        elif text.startswith("//", i):
            nl = text.find("\n", i)
            i = len(text) if nl < 0 else nl + 1
        else:
            return i
    return i


def _balanced(text: str, open_idx: int) -> tuple[int, int]:
    """返回 `text[open_idx] == '('` 对应括号的内部区间。"""
    depth = 0
    i = open_idx
    while i < len(text):
        ch = _skip_noise(text, i)
        if ch >= len(text):
            break
        i = ch
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return open_idx + 1, i
        i += 1
    raise ParityError(f"括号不配平，起始处：{text[open_idx:open_idx + 60]!r}")


def _block(text: str, brace_idx: int) -> tuple[int, int]:
    """返回 `text[brace_idx] == '{'` 对应花括号的内部区间。"""
    depth = 0
    i = brace_idx
    while i < len(text):
        ch = _skip_noise(text, i)
        if ch >= len(text):
            break
        i = ch
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return brace_idx + 1, i
        i += 1
    raise ParityError(f"花括号不配平，起始处：{text[brace_idx:brace_idx + 60]!r}")


def _split_args(text: str, start: int, end: int) -> list[str]:
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    i = start
    while i < end:
        ch = text[i]
        if ch in '"\'':
            j = min(_skip_string(text, i), end)
            buf.append(text[i:j])
            i = j
            continue
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]


def _string_literal(part: str) -> str | None:
    part = part.strip()
    if len(part) >= 2 and part[0] == '"' and part[-1] == '"':
        return part[1:-1]
    return None


def luaopts_keys(text: str) -> set[str]:
    """收集一段 Kotlin 里 `LuaOpts.*` 实际读到的选项键。"""
    keys: set[str] = set()
    for m in re.finditer(r"\bLuaOpts\.(\w+)\s*\(", text):
        reader = m.group(1)
        if reader in _LUAOPTS_IMPLIED:
            keys.add(_LUAOPTS_IMPLIED[reader])
            continue
        if reader not in _LUAOPTS_READERS:
            continue
        start, end = _balanced(text, m.end() - 1)
        parts = _split_args(text, start, end)
        if len(parts) >= 2:
            key = _string_literal(parts[1])
            if key:
                keys.add(key)
    return keys


def _class_body(src: str, cls: str) -> str:
    m = re.search(r"\bclass\s+%s\b" % re.escape(cls), src)
    if not m:
        raise ParityError(f"找不到 class {cls}")
    brace = _skip_noise(src, src.find("{", m.end()))
    start, end = _block(src, brace)
    return src[start:end]


def _binding_body(src: str, set_match: re.Match[str]) -> str:
    """bot.set/panel.set 第二项可能是类名，也可能是内联 `object : OneArgFunction()`。"""
    cls = set_match.group(2)
    if cls == "object":
        brace = _skip_noise(src, src.find("{", set_match.end()))
        start, end = _block(src, brace)
        return src[start:end]
    return _class_body(src, cls)


def _fun_bodies(src: str, fn: str) -> list[str]:
    """同名重载全部收进（AutoScriptBridge 里如 findColorBgr 会转发）。"""
    bodies: list[str] = []
    for m in re.finditer(r"\bfun\s+%s\s*\(" % re.escape(fn), src):
        _paren_start, paren_end = _balanced(src, m.end() - 1)
        brace = src.find("{", paren_end)
        if brace < 0:
            continue
        nxt = _skip_noise(src, brace)
        if src[nxt:nxt + 1] != "{":
            continue  # 表达式体函数
        start, end = _block(src, nxt)
        bodies.append(src[start:end])
    return bodies


def _opts_taking_bodies(src: str) -> dict[str, str]:
    """本文件内所有「签名含 opts: Map<String…」」的函数体，用于递归并入 helper。"""
    out: dict[str, str] = {}
    for m in _OPTS_FUN_RE.finditer(src):
        bodies = _fun_bodies(src, m.group(1))
        if bodies:
            out[m.group(1)] = "\n".join(bodies)
    return out


def attribute_text(set_match: re.Match[str], bindings_src: str, bridge_src: str) -> str:
    """把某个 Lua 绑定的全部相关源码并成一段文本。

    归属链：`绑定体（Fn 类或内联 object）` → 其中每个 `bridge.<callee>(` 的函数体 →
    该函数体内调用的、签名带 `opts: Map<String` 的私有 helper（resolveModel 等）。
    """
    body = _binding_body(bindings_src, set_match)
    text = body
    seen: set[str] = set()
    helpers = _opts_taking_bodies(bridge_src)
    for callee in sorted(set(_BRIDGE_CALL_RE.findall(body))):
        bodies = _fun_bodies(bridge_src, callee)
        if not bodies:
            raise ParityError(
                f"{set_match.group(1)}() 调用 bridge.{callee}()，但 {BRIDGE.name} 里找不到该函数体"
            )
        merged = "\n".join(bodies)
        text += "\n" + merged
        for helper in sorted(set(_CALL_NAME_RE.findall(merged))):
            if helper in helpers and helper not in seen:
                seen.add(helper)
                text += "\n" + helpers[helper]
    return text


def device_bindings(bindings_src: str, bridge_src: str) -> dict[str, set[str]]:
    """{"bot.findImage": {设备端读到的 opts 键}, …}（panel.* 也在内）。"""
    out: dict[str, set[str]] = {}
    for m in _SET_RE.finditer(bindings_src):
        prefix = bindings_src[: m.start()]
        table = "panel" if prefix.rfind(_PANEL_OPEN) > prefix.rfind(_TABLE_OPEN) else "bot"
        full = f"{table}.{m.group(1)}"
        if full in out:
            raise ParityError(f"设备端重复注册 {full}")
        out[full] = luaopts_keys(attribute_text(m, bindings_src, bridge_src))
    return out


def device_detection_fields(bindings_src: str) -> set[str]:
    m = re.search(r"\bprivate fun detectionsToLua\b", bindings_src)
    if not m:
        raise ParityError(f"{LUA_BINDINGS.name} 里找不到 detectionsToLua")
    brace = _skip_noise(bindings_src, bindings_src.find("{", m.end()))
    start, end = _block(bindings_src, brace)
    return set(_ROW_SET_RE.findall(bindings_src[start:end]))


# ------------------------------------------------------------------ 契约对账


def check_device(entries: Mapping[str, Any]) -> list[str]:
    """契约 vs 设备端：名字集合、选项键、检测行字段。"""
    for path in (LUA_BINDINGS, BRIDGE):
        if not path.is_file():
            raise ParityError(f"找不到设备端源码：{path}")
    bindings_src = LUA_BINDINGS.read_text(encoding="utf-8")
    bridge_src = BRIDGE.read_text(encoding="utf-8")
    device = device_bindings(bindings_src, bridge_src)
    issues: list[str] = []

    contract_apk = {e.name for e in entries.values() if e.on_apk}
    for name in sorted(contract_apk - set(device)):
        issues.append(f"契约标了 apk 可用，但设备端未注册：{name}")
    for name in sorted(set(device) - contract_apk):
        issues.append(f"设备端注册了，但契约没有（或 availability 缺 apk）：{name}")

    for name in sorted(set(device) & contract_apk):
        entry = entries[name]
        read = device[name]
        declared = {o.key for o in entry.opts}
        for key in sorted(read - declared):
            issues.append(f"{name}: 设备端读 opts.{key}，契约未声明")
        for key in sorted(declared - read):
            issues.append(f"{name}: 契约声明 opts.{key}，设备端不读（sides 已过时）")
        for opt in entry.opts:
            if "apk" in opt.sides and opt.key not in read:
                issues.append(f"{name}: 契约声明 opts.{opt.key} 支持 apk，设备端却读不到")
        if entry.opts and entry.opts_index is None:
            issues.append(f"{name}: 契约有 opts 段，但 args 里没有名为 opts 的参数")
        if read and entry.opts_index is None:
            issues.append(f"{name}: 设备端读了 opts 键，但契约 args 里没有 opts 表参数")

    entry = entries.get("bot.yoloDetect")
    if entry is None:
        raise ParityError("契约里没有 bot.yoloDetect")
    always = list(entry.returns.get("item_fields") or [])
    conditional = list(entry.returns.get("optional_item_fields") or [])
    actual = device_detection_fields(bindings_src)
    for key in sorted(set(always) - actual):
        issues.append(f"bot.yoloDetect: 契约 item_fields 有 {key}，detectionsToLua 未写")
    for key in sorted(actual - set(always) - set(conditional)):
        issues.append(f"bot.yoloDetect: detectionsToLua 写了 {key}，契约 item_fields 未声明")
    return issues


# -------------------------------------------------------------------- PC 端对账

PC_BOT = REPO_ROOT / "studio/runtime/pc_bot.py"
PANEL_STATE = REPO_ROOT / "studio/runtime/panel_state.py"

_PY_DEF_RE = re.compile(r"^    def\s+(\w+)\s*\(", re.M)
_PY_OPTS_FUN_RE = re.compile(r"^    def\s+(\w+)\(self,\s*opts:\s*dict", re.M)
_PY_SELF_CALL_RE = re.compile(r"\bself\.(\w+)\s*\(")
# PcBot 用三个小 reader 读 opts，键名总在第二个实参
_PY_READER_RE = re.compile(r'self\._(?:float|int|bool)\(\s*\w+\s*,\s*"([a-z_][a-z0-9_]*)"')
_PY_GET_RE = re.compile(r'\b\w+\.get\("([a-z_][a-z0-9_]*)"')
_PY_FOR_KEYS_RE = re.compile(r"for\s+\w+\s+in\s+\(([^)]*)\)")
_PY_STR_RE = re.compile(r'"([a-z_][a-z0-9_]*)"')
# 这两个 helper 读的键名写死在 lua_values.py 里
_PY_IMPLIED = (("roi_tuple(", "roi"), ("frac_pair(", "frac"))


def _py_def_bodies(src: str, name: str) -> list[str]:
    """按 8 空格缩进收 `def name(...)` 的函数体（重载全收）。"""
    lines = src.splitlines()
    pat = re.compile(r"^    def\s+%s\s*\(" % re.escape(name))
    bodies: list[str] = []
    for i, line in enumerate(lines):
        if not pat.match(line):
            continue
        body = [line]
        for nxt in lines[i + 1 :]:
            if nxt.strip() and not nxt.startswith("        "):
                break
            body.append(nxt)
        bodies.append("\n".join(body))
    return bodies


def pc_methods(src: str) -> dict[str, tuple[str, str]]:
    """{方法名: (直接方法体, 并入 opts helper 后的全量文本)}，helper 只并一层。"""
    helpers = {m.group(1) for m in _PY_OPTS_FUN_RE.finditer(src)}
    out: dict[str, tuple[str, str]] = {}
    for m in _PY_DEF_RE.finditer(src):
        name = m.group(1)
        bodies = _py_def_bodies(src, name)
        if not bodies:
            raise ParityError(f"解析不到方法 {name}() 的函数体")
        head = "\n".join(bodies)
        text = head
        for callee in sorted(set(_PY_SELF_CALL_RE.findall(head))):
            if callee in helpers and callee != name:
                text += "\n" + "\n".join(_py_def_bodies(src, callee))
        out[name] = (head, text)
    return out


def pc_opts_keys(text: str) -> set[str]:
    keys = set(_PY_READER_RE.findall(text)) | set(_PY_GET_RE.findall(text))
    for group in _PY_FOR_KEYS_RE.findall(text):
        keys |= set(_PY_STR_RE.findall(group))
    for token, key in _PY_IMPLIED:
        if token in text:
            keys.add(key)
    return keys


def check_pc(entries: Mapping[str, Any]) -> list[str]:
    """契约 vs PC 实现：pc 方法存在性 + opts 键的双向抽查。

    正向（契约声明支持 pc → 必须读到）看全量文本；反向（读到 → 必须声明）只看直接
    方法体，避免把 helper 里读 project.json 的配置键误报成 opts。
    """
    for path in (PC_BOT, PANEL_STATE):
        if not path.is_file():
            raise ParityError(f"找不到 PC 端源码：{path}")
    bot_methods = pc_methods(PC_BOT.read_text(encoding="utf-8"))
    panel_methods = pc_methods(PANEL_STATE.read_text(encoding="utf-8"))
    if not bot_methods:
        raise ParityError(f"{PC_BOT.name} 里解析不出任何方法，校验已失效")
    issues: list[str] = []

    for name, entry in sorted(entries.items()):
        if not entry.on_pc:
            continue
        pool = bot_methods if entry.table == "bot" else panel_methods
        if entry.pc not in pool:
            where = PC_BOT.name if entry.table == "bot" else PANEL_STATE.name
            issues.append(f"{name}: 契约说 PC 方法是 {entry.pc}()，但 {where} 里没有")
            continue
        if not entry.opts:
            continue
        direct, full = pool[entry.pc]
        read_direct = pc_opts_keys(direct)
        read_anywhere = pc_opts_keys(full)
        declared = {o.key for o in entry.opts}
        legal = set(entry.side_opts("pc"))
        for key in sorted(legal - read_anywhere):
            issues.append(f"{name}: 契约声明 opts.{key} 支持 pc，但 {entry.pc}() 读不到")
        for key in sorted(read_direct & (declared - legal)):
            issues.append(f"{name}: 契约标 opts.{key} 仅设备端，但 PC 的 {entry.pc}() 读了它")
        for key in sorted(read_direct - declared):
            issues.append(f"{name}: PC 的 {entry.pc}() 读了 opts.{key}，契约未声明")
    return issues


# ---------------------------------------------------------- 工具箱 / 可插入片段


def _table_keys(expr: str) -> set[str]:
    """只取顶层表构造的 `key =`；roi/points 的位置数组不含键。"""
    expr = expr.strip()
    if not (expr.startswith("{") and expr.endswith("}")):
        return set()
    inner = expr[1:-1]
    keys: set[str] = set()
    for part in _split_args(inner, 0, len(inner)):
        m = re.match(r"^([A-Za-z_]\w*)\s*=(?!=)", part.strip())
        if m:
            keys.add(m.group(1))
    return keys


def lua_call_opts(text: str) -> dict[str, set[str]]:
    """从 Lua 源码片段抽 `{ "bot.findImage": {"threshold", …} }`。"""
    found: dict[str, set[str]] = {}
    for m in _LUA_API_TOKEN_RE.finditer(text):
        full = f"{m.group(1)}.{m.group(2)}"
        i = m.end()
        while i < len(text) and text[i] in " \t":
            i += 1
        if i >= len(text) or text[i] != "(":
            continue
        start, end = _balanced(text, i)
        keys = found.setdefault(full, set())
        for part in _split_args(text, start, end):
            keys |= _table_keys(part)
    return found


def _syntax_apis(syntax: str) -> dict[str, int | None]:
    """`bot.swipe(x1,y1,x2,y2 [,duration_ms])` → {"bot.swipe": 5}"""
    out: dict[str, int | None] = {}
    for m in _LUA_API_TOKEN_RE.finditer(syntax):
        full = f"{m.group(1)}.{m.group(2)}"
        i = m.end()
        while i < len(syntax) and syntax[i] in " \t":
            i += 1
        if i >= len(syntax) or syntax[i] != "(":
            out.setdefault(full, None)
            continue
        start, end = _balanced(syntax, i)
        body = syntax[start:end].replace("[", "").replace("]", "").strip()
        out[full] = len(_split_args(body, 0, len(body))) if body else 0
    return out


def check_catalog(entries: Mapping[str, Any]) -> list[str]:
    """工具箱条目：名字存在于契约、syntax 元数一致、snippet 的 opts 键合法。"""
    import sys

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from studio.services.bot_command_catalog import all_commands

    issues: list[str] = []
    for cmd in all_commands():
        label = f"catalog {cmd.id}"
        for api, arity in sorted(_syntax_apis(cmd.syntax).items()):
            entry = entries.get(api)
            if entry is None:
                issues.append(f"{label}: syntax 写了契约里没有的 {api}()")
                continue
            if entry.internal:
                issues.append(f"{label}: syntax 暴露了内部名字 {api}")
            if arity is not None and arity != len(entry.args):
                issues.append(
                    f"{label}: syntax {api} 写了 {arity} 个参数，契约是 {len(entry.args)} 个"
                )
        for api, keys in sorted(lua_call_opts(cmd.snippet).items()):
            entry = entries.get(api)
            if entry is None:
                issues.append(f"{label}: snippet 调用契约里没有的 {api}()")
                continue
            if entry.internal:
                issues.append(f"{label}: snippet 暴露了内部名字 {api}")
            declared = {o.key for o in entry.opts}
            for key in sorted(keys - declared):
                issues.append(f"{label}: {api} 的 snippet 用了契约未声明的 opts.{key}")
            if keys and entry.opts_index is None:
                issues.append(f"{label}: {api} 的 snippet 传了表键，但契约该函数无 opts")
    return issues


def _snippet_call_kwargs(fn: Any) -> list[dict[str, Any]]:
    """为片段生成器造两组实参：默认态 + 全开启态（覆盖条件分支里追加的 opts 键）。"""
    import inspect

    sig = inspect.signature(fn)
    positional: dict[str, Any] = {}
    on: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if param.default is param.empty:
            if name not in _DUMMY_ARGS:
                raise ParityError(
                    f"lua_snippets.{fn.__name__}: 出现未知必填参数 {name}，无法调用校验"
                )
            positional[name] = _DUMMY_ARGS[name]
            continue
        if name in _DUMMY_ARGS:
            on[name] = _DUMMY_ARGS[name]
        elif isinstance(param.default, bool):
            on[name] = True
        elif isinstance(param.default, (int, float)):
            on[name] = 1
        elif isinstance(param.default, str):
            on[name] = "x"
    return [positional, {**positional, **on}]


def check_snippets(entries: Mapping[str, Any]) -> list[str]:
    """调用 `lua_snippets.py` 的片段生成器，校验**真正产出**的 Lua 文本。

    不能只扫源码里的字符串常量：opts 键分散在多个 f-string 片段里（如
    `f"stable_frames = {stable_frames}"`），扫常量会整段漏掉守卫。
    """
    import inspect

    import studio.services.lua_snippets as snippets

    issues: list[str] = []
    builders = [
        (name, obj)
        for name, obj in vars(snippets).items()
        if inspect.isfunction(obj)
        and obj.__module__ == snippets.__name__
        and not name.startswith("_")
    ]
    if not builders:
        raise ParityError("lua_snippets 里找不到任何公开片段生成器，校验已失效")
    for name, fn in builders:
        for kwargs in _snippet_call_kwargs(fn):
            try:
                code = fn(**kwargs)
            except Exception as exc:  # noqa: BLE001 - 调用不进去必须暴露，不能静默跳过
                issues.append(
                    f"lua_snippets.{name}: 无法调用以校验产出（{type(exc).__name__}: {exc}）"
                )
                continue
            if not isinstance(code, str):
                issues.append(f"lua_snippets.{name}: 未返回 Lua 源码字符串")
                continue
            for api, keys in sorted(lua_call_opts(code).items()):
                entry = entries.get(api)
                if entry is None:
                    issues.append(f"lua_snippets.{name}: 产出契约里没有的 {api}()")
                    continue
                declared = {o.key for o in entry.opts}
                for key in sorted(keys - declared):
                    issues.append(
                        f"lua_snippets.{name}: {api} 产出用了契约未声明的 opts.{key}"
                    )
    return issues


# ------------------------------------------------------------------------ 文档


def check_docs(entries: Mapping[str, Any], doc_path: Path | None = None) -> list[str]:
    """LUA.md 与契约的名字集合双向一致（只到名字级别，散文仍手写）。"""
    path = doc_path or REPO_ROOT / "docs/LUA.md"
    if not path.is_file():
        raise ParityError(f"找不到文档：{path}")
    text = path.read_text(encoding="utf-8")
    mentioned = {f"{m.group(1)}.{m.group(2)}" for m in _LUA_API_TOKEN_RE.finditer(text)}
    issues: list[str] = []
    for name in sorted(mentioned):
        if name not in entries:
            issues.append(f"LUA.md 写了 {name}()，契约里没有这个名字")
    for entry in entries.values():
        if not entry.internal and entry.name not in mentioned:
            issues.append(f"{entry.name} 在契约里，但 LUA.md 没有提到")
    return issues


def all_issues(
    entries: Mapping[str, Any],
    checks: Iterable[str] = ("device", "pc", "catalog", "snippets", "docs"),
) -> list[str]:
    runners = {
        "device": check_device,
        "pc": check_pc,
        "catalog": check_catalog,
        "snippets": check_snippets,
        "docs": check_docs,
    }
    issues: list[str] = []
    for name in checks:
        issues.extend(runners[name](entries))
    return issues
