# IR Specification (v0.1)

The Intermediate Representation is the platform's contract between
agent and engine. It is a **versioned JSON object** — no custom syntax.
If you can read JSON you can read (and write) an IR program.

## Program schema

```jsonc
{
  "version": "0.1",                       // required; reject anything else
  "name": "order_processing",             // required, non-empty
  "description": "…",                     // optional, human-only
  "inputs": [
    {"name": "order_id", "type": "str", "required": true},
    {"name": "inventory", "type": "map", "required": false,
     "default": {"SKU-A": 50}}
  ],
  "nodes": [
    {
      "id": "n_subtotal",                 // unique; also the SSA variable
      "op": "sum_line_total",             // must be in the registry
      "args": {"items": {"input": "items"}},
      "params": {"digits": 2},            // optional static knobs
      "guard": {"ref": "n_has_volume"},   // optional bool Arg: skip if false
      "desc": "Subtotal = sum of price x qty"  // optional, for the debugger
    }
  ],
  "outputs": {"total": {"ref": "n_total_r"}}   // name -> Arg
}
```

### Args (values flowing into a node)

Every argument is exactly one of:

| Kind | Form | Meaning |
|---|---|---|
| Input | `{"input": "<name>"}` | A declared program input |
| Ref | `{"ref": "<node-id>"}` | A prior node's output (SSA; forward refs are invalid) |
| Const | `{"const": <literal>}` | An embedded JSON literal |

### Types (closed set, v0.1)

`str`, `int`, `float`, `money`, `bool`, `list`, `map`, `void`, `any`.
Numeric types are mutually compatible for validation (they share float
runtime semantics). `money` is float-backed in v0.1; exact decimals are
future work. `any` is the escape hatch for untyped/composed values.

### Semantics (execution order of operations)

1. **Validate.** Static checks run before any node executes (unknown op,
   dangling ref, duplicate id, missing required arg, type mismatch,
   input/node collision). Any failure halts with `validation_errors`
   and executes zero nodes.
2. **Bind inputs.** Supplied value wins; else `default`; else error if
   `required`; else `null`.
3. **Execute in order.** Each node resolves its args, then either
   executes its primitive or — if a `guard` is present and false —
   is *skipped* (output = `params.on_skip`, default null, trace status
   `skipped`). Nodes after the first failure never run.
4. **Collect outputs.** Each output Arg is resolved from the final env.
5. **Trace everything.** Every node records status, resolved inputs,
   output, and duration — success or failure.

### Control flow in v0.1 (what's possible, what's not)

- ✅ Dataflow conditionals: `select(cond, then, otherwise)`.
- ✅ Node-level conditionals: `guard` (skip-to-default).
- ✅ Early failure: any primitive may raise a domain error and halt.
- ❌ Visual branch-join graphs with merge nodes.
- ❌ General loops over subgraphs (use `sum_*` / `map`-style primitives).
- ❌ Subroutines / component composition (Phase 3+).
- ❌ Concurrency / parallelism (Phase 5).

These gaps are deliberate: each one makes the IR bigger and the
debugger harder, and none was needed to prove the thesis.

### Versioning and evolution

`version: "0.1"` is validated strictly — unknown versions are rejected,
never coerced. A v0.2 must (a) accept v0.1 programs, (b) add only new
ops/fields, (c) never change the meaning of an existing op. The JSON
file in `examples/` is the conformance fixture: `test_demo.py` fails if
the built-in program and the checked-in file ever diverge.

## Worked example (the demo, condensed)

```jsonc
{"id": "n_subtotal", "op": "sum_line_total",
 "args": {"items": {"input": "items"}},
 "desc": "Subtotal = sum of price x qty"}
```

means: "look up the `items` input (a list of `{sku, price, qty}` maps),
sum `price × qty` over it, store the result where later nodes can
reference it as `n_subtotal`." The engine interprets this mechanically;
the `desc` is what the human debugger prints. The full program is
`examples/order_processing.json` (16 nodes).
