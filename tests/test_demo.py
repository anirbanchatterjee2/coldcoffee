"""Demo + benchmark-equivalence tests."""

import json
from pathlib import Path

from agent_minimiser.agent_api import AgentAPI
from agent_minimiser.demo_order import ORDER_PROGRAM, SAMPLE_INPUTS

ROOT = Path(__file__).resolve().parent.parent


def test_checked_in_json_matches_built_program():
    text = (ROOT / "examples" / "order_processing.json").read_text(encoding="utf-8")
    assert json.loads(text) == ORDER_PROGRAM


def test_demo_via_agent_api():
    api = AgentAPI()
    loaded = api.load_app(json.loads((ROOT / "examples" / "order_processing.json").read_text(encoding="utf-8")))
    assert loaded["valid"]
    res = api.execute("order_processing", SAMPLE_INPUTS)
    assert res["ok"]
    assert res["outputs"]["total"] == 99.0
    assert "ORD-1001" in res["outputs"]["confirmation"]
    assert res["graph"].startswith("order_processing")
    assert res["explains"].startswith("## Execution")


def test_python_baseline_same_behaviour():
    ns: dict = {}
    ns["__file__"] = str(ROOT / "examples" / "order_processing.py")
    exec(compile((ROOT / "examples" / "order_processing.py").read_text(encoding="utf-8"),
                 str(ROOT / "examples" / "order_processing.py"), "exec"), ns)
    py = ns["process_order"](**SAMPLE_INPUTS)
    assert py["total"] == 99.0
    assert py["confirmation"] == "Thanks Anirban! Order ORD-1001 confirmed. Total: $99.00."
