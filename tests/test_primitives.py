"""Primitive unit tests: every category exercised at least once."""

import pytest

from agent_minimiser.primitives import Context, PrimitiveError, REGISTRY


def call(op: str, args: dict, params: dict | None = None):
    return REGISTRY[op].func(Context(), args, params or {})


def test_registry_covers_categories():
    cats = {p.category for p in REGISTRY.values()}
    assert {"arithmetic", "compare", "logic", "string", "data",
            "validation", "conversion", "state", "events"} <= cats
    assert len(REGISTRY) >= 40


def test_arithmetic():
    assert call("add", {"a": 2, "b": 3}) == 5
    assert call("sub", {"a": 2, "b": 3}) == -1
    assert call("mul", {"a": 2, "b": 3}) == 6
    assert call("div", {"a": 7, "b": 2}) == 3.5
    assert call("mod", {"a": 7, "b": 3}) == 1
    assert call("neg", {"a": 4}) == -4
    assert call("abs", {"a": -4}) == 4
    assert call("clamp", {"v": 99, "lo": 0, "hi": 10}) == 10
    assert call("round", {"v": 3.14159}) == 3.14
    assert call("min", {"a": 2, "b": 5}) == 2
    assert call("max", {"a": 2, "b": 5}) == 5
    with pytest.raises(PrimitiveError, match="zero"):
        call("div", {"a": 1, "b": 0})


def test_compare_logic():
    assert call("eq", {"a": 1, "b": 1}) is True
    assert call("ne", {"a": 1, "b": 2}) is True
    assert call("lt", {"a": 1, "b": 2}) is True
    assert call("ge", {"a": 2, "b": 2}) is True
    assert call("and", {"a": True, "b": False}) is False
    assert call("or", {"a": False, "b": True}) is True
    assert call("not", {"v": False}) is True
    assert call("select", {"cond": True, "then": "y", "otherwise": "n"}) == "y"
    assert call("select", {"cond": False, "then": "y", "otherwise": "n"}) == "n"
    assert call("is_empty", {"v": ""}) is True
    assert call("is_empty", {"v": "x"}) is False
    assert call("is_null", {"v": None}) is True


def test_string():
    assert call("concat", {"a": "a", "b": "b"}, {"sep": "-"}) == "a-b"
    assert call("upper", {"s": "ab"}) == "AB"
    assert call("lower", {"s": "AB"}) == "ab"
    assert call("trim", {"s": "  x "}) == "x"
    assert call("len", {"v": [1, 2, 3]}) == 3
    assert call("contains", {"haystack": "hello", "needle": "ell"}) is True
    assert call("format_money", {"v": 12.5}) == "12.50"
    assert call("template", {"text": "Hi {n}!", "n": "Bo"}) == "Hi Bo!"
    with pytest.raises(PrimitiveError, match="Unbound"):
        call("template", {"text": "Hi {missing}!"})


def test_data():
    assert call("get_field", {"m": {"a": 1}, "field": "a"}) == 1
    assert call("get_index", {"items": [10, 20], "i": 1}) == 20
    assert call("count", {"items": [1, 2]}) == 2
    assert call("sum_list", {"items": [1, 2, 3]}) == 6
    assert call("sum_field", {"items": [{"q": 2}, {"q": 3}], "field": "q"}) == 5
    assert call("sum_line_total", {"items": [{"price": 10, "qty": 2}, {"price": 5, "qty": 1}]}) == 25
    assert call("map_lookup", {"m": {"k": "v"}, "key": "k"}) == "v"
    assert call("coalesce", {"a": None, "b": 7}) == 7
    assert call("coalesce", {"a": 3, "b": 7}) == 3
    assert call("dict_build", {"a": 1, "b": 2}) == {"a": 1, "b": 2}


def test_validation_ops():
    assert call("require_nonempty", {"v": "x"}) == "x"
    with pytest.raises(PrimitiveError, match="required"):
        call("require_nonempty", {"v": ""})
    assert call("validate_email", {"email": "a@b.com"}) == "a@b.com"
    with pytest.raises(PrimitiveError, match="Invalid email"):
        call("validate_email", {"email": "nope"})
    assert call("check_stock", {"items": [{"sku": "S", "qty": 1}], "inventory": {"S": 5}}) is True
    with pytest.raises(PrimitiveError, match="Insufficient"):
        call("check_stock", {"items": [{"sku": "S", "qty": 9}], "inventory": {"S": 5}})
    with pytest.raises(PrimitiveError, match="boom"):
        call("assert_true", {"cond": False}, {"message": "boom"})


def test_conversion():
    assert call("to_str", {"v": 42}) == "42"
    assert call("to_int", {"v": "42"}) == 42
    assert call("to_int", {"v": 3.9}) == 3
    assert call("to_float", {"v": "2.5"}) == 2.5
    assert call("to_bool", {"v": "yes"}) is True
    assert call("to_bool", {"v": 0}) is False
    with pytest.raises(PrimitiveError):
        call("to_int", {"v": "not-a-number"})


def test_state_events_log():
    ctx = Context()
    REGISTRY["state_set"].func(ctx, {"key": "k", "value": 9}, {})
    assert REGISTRY["state_get"].func(ctx, {"key": "k"}, {}) == 9
    assert REGISTRY["emit"].func(ctx, {"payload": 1}, {"event": "e1"}) == "e1"
    assert ctx.events == [{"event": "e1", "payload": 1}]
    assert "info: hi" in REGISTRY["log"].func(ctx, {"message": "hi"}, {})
