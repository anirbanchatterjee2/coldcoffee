"""Primitive library — verified, reusable operations agents compose.

Each primitive declares:
  - ``inputs``: ordered ``(name, ir_type, required)`` tuples,
  - ``output``: IR type,
  - ``category`` / ``desc``: for cataloguing and the semantic debugger,
  - ``func(ctx, args, params)``: the implementation.

``ctx`` carries engine state (``ctx.state``, ``ctx.events``) so stateful
primitives (`state_get`/`state_set`/`emit`) stay explicit and testable.
Pure primitives must not mutate ``ctx.state``.

Conventions:
  - Money is represented as ``float`` (dollars) in v0.1 but typed `money`
    so validators keep it distinct from `float`.  Exact decimal arithmetic
    is future work (see docs/IR_SPEC.md).
  - Errors are raised as ``PrimitiveError`` (domain failure) or
    ``PrimitiveTypeError`` (bad operand types).  Both halt execution and
    surface in the trace with a human repair hint.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from .types import NUMERIC


class PrimitiveError(Exception):
    """Domain failure (e.g. validation failed, out of stock)."""

    def __init__(self, message: str, hint: str = ""):
        super().__init__(message)
        self.hint = hint


class PrimitiveTypeError(PrimitiveError):
    """An operand had the wrong runtime type."""


@dataclass
class Context:
    state: dict = field(default_factory=dict)
    events: list = field(default_factory=list)


@dataclass(frozen=True)
class Primitive:
    name: str
    inputs: tuple  # tuple[(name, type, required)]
    output: str
    category: str
    desc: str
    func: Callable[..., Any]


def _num(args: dict, key: str) -> float:
    v = args[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise PrimitiveTypeError(f"'{key}' must be numeric, got {type(v).__name__}: {v!r}",
                                 hint=f"Ensure '{key}' is a number (int/float/money).")
    return v


def _num2(args: dict, a: str = "a", b: str = "b"):
    return _num(args, a), _num(args, b)


def _text(args: dict, key: str) -> str:
    if not isinstance(args[key], str):
        raise PrimitiveTypeError(f"'{key}' must be str, got {type(args[key]).__name__}",
                                 hint=f"Convert '{key}' with to_str first.")
    return args[key]


def _truth(args: dict, key: str = "v") -> bool:
    if not isinstance(args[key], bool):
        raise PrimitiveTypeError(f"'{key}' must be bool, got {type(args[key]).__name__}: {args[key]!r}",
                                 hint="Use a comparison (eq/lt/...) or validate_email to produce a bool.")
    return args[key]


def _lst(args: dict, key: str = "items") -> list:
    if not isinstance(args[key], list):
        raise PrimitiveTypeError(f"'{key}' must be list, got {type(args[key]).__name__}",
                                 hint=f"Ensure '{key}' is a list.")
    return args[key]


# --- arithmetic -----------------------------------------------------------

def _add(ctx, args, params):
    a, b = _num2(args)
    return a + b


def _sub(ctx, args, params):
    a, b = _num2(args)
    return a - b


def _mul(ctx, args, params):
    a, b = _num2(args)
    return a * b


def _div(ctx, args, params):
    a, b = _num2(args)
    if b == 0:
        raise PrimitiveError("Division by zero.", hint="Check the divisor is non-zero, or guard with select/coalesce.")
    return a / b


def _mod(ctx, args, params):
    a, b = _num2(args)
    if b == 0:
        raise PrimitiveError("Modulo by zero.", hint="Check the divisor is non-zero.")
    return a % b


def _neg(ctx, args, params):
    return -_num(args, "a")


def _abs(ctx, args, params):
    return abs(_num(args, "a"))


def _clamp(ctx, args, params):
    v = _num(args, "v")
    lo = _num(args, "lo")
    hi = _num(args, "hi")
    return max(lo, min(hi, v))


def _round(ctx, args, params):
    v = _num(args, "v")
    digits = int(params.get("digits", 2))
    return round(v, digits)


def _min_max(which):
    def fn(ctx, args, params):
        a, b = _num2(args)
        return min(a, b) if which == "min" else max(a, b)
    return fn


# --- compare / logic --------------------------------------------------------

def _cmp(op):
    def fn(ctx, args, params):
        a, b = _num2(args, "a", "b") if op not in ("eq", "ne") or isinstance(args.get("a"), (int, float)) and not isinstance(args.get("a"), bool) else (args["a"], args["b"])
        if op == "eq":
            return a == b
        if op == "ne":
            return a != b
        if op == "lt":
            return a < b
        if op == "le":
            return a <= b
        if op == "gt":
            return a > b
        if op == "ge":
            return a >= b
    return fn


def _logic(op):
    def fn(ctx, args, params):
        if op == "not":
            return not _truth(args, "v")
        a, b = _truth(args, "a"), _truth(args, "b")
        return (a and b) if op == "and" else (a or b)
    return fn


def _select(ctx, args, params):
    return args["then"] if _truth(args, "cond") else args["otherwise"]


def _is_null(ctx, args, params):
    return args["v"] is None


def _is_empty(ctx, args, params):
    v = args["v"]
    if v is None:
        return True
    if isinstance(v, (str, list, dict)):
        return len(v) == 0
    return False


def _contains(ctx, args, params):
    return _text(args, "haystack").find(_text(args, "needle")) >= 0


# --- strings ------------------------------------------------------------------

def _concat(ctx, args, params):
    sep = params.get("sep", "")
    return sep.join(_text(args, k) for k in ("a", "b"))


def _upper(ctx, args, params):
    return _text(args, "s").upper()


def _lower(ctx, args, params):
    return _text(args, "s").lower()


def _trim(ctx, args, params):
    return _text(args, "s").strip()


def _len(ctx, args, params):
    v = args["v"]
    if not isinstance(v, (str, list, dict)):
        raise PrimitiveTypeError("'v' must be str/list/map.", hint="Check the value before measuring.")
    return len(v)


def _template(ctx, args, params):
    """``template(text, ...vars)``: the literal ``text`` declares ``{name}``
    placeholders; the engine binds each from ``args``.  This lets agents
    author a confirmation email as one compact node instead of a chain of
    concats.
    """
    text = _text(args, "text")
    out = text
    for key, value in args.items():
        if key == "text":
            continue
        out = out.replace("{" + key + "}", _fmt(value))
    if "{" in out and "}" in out:
        # A placeholder remained unbound — likely a missing arg.
        leftover = re.findall(r"\{(\w+)\}", out)
        if leftover:
            raise PrimitiveError(f"Unbound template placeholders: {leftover}.",
                                 hint="Provide every {name} used in the template as an arg.")
    return out


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _format_money(ctx, args, params):
    return f"{_num(args, 'v'):.2f}"


# --- collections / data -------------------------------------------------------

def _get_field(ctx, args, params):
    m = args["m"]
    if not isinstance(m, dict):
        raise PrimitiveTypeError("'m' must be map.", hint="Use dict_build or ensure the input is a map.")
    field_name = _text(args, "field")
    if field_name not in m:
        if "default" in args and args["default"] is not None:
            return args["default"]
        raise PrimitiveError(f"Missing field '{field_name}' in map {list(m.keys())}.",
                             hint="Check the field name or pass a 'default'.")
    return m[field_name]


def _get_index(ctx, args, params):
    items = _lst(args, "items")
    i = args["i"]
    if isinstance(i, bool) or not isinstance(i, int):
        raise PrimitiveTypeError("'i' must be int.", hint="Use an integer index.")
    if i < 0 or i >= len(items):
        raise PrimitiveError(f"Index {i} out of range (len={len(items)}).", hint="Guard with count + comparison or select.")
    return items[i]


def _count(ctx, args, params):
    return len(_lst(args, "items"))


def _sum_list(ctx, args, params):
    items = _lst(args, "items")
    total = 0.0
    for i, v in enumerate(items):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise PrimitiveTypeError(f"items[{i}] must be numeric, got {v!r}.", hint="Map each item to a number first (e.g. sum_field).")
        total += v
    return total


def _sum_field(ctx, args, params):
    items = _lst(args, "items")
    field_name = _text(args, "field")
    total = 0.0
    for i, item in enumerate(items):
        if not isinstance(item, dict) or field_name not in item:
            raise PrimitiveError(f"items[{i}] missing field '{field_name}'.", hint=f"Ensure every item has '{field_name}'.")
        v = item[field_name]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise PrimitiveTypeError(f"items[{i}]['{field_name}'] must be numeric, got {v!r}.")
        total += v
    return total


def _sum_line_total(ctx, args, params):
    """Sum ``price * qty`` over an order-items list.  The standard
    last-mile primitive for tabulation, kept generic: any map list with
    numeric ``price``/``qty`` fields works."""
    items = _lst(args, "items")
    total = 0.0
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise PrimitiveError(f"items[{i}] must be a map.", hint="Each item must be a map with price/qty.")
        for f in ("price", "qty"):
            if f not in item:
                raise PrimitiveError(f"items[{i}] missing '{f}'.", hint=f"Ensure every item has '{f}'.")
            if isinstance(item[f], bool) or not isinstance(item[f], (int, float)):
                raise PrimitiveTypeError(f"items[{i}]['{f}'] must be numeric, got {item[f]!r}.")
        total += item["price"] * item["qty"]
    return total


def _map_lookup(ctx, args, params):
    m = args["m"]
    if not isinstance(m, dict):
        raise PrimitiveTypeError("'m' must be map.", hint="Ensure the lookup table is a map.")
    key = args["key"]
    if key not in m:
        if "default" in args and args["default"] is not None:
            return args["default"]
        raise PrimitiveError(f"Key {key!r} not in map (keys={list(m.keys())[:10]}).", hint="Pass a default or check the key.")
    return m[key]


def _dict_build(ctx, args, params):
    """Build a map from flat args: ``dict_build(a=…, b=…)`` → ``{a:…, b:…}``."""
    return dict(args)


def _list_build(ctx, args, params):
    names = params.get("order", list(args.keys()))
    return [args[k] for k in names]


def _coalesce(ctx, args, params):
    return args["a"] if args["a"] is not None else args["b"]


# --- validation / business -----------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _require_nonempty(ctx, args, params):
    v = args["v"]
    name = params.get("name", "value")
    if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
        raise PrimitiveError(f"{name} is required and must be non-empty.",
                             hint=f"Provide a non-empty {name} in the inputs.")
    return v


def _validate_email(ctx, args, params):
    email = _text(args, "email")
    if not _EMAIL_RE.match(email):
        raise PrimitiveError(f"Invalid email address: {email!r}.",
                             hint="Expect local@domain.tld with no spaces.")
    return email


def _check_stock(ctx, args, params):
    """Verify every order item has enough stock against ``inventory``
    (a ``sku -> count`` map, typically seeded from ``state``)."""
    items = _lst(args, "items")
    inv = args["inventory"]
    if not isinstance(inv, dict):
        raise PrimitiveTypeError("'inventory' must be map sku->count.", hint="Seed inventory as a map.")
    for i, item in enumerate(items):
        if not isinstance(item, dict) or "sku" not in item or "qty" not in item:
            raise PrimitiveError(f"items[{i}] must have 'sku' and 'qty'.", hint="Provide sku/qty per item.")
        sku, qty = item["sku"], item["qty"]
        if sku not in inv:
            raise PrimitiveError(f"Unknown SKU: {sku!r}.", hint="Check the SKU spelling or extend inventory.")
        if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
            raise PrimitiveError(f"Invalid qty for {sku!r}: {qty!r}.", hint="Qty must be a positive number.")
        if inv[sku] < qty:
            raise PrimitiveError(f"Insufficient stock for {sku!r}: need {qty}, have {inv[sku]}.",
                                 hint="Reduce qty or restock before retrying.")
    return True


def _assert_true(ctx, args, params):
    if not _truth(args, "cond"):
        raise PrimitiveError(params.get("message", "Assertion failed."),
                             hint=params.get("hint", "Re-check the condition leading here."))
    return True


def _fail_if(ctx, args, params):
    if _truth(args, "cond"):
        raise PrimitiveError(params.get("message", "Failed."), hint=params.get("hint", ""))
    return True


# --- conversions -----------------------------------------------------------------

def _to_str(ctx, args, params):
    v = args["v"]
    return "" if v is None else str(v)


def _to_int(ctx, args, params):
    v = args["v"]
    if isinstance(v, bool):
        raise PrimitiveTypeError("Cannot convert bool to int.", hint="Use to_bool's negation explicitly.")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            return int(Decimal(v.strip()))
        except (InvalidOperation, ValueError):
            raise PrimitiveError(f"Cannot parse int from {v!r}.", hint="Provide an integer string like '42'.")
    raise PrimitiveTypeError(f"Cannot convert {type(v).__name__} to int.")


def _to_float(ctx, args, params):
    v = args["v"]
    if isinstance(v, bool):
        raise PrimitiveTypeError("Cannot convert bool to float.", hint="Use numeric inputs.")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(Decimal(v.strip()))
        except (InvalidOperation, ValueError):
            raise PrimitiveError(f"Cannot parse float from {v!r}.", hint="Provide a numeric string like '19.99'.")
    raise PrimitiveTypeError(f"Cannot convert {type(v).__name__} to float.")


def _to_bool(ctx, args, params):
    v = args["v"]
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    raise PrimitiveTypeError(f"Cannot convert {type(v).__name__} to bool.")


def _to_money(ctx, args, params):
    return _to_float(ctx, args, params)


# --- state / events --------------------------------------------------------------

def _state_get(ctx, args, params):
    return ctx.state.get(_text(args, "key"))


def _state_set(ctx, args, params):
    # ``value`` may be any; params key hint is for the trace only.
    ctx.state[_text(args, "key")] = args["value"]
    return args["value"]


def _emit(ctx, args, params):
    name = params.get("event", "event")
    ctx.events.append({"event": name, "payload": args.get("payload")})
    return name


def _log(ctx, args, params):
    return f"{params.get('level','info')}: {_text(args,'message')}"


# Registry ---------------------------------------------------------------------

def _p(name, inputs, output, category, desc, func):
    return Primitive(name, tuple(inputs), output, category, desc, func)


_PRIMITIVES = [
    _p("add", [("a", "float", True), ("b", "float", True)], "float", "arithmetic", "a + b", _add),
    _p("sub", [("a", "float", True), ("b", "float", True)], "float", "arithmetic", "a - b", _sub),
    _p("mul", [("a", "float", True), ("b", "float", True)], "float", "arithmetic", "a * b", _mul),
    _p("div", [("a", "float", True), ("b", "float", True)], "float", "arithmetic", "a / b (errors on zero)", _div),
    _p("mod", [("a", "float", True), ("b", "float", True)], "float", "arithmetic", "a mod b (errors on zero)", _mod),
    _p("neg", [("a", "float", True)], "float", "arithmetic", "-a", _neg),
    _p("abs", [("a", "float", True)], "float", "arithmetic", "|a|", _abs),
    _p("clamp", [("v", "float", True), ("lo", "float", True), ("hi", "float", True)], "float", "arithmetic", "clamp v to [lo, hi]", _clamp),
    _p("round", [("v", "float", True)], "float", "arithmetic", "round v (params.digits, default 2)", _round),
    _p("min", [("a", "float", True), ("b", "float", True)], "float", "arithmetic", "min(a, b)", _min_max("min")),
    _p("max", [("a", "float", True), ("b", "float", True)], "float", "arithmetic", "max(a, b)", _min_max("max")),
    _p("eq", [("a", "any", True), ("b", "any", True)], "bool", "compare", "a == b", _cmp("eq")),
    _p("ne", [("a", "any", True), ("b", "any", True)], "bool", "compare", "a != b", _cmp("ne")),
    _p("lt", [("a", "float", True), ("b", "float", True)], "bool", "compare", "a < b", _cmp("lt")),
    _p("le", [("a", "float", True), ("b", "float", True)], "bool", "compare", "a <= b", _cmp("le")),
    _p("gt", [("a", "float", True), ("b", "float", True)], "bool", "compare", "a > b", _cmp("gt")),
    _p("ge", [("a", "float", True), ("b", "float", True)], "bool", "compare", "a >= b", _cmp("ge")),
    _p("and", [("a", "bool", True), ("b", "bool", True)], "bool", "logic", "a AND b", _logic("and")),
    _p("or", [("a", "bool", True), ("b", "bool", True)], "bool", "logic", "a OR b", _logic("or")),
    _p("not", [("v", "bool", True)], "bool", "logic", "NOT v", _logic("not")),
    _p("select", [("cond", "bool", True), ("then", "any", True), ("otherwise", "any", True)], "any", "logic", "cond ? then : otherwise", _select),
    _p("is_null", [("v", "any", True)], "bool", "logic", "v is null", _is_null),
    _p("is_empty", [("v", "any", True)], "bool", "logic", "v is empty string/list/map/null", _is_empty),
    _p("concat", [("a", "str", True), ("b", "str", True)], "str", "string", "a + b (params.sep)", _concat),
    _p("upper", [("s", "str", True)], "str", "string", "uppercase", _upper),
    _p("lower", [("s", "str", True)], "str", "string", "lowercase", _lower),
    _p("trim", [("s", "str", True)], "str", "string", "strip whitespace", _trim),
    _p("contains", [("haystack", "str", True), ("needle", "str", True)], "bool", "string", "needle in haystack", _contains),
    _p("len", [("v", "any", True)], "int", "string", "len of str/list/map", _len),
    _p("template", [("text", "str", True)], "str", "string", "fill {name} placeholders from args", _template),
    _p("format_money", [("v", "money", True)], "str", "string", "format as 2dp", _format_money),
    _p("get_field", [("m", "map", True), ("field", "str", True)], "any", "data", "map[field] (optional default)", _get_field),
    _p("get_index", [("items", "list", True), ("i", "int", True)], "any", "data", "items[i]", _get_index),
    _p("count", [("items", "list", True)], "int", "data", "number of items", _count),
    _p("sum_list", [("items", "list", True)], "float", "data", "sum of numeric list", _sum_list),
    _p("sum_field", [("items", "list", True), ("field", "str", True)], "float", "data", "sum of numeric field over maps", _sum_field),
    _p("sum_line_total", [("items", "list", True)], "money", "data", "sum of price*qty over order items", _sum_line_total),
    _p("map_lookup", [("m", "map", True), ("key", "any", True)], "any", "data", "m[key] (optional default)", _map_lookup),
    _p("dict_build", [], "map", "data", "collect named args into a map", _dict_build),
    _p("list_build", [], "list", "data", "collect named args into a list (params.order)", _list_build),
    _p("coalesce", [("a", "any", True), ("b", "any", True)], "any", "data", "a if a is not null else b", _coalesce),
    _p("require_nonempty", [("v", "any", True)], "any", "validation", "error if empty/null (params.name)", _require_nonempty),
    _p("validate_email", [("email", "str", True)], "str", "validation", "error if not a valid email", _validate_email),
    _p("check_stock", [("items", "list", True), ("inventory", "map", True)], "bool", "validation", "error if any item is out of stock", _check_stock),
    _p("assert_true", [("cond", "bool", True)], "bool", "validation", "error if false (params.message)", _assert_true),
    _p("fail_if", [("cond", "bool", True)], "bool", "validation", "error if true (params.message)", _fail_if),
    _p("to_str", [("v", "any", True)], "str", "conversion", "stringify", _to_str),
    _p("to_int", [("v", "any", True)], "int", "conversion", "parse/truncate to int", _to_int),
    _p("to_float", [("v", "any", True)], "float", "conversion", "parse to float", _to_float),
    _p("to_bool", [("v", "any", True)], "bool", "conversion", "truthiness conversion", _to_bool),
    _p("to_money", [("v", "any", True)], "money", "conversion", "parse to money", _to_money),
    _p("state_get", [("key", "str", True)], "any", "state", "read engine state", _state_get),
    _p("state_set", [("key", "str", True), ("value", "any", True)], "any", "state", "write engine state", _state_set),
    _p("emit", [], "str", "events", "record an event (params.event, arg payload)", _emit),
    _p("log", [("message", "str", True)], "str", "events", "log message (params.level)", _log),
]

REGISTRY: dict[str, Primitive] = {p.name: p for p in _PRIMITIVES}


def list_primitives() -> list[dict]:
    """JSON-serializable catalog for the agent interface."""
    return [
        {
            "name": p.name,
            "inputs": [{"name": n, "type": t, "required": r} for n, t, r in p.inputs],
            "output": p.output,
            "category": p.category,
            "desc": p.desc,
        }
        for p in _PRIMITIVES
    ]


def get_primitive(name: str) -> Primitive | None:
    return REGISTRY.get(name)
