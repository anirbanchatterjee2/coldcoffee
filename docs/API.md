# Agent API Reference

The agent drives the platform through plain dicts and returns — no
source code, no MCP/HTTP in v0.1 (transport is a drop-in: every method
already returns JSON-serializable data). The Python class is
`agent_minimiser.AgentAPI`; the CLI (`python -m agent_minimiser.cli`)
is a thin JSON-file wrapper over the same methods.

## Discovery

```python
api.list_primitives()  # [{"name", "inputs": [{name,type,required}], "output", "category", "desc"}]
api.describe()         # {"platform", "version", "ir_version", "primitives", "apps"}
```

## Build → validate → execute

```python
api.create_app(name, inputs, nodes, outputs, description="")
# -> {"name", "valid": bool, "errors": [...], "program": <IR dict>}

api.load_app(program_dict)   # same, from a full IR dict
api.get_app(name)            # -> IR dict | None (deep copy)

api.validate(program_dict_or_name)
# -> {"valid": bool, "errors": [{"node", "message", "hint"}]}

api.execute(program_dict_or_name, inputs, state=None)
# -> {"ok", "outputs", "error", "validation_errors", "events",
#     "state", "duration_ms", "trace": [...], "explains": <markdown>,
#     "graph": <text sketch>}
```

A failed execution never throws; it returns `ok: False` with a
machine-readable `error {kind, node, op, message, hint}` plus the
trace of exactly what ran before the failure.

## Repair loop

```python
res = api.execute(app, inputs)
while not res["ok"]:
    diag = api.diagnose(res)     # {"node", "message", "hint", "action"}
    api.patch_app(name, diag["node"], {"op": "...", "args": {...}})
    res = api.execute(name, inputs)
```

`patch_app(name, node_id, changes)` merges `changes` into one node —
the unit of repair. `action` is one of `patch_node` (runtime error),
`create_app` (validation error), `fix_inputs` (missing input), `none`.

## The demo end-to-end

```python
from agent_minimiser import AgentAPI, ORDER_PROGRAM, SAMPLE_INPUTS

api = AgentAPI()
api.load_app(ORDER_PROGRAM)                      # {"valid": True, ...}
result = api.execute("order_processing", SAMPLE_INPUTS)
result["ok"]                                     # True
result["outputs"]                                # {"confirmation": "Thanks Anirban! … $99.00.", "total": 99.0, "status": "confirmed"}
print(result["explains"])                        # human-readable narrative
```

CLI equivalents:

```
python -m agent_minimiser.cli list
python -m agent_minimiser.cli demo
python -m agent_minimiser.cli validate examples/order_processing.json
python -m agent_minimiser.cli run examples/order_processing.json --inputs examples/order_inputs.json
python -m agent_minimiser.cli explain examples/order_processing.json
```

Exit codes: 0 ok, 1 validation/runtime failure, 2 usage/IO error.
