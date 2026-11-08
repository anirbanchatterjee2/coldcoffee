"""Benchmark harness: IR construction cost vs conventional Python.

Counts reproducible proxies (characters, approximate tokens = chars/4,
node count, execution ms) for the *same* order-processing behaviour
expressed two ways:
  A. Agent Minimiser IR (``examples/order_processing.json``)
  B. Equivalent conventional Python (``examples/order_processing.py``)

Run: ``python -m agent_minimiser.benchmark``
See ``docs/BENCHMARK.md`` for methodology and caveats.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IR_PATH = ROOT / "examples" / "order_processing.json"
PY_PATH = ROOT / "examples" / "order_processing.py"


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def main() -> None:
    ir_text = IR_PATH.read_text(encoding="utf-8")
    py_text = PY_PATH.read_text(encoding="utf-8")

    from .agent_api import AgentAPI
    from .demo_order import SAMPLE_INPUTS

    api = AgentAPI()
    program = json.loads(ir_text)
    t0 = time.perf_counter()
    result = api.execute(program, SAMPLE_INPUTS)
    ir_ms = (time.perf_counter() - t0) * 1000

    # Run the Python equivalent in-process (no subprocess needed).
    namespace: dict = {}
    t0 = time.perf_counter()
    exec(compile(py_text, str(PY_PATH), "exec"), namespace)
    py_result = namespace["process_order"](**SAMPLE_INPUTS)
    py_ms = (time.perf_counter() - t0) * 1000

    ir_result = result["outputs"]
    match = (
        abs(float(ir_result.get("total", -1)) - float(py_result.get("total", -2))) < 0.01
        and ir_result.get("confirmation") == py_result.get("confirmation")
    )

    rows = [
        ("IR characters", len(ir_text), len(py_text)),
        ("IR approx. tokens (chars/4)", approx_tokens(ir_text), approx_tokens(py_text)),
        ("Lines", ir_text.count("\n") + 1, py_text.count("\n") + 1),
        ("IR nodes (no equivalent in Python)", len(program["nodes"]), "—"),
    ]
    print("=== Agent Minimiser vs conventional Python (order_processing) ===")
    print(f"{'metric':<36} {'IR':>14} {'Python':>14}")
    for label, a, b in rows:
        print(f"{label:<36} {str(a):>14} {str(b):>14}")
    print(f"{'Execution ms (1 run)':<36} {ir_ms:>14.2f} {py_ms:>14.2f}")
    print(f"{'Behaviour match (total+message)':<36} {'yes' if match else 'NO — investigate':>14}")
    if not match:
        print(f"  IR: {ir_result}\n  PY: {py_result}")
    else:
        print(f"\nBoth produce total=${ir_result['total']} and:")
        print(f"  {ir_result['confirmation']}")
    print("\nNote: token counts here are the *payload* cost only. The IR's")
    print("advantage compounds on reuse (primitives are pre-verified and")
    print("never re-emitted) and on repair (structured hints vs stack traces).")


if __name__ == "__main__":
    main()
