"""`contract/lua_api.json` 的加载、自校验与返回 marshal。

契约是 bot.* / panel.* 的单一来源：本模块只负责读它、验它、把 Python 侧返回值
marshal 成 Lua 值；真正的注册在 `lua_runner.install_bot()`。设备端与文档、工具箱的
对账在 `tools/lua_contract_check.py`（由 tests/test_lua_contract_parity.py 调用）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contract" / "lua_api.json"

ARG_TYPES = ("string", "int", "number", "bool", "table", "function")
OPT_TYPES = ("string", "int", "number", "bool", "roi", "frac", "color_points", "table")
RETURN_KINDS = (
    "none",
    "bool",
    "number",
    "string",
    "tuple",
    "table",
    "table_or_nil",
    "array_of",
)
SIDES = ("pc", "apk")


class ContractError(RuntimeError):
    """契约自身不合法（结构、词表或字段冲突）。"""


@dataclass(frozen=True)
class ApiArg:
    name: str
    type: str
    optional: bool = False


@dataclass(frozen=True)
class ApiOpt:
    key: str
    type: str
    sides: tuple[str, ...] = SIDES
    default: Any = None
    has_default: bool = False
    default_from: str = ""
    note: str = ""


@dataclass(frozen=True)
class ApiEntry:
    name: str
    pc: str = ""
    availability: tuple[str, ...] = ()
    pc_missing: str = "raise"
    pc_error: str = ""
    internal: bool = False
    args: tuple[ApiArg, ...] = ()
    opts: tuple[ApiOpt, ...] = ()
    returns: Mapping[str, Any] = field(default_factory=dict)

    @property
    def table(self) -> str:
        return self.name.split(".", 1)[0]

    @property
    def lua_name(self) -> str:
        return self.name.split(".", 1)[1]

    @property
    def opts_index(self) -> int | None:
        for i, arg in enumerate(self.args):
            if arg.name == "opts":
                return i
        return None

    def side_opts(self, side: str) -> dict[str, ApiOpt]:
        return {o.key: o for o in self.opts if side in o.sides}

    @property
    def on_pc(self) -> bool:
        return "pc" in self.availability

    @property
    def on_apk(self) -> bool:
        return "apk" in self.availability


def _dup_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    dups: list[str] = []
    for key, _ in pairs:
        if key in seen:
            dups.append(key)
        seen.add(key)
    if dups:
        raise ContractError(f"契约存在重复键：{sorted(set(dups))}")
    return dict(pairs)


_CACHE: dict[Path, dict[str, ApiEntry]] = {}


def load(path: Path | str | None = None, *, use_cache: bool = True) -> dict[str, ApiEntry]:
    """读取并自校验契约，返回 {name: ApiEntry}（按名字典序无依赖）。"""
    p = CONTRACT_PATH if path is None else Path(path)
    if use_cache and p in _CACHE:
        return _CACHE[p]
    if not p.is_file():
        raise ContractError(f"缺少契约文件：{p}")
    raw = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=_dup_hook)
    issues = validate(raw)
    if issues:
        raise ContractError("契约校验失败：\n  - " + "\n  - ".join(issues))
    entries = {str(k): _entry(str(k), v) for k, v in (raw.get("api") or {}).items()}
    if use_cache:
        _CACHE[p] = entries
    return entries


def lookup(entries: Mapping[str, ApiEntry], name: str) -> ApiEntry:
    try:
        return entries[name]
    except KeyError as exc:
        raise ContractError(f"契约中没有 {name}") from exc


def _entry(name: str, spec: Any) -> ApiEntry:
    if not isinstance(spec, Mapping):
        raise ContractError(f"{name} 的定义不是对象")
    args = tuple(
        ApiArg(str(a.get("name") or ""), str(a.get("type") or ""), bool(a.get("optional")))
        for a in (spec.get("args") or [])
    )
    opts = tuple(
        ApiOpt(
            key=str(key),
            type=str((val or {}).get("type") or ""),
            sides=tuple((val or {}).get("sides") or SIDES),
            default=(val or {}).get("default"),
            has_default="default" in (val or {}),
            default_from=str((val or {}).get("default_from") or ""),
            note=str((val or {}).get("note") or ""),
        )
        for key, val in (spec.get("opts") or {}).items()
    )
    return ApiEntry(
        name=name,
        pc=str(spec.get("pc") or ""),
        availability=tuple(spec.get("availability") or ()),
        pc_missing=str(spec.get("pc_missing") or "raise"),
        pc_error=str(spec.get("pc_error") or ""),
        internal=bool(spec.get("internal")),
        args=args,
        opts=opts,
        returns=dict(spec.get("returns") or {}),
    )


def validate(raw: Mapping[str, Any]) -> list[str]:
    """结构自校验：返回问题列表（空 = 合法）。不抛异常，便于测试逐项断言。"""
    issues: list[str] = []
    if not isinstance(raw, Mapping):
        return ["契约根节点不是对象"]
    if raw.get("version") != 1:
        issues.append(f"version 须为 1，实际 {raw.get('version')!r}")
    api = raw.get("api")
    if not isinstance(api, Mapping) or not api:
        issues.append("缺少非空的 api 段")
        return issues
    for name, spec in api.items():
        issues.extend(_validate_entry(str(name), spec))
    return issues


def _validate_entry(name: str, spec: Any) -> list[str]:
    issues: list[str] = []

    def bad(msg: str) -> None:
        issues.append(f"{name}: {msg}")

    table, _, lua_name = name.partition(".")
    if table not in ("bot", "panel") or not lua_name:
        bad("名字须为 bot.xxx / panel.xxx")
    if not isinstance(spec, Mapping):
        bad("定义不是对象")
        return issues

    availability = spec.get("availability")
    if not isinstance(availability, Sequence) or isinstance(availability, str) or not availability:
        bad("availability 须为非空数组")
        avail: list[str] = []
    else:
        avail = [str(a) for a in availability]
        unknown = [a for a in avail if a not in SIDES]
        if unknown:
            bad(f"availability 含未知端 {unknown}")
        if len(set(avail)) != len(avail):
            bad("availability 有重复项")

    if "pc" in avail:
        if not str(spec.get("pc") or ""):
            bad("availability 含 pc 时必须给出 pc 方法名")
    else:
        if "pc" in spec:
            bad("设备专有名字不应有 pc 字段")
        missing = str(spec.get("pc_missing") or "raise")
        if missing not in ("nil", "raise"):
            bad(f"pc_missing 须为 nil/raise，实际 {missing!r}")
        if missing == "raise" and not str(spec.get("pc_error") or "").strip():
            bad('pc_missing="raise" 需要 pc_error 文案')

    args = spec.get("args")
    if not isinstance(args, Sequence) or isinstance(args, str):
        bad("args 须为数组（无参时给 []）")
        args = []
    seen_arg: set[str] = set()
    for i, arg in enumerate(args):
        if not isinstance(arg, Mapping):
            bad(f"args[{i}] 不是对象")
            continue
        aname = str(arg.get("name") or "")
        atype = str(arg.get("type") or "")
        if not aname:
            bad(f"args[{i}] 缺少 name")
        elif aname in seen_arg:
            bad(f"args[{i}] 名字 {aname} 重复")
        else:
            seen_arg.add(aname)
        if atype not in ARG_TYPES:
            bad(f"args[{i}] 类型 {atype!r} 不在词表 {list(ARG_TYPES)}")
        if bool(arg.get("optional")) and i != len(args) - 1:
            bad(f"args[{i}] 只有末位参数可标 optional")

    opts = spec.get("opts") or {}
    if not isinstance(opts, Mapping):
        bad("opts 须为对象")
        opts = {}
    elif opts and "opts" not in seen_arg:
        bad("声明了 opts 段但 args 里没有名为 opts 的表参数")
    for key, val in opts.items():
        if not _is_opt_key(str(key)):
            bad(f"opts.{key} 键名须为 snake_case")
        if not isinstance(val, Mapping):
            bad(f"opts.{key} 定义不是对象")
            continue
        otype = str(val.get("type") or "")
        if otype not in OPT_TYPES:
            bad(f"opts.{key} 类型 {otype!r} 不在词表 {list(OPT_TYPES)}")
        if "default" in val and "default_from" in val:
            bad(f"opts.{key} 的 default 与 default_from 互斥")
        sides = val.get("sides")
        if sides is not None:
            if not isinstance(sides, Sequence) or isinstance(sides, str) or not sides:
                bad(f"opts.{key}.sides 须为非空数组")
            else:
                unknown = [s for s in sides if str(s) not in SIDES]
                if unknown:
                    bad(f"opts.{key}.sides 含未知端 {unknown}")
                if len(set(sides)) == len(sides) and set(sides) == set(SIDES):
                    bad(f"opts.{key}.sides 两端齐全时应省略")

    ret = spec.get("returns")
    if not isinstance(ret, Mapping):
        bad("缺少 returns 段")
    else:
        kind = str(ret.get("kind") or "")
        if kind not in RETURN_KINDS:
            bad(f"returns.kind {kind!r} 不在词表 {list(RETURN_KINDS)}")
        if kind == "tuple":
            items = ret.get("items")
            if not isinstance(items, Sequence) or isinstance(items, str) or not items:
                bad("tuple 返回需要 items")
            else:
                for it in items:
                    if str(it) not in ("int", "number"):
                        bad(f"tuple items 只支持 int/number，实际 {it!r}")
        if kind == "array_of" and not (ret.get("item_fields") or []):
            bad("array_of 返回需要 item_fields")
        if kind in ("table", "table_or_nil") and "item_fields" in ret:
            bad(f"{kind} 返回不应带 item_fields")

    if bool(spec.get("internal")) and not lua_name.startswith("_"):
        bad("internal 名字的末段须以下划线开头")
    return issues


def _is_opt_key(key: str) -> bool:
    return (
        len(key) > 1
        and key[0].islower()
        and all(c.islower() or c.isdigit() or c == "_" for c in key)
        and not key.endswith("_")
    )


# --------------------------------------------------------------------------- marshal


def marshal(lua: Any, value: Any, spec: Mapping[str, Any]) -> Any:
    """把 Python 返回值按 returns 段转成 Lua 侧形状。

    设备端（LuaJ）返回的是真 Lua 表，所以 PC 也必须用 `lua.table_from` 造表：
    直接返回 Python list/dict 在 lupa 里是 POBJECT userdata，`#t`/`ipairs`/`pairs`
    全部失效且索引从 0 开始。
    """
    kind = str((spec or {}).get("kind") or "none")
    if kind == "none":
        return None
    if value is None:
        return None
    if kind == "bool":
        return bool(value)
    if kind == "number":
        return value
    if kind == "string":
        return str(value)
    if kind == "tuple":
        items = list((spec or {}).get("items") or [])
        seq = list(value) if not isinstance(value, (int, float, str)) else [value]
        if len(seq) < len(items):
            raise ContractError(f"tuple 返回只有 {len(seq)} 个值，契约要求 {len(items)}")
        return tuple(coerce(v, str(t)) for v, t in zip(seq, items))
    fields = list((spec or {}).get("fields") or [])
    if fields and isinstance(value, (list, tuple)) and not isinstance(value, Mapping):
        # 契约声明了具名字段而 Python 侧返回位置元组（如 time_range -> (start, end)）
        if len(value) < len(fields):
            raise ContractError(f"返回只有 {len(value)} 个值，契约要求字段 {fields}")
        value = {name: value[i] for i, name in enumerate(fields)}
    return _to_lua(lua, value)


def coerce(value: Any, atype: str) -> Any:
    """按契约声明的参数类型强转（lupa 交回来的是 Python 标量或 Lua 代理）。"""
    if atype == "int":
        return int(value)
    if atype == "number":
        return value
    if atype == "bool":
        return bool(value)
    if atype == "string":
        # 设备端 tojstring 把 Lua boolean 变成 "true"/"false"，Python 的 str(True)
        # 是 "True"，会让 panel.get 读回的值两端不一致。
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
    return value


def _to_lua(lua: Any, value: Any) -> Any:
    """递归把 list/tuple/dict 转成真 Lua 表（1 基数组 / 哈希表）。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return lua.table_from({str(k): _to_lua(lua, v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return lua.table_from([_to_lua(lua, v) for v in value])
    return value
