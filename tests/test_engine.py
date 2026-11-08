"""Engine + validator tests: static checks, tracing, guards, repair loop."""

import pytest

from agent_minimiser.agent_api import AgentAPI
from agent_minimiser.demo_order import ORDER_PROGRAM, SAMPLE_INPUTS, build_order_program
from agent_minimiser.engine import Engine

engine = Engine()


def test_validate_accepts_order_program():
    assert engine.validate(build_order_program()).ok


def test_validate_rejects_unknown_op_with_hint():
    p = build_order_program()
    p["nodes"][0]["op"] = "frobnicatetime"
    v = engine.validate(p)
    assert not v.ok
    assert any("Unknown op" in e["message"] for e in v.errors)


def test_validate_rejects_dangling_ref():
    p = build_order_program()
    p["nodes"][1]["args"]["email"] = {"ref": "n_nonexistent"}
    v = engine.validate(p)
    assert not v.ok
    assert any("unknown/future node" in e["message"] for e in v.errors)


def test_validate_rejects_missing_required_arg():
    p = build_order_program()
    p["nodes"][0]["args"] = {}
    v = engine.validate(p)
    assert not v.ok
    assert any("Missing required arg" in e["message"] for e in v.errors)


def test_validate_rejects_input_node_collision():
    p = build_order_program()
    p["nodes"][0]["id"] = "order_id"
    v = engine.validate(p)
    assert not v.ok
    assert any("collides" in e["message"] for e in v.errors)


def test_execute_order_demo_success():
    result = engine.execute(build_order_program(), SAMPLE_INPUTS)
    assert result.ok
    assert result.outputs["total"] == 99.0
    assert result.outputs["status"] == "confirmed"
    assert "ORD-1001" in result.outputs["confirmation"]
    assert result.state.get("last_order") == "ORD-1001"
    assert result.events and result.events[0]["event"] == "order_confirmed"
    # Trace length matches node count; all ok.
    assert len(result.trace) == len(ORDER_PROGRAM["nodes"])
    assert all(t.status == "ok" for t in result.trace)


def test_execute_discount_and_free_shipping_thresholds():
    # Subtotal 120 -> 10% off = 108 -> free shipping -> total 108.
    inputs = dict(SAMPLE_INPUTS, items=[{"sku": "SKU-A", "price": 120.0, "qty": 1}])
    result = engine.execute(build_order_program(), inputs)
    assert result.ok and result.outputs["total"] == 108.0

    # Subtotal 30 -> no discount, shipping 9.99 -> 39.99.
    inputs = dict(SAMPLE_INPUTS, items=[{"sku": "SKU-B", "price": 30.0, "qty": 1}])
    result = engine.execute(build_order_program(), inputs)
    assert result.ok and result.outputs["total"] == 39.99


def test_execute_invalid_email_halts_with_trace():
    inputs = dict(SAMPLE_INPUTS, customer_email="not-an-email")
    result = engine.execute(build_order_program(), inputs)
    assert not result.ok
    assert result.error["node"] == "n_email"
    assert "Invalid email" in result.error["message"]
    assert result.error["hint"]  # repair hint present for the agent loop
    assert not result.outputs
    # Downstream nodes never ran.
    assert all(t.status in ("ok", "error") for t in result.trace)
    assert not any(t.id == "n_msg" for t in result.trace)


def test_execute_out_of_stock_halts():
    inputs = dict(SAMPLE_INPUTS, items=[{"sku": "SKU-C", "price": 10.0, "qty": 99}])
    result = engine.execute(build_order_program(), inputs)
    assert not result.ok
    assert result.error["node"] == "n_stock"
    assert "Insufficient stock" in result.error["message"]


def test_missing_required_input():
    inputs = dict(SAMPLE_INPUTS)
    del inputs["order_id"]
    result = engine.execute(build_order_program(), inputs)
    assert not result.ok
    assert result.error["kind"] == "input"


def test_guard_skips_node_and_uses_on_skip():
    program = {
        "version": "0.1", "name": "guarded",
        "inputs": [{"name": "flag", "type": "bool"}],
        "nodes": [
            {"id": "n_val", "op": "to_str", "args": {"v": {"const": "ran"}},
             "guard": {"input": "flag"}, "params": {"on_skip": "skipped!"}, "desc": "only when flag"},
        ],
        "outputs": {"v": {"ref": "n_val"}},
    }
    r = engine.execute(program, {"flag": False})
    assert r.ok and r.outputs["v"] == "skipped!"
    assert r.trace[0].status == "skipped"

    r2 = engine.execute(program, {"flag": True})
    assert r2.ok and r2.outputs["v"] == "ran"
    assert r2.trace[0].status == "ok"


def test_agent_api_repair_loop():
    api = AgentAPI()
    p = build_order_program()
    p["nodes"][0]["op"] = "UNKNOWN_OP_X"  # break it, then repair via API
    # load_app keeps the broken program so execute fails validation.
    api.load_app(p)
    res = api.execute("order_processing", SAMPLE_INPUTS)
    assert not res["ok"]
    diag = api.diagnose(res)
    assert diag["action"] in ("create_app", "patch_node", "fix_inputs")
    # Repair: valid patch restores the op; re-validate + execute succeeds.
    fixed = api.patch_app("order_processing", "n_name", {"op": "require_nonempty"})
    assert fixed["valid"]
    res2 = api.execute("order_processing", SAMPLE_INPUTS)
    assert res2["ok"]


def test_explain_mentions_failure_and_hint():
    from agent_minimiser.debugger import explain
    inputs = dict(SAMPLE_INPUTS, customer_email="bad")
    result = engine.execute(build_order_program(), inputs)
    text = explain(result, inputs, "order_processing")
    assert "failed" in text and "What to change" in text and "n_email" in text
