# Agent Minimiser

**An agent-native software construction and execution platform.**

Agents construct applications directly in a compact, typed, verifiable
machine representation (IR) and a model-independent engine executes
them — no conventional source code as the primary artifact. Python
implements the *engine* (a prototype choice); the *applications* are
pure IR.

## Quick start

```bash
pip install -e .[dev]
python -m pytest tests -q            # 24 tests
python -m agent_minimiser.cli list   # 55-primitive catalogue
python -m agent_minimiser.cli demo          # order demo, human-readable
python -m agent_minimiser.cli run examples/order_processing.json
python -m agent_minimiser.benchmark  # IR vs Python, honestly reported
```

## The demo in 30 seconds

An agent composes 16 IR nodes from 55 verified primitives:

```json
{"id": "n_subtotal", "op": "sum_line_total",
 "args": {"items": {"input": "items"}},
 "desc": "Subtotal = sum of price x qty"}
```

The engine validates the whole graph (unknown op? dangling ref? type
mismatch? — reported with repair hints *before* anything runs), executes
it, and returns structured `outputs` + a per-node `trace` + a markdown
`explain`. Full program: `examples/order_processing.json`.

```python
from agent_minimiser import AgentAPI, ORDER_PROGRAM, SAMPLE_INPUTS

api = AgentAPI()
api.load_app(ORDER_PROGRAM)
result = api.execute("order_processing", SAMPLE_INPUTS)
assert result["ok"] and result["outputs"]["total"] == 99.0
```

## Docs

- `docs/ARCHITECTURE.md` — feasibility, overlap with WASM/MLOps, novelty, hardest problems
- `docs/IR_SPEC.md` — the IR schema and execution semantics
- `docs/PRIMITIVES.md` — the typed primitive catalogue
- `docs/API.md` — the agent interface and repair loop
- `docs/BENCHMARK.md` — measured IR-vs-Python costs (no unproven claims)
- `docs/ROADMAP.md` — phase status and decision log

## Status

| Area | Status |
|---|---|
| IR + validator + engine + traces | ✅ Implemented, tested |
| Primitive library (55 ops, 9 categories) | ✅ Implemented, tested |
| Order-processing demo (IR only) | ✅ Works end-to-end |
| Agent API + repair loop | 🔶 In-process + CLI (MCP next) |
| Semantic debugger (narrative + text graph) | 🔶 Web explorer next |
| OS capabilities / concurrency / Rust core | ⬜ Phase 5, seam reserved |

## Layout

```
agent_minimiser/   engine (ir, types, primitives, engine, debugger, agent_api, cli, benchmark)
examples/          order_processing.json (IR), order_processing.py (baseline), inputs
tests/             engine, primitives, demo suites (24 tests)
docs/              architecture, IR spec, primitives, API, benchmark, roadmap
```

MIT licensed. Built incrementally per the project roadmap — see `docs/ROADMAP.md`.
