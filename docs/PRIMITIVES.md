# Primitive Library Specification

55 primitives (v0.1), all unit-tested (`tests/test_primitives.py`) and
discoverable at runtime via `AgentAPI.list_primitives()` — the agent
never needs to guess this document.

## Design rules

1. **One behaviour per primitive.** Primitives do one thing and say what
   they do in `desc` (that text is what the debugger prints).
2. **Typed signatures.** Every primitive declares `(name, type, required)`
   inputs and an output type; the validator enforces them statically.
3. **Total errors.** Every failure is a `PrimitiveError` with a repair
   `hint` — never a bare Python exception or a stack trace.
4. **Purity by default.** Primitives that touch engine context
   (`state_*`, `emit`, `log`) are explicit; all others are pure
   functions of their args.
5. **No business logic smuggling.** `sum_line_total` and `check_stock`
   are the *most* domain-flavoured primitives in v0.1 (they encode
   "price × qty" and "sku inventory"). Everything else stays generic;
   domain policy (discount rates, thresholds) lives in the IR graph,
   where the agent and human can see and change it.

## Catalogue (9 categories)

### arithmetic (11)
`add, sub, mul, div, mod, neg, abs, clamp, round, min, max` — all
`float` numeric. `div`/`mod` error on zero divisor with a hint.

### compare (6)
`eq, ne` (`any`), `lt, le, gt, ge` (numeric) → `bool`.

### logic (6)
`and, or, not` (`bool`), `select(cond, then, otherwise)` (the dataflow
conditional), `is_null`, `is_empty`.

### string (8)
`concat` (`params.sep`), `upper, lower, trim, len, contains`,
`template` (fill `{name}` placeholders from args — one node composes a
whole message), `format_money`.

### data (10)
`get_field` (optional `default` arg), `get_index` (bounds-checked),
`count`, `sum_list`, `sum_field(items, field)`, `sum_line_total`,
`map_lookup` (optional default), `dict_build`, `list_build`
(`params.order`), `coalesce(a, b)`.

### validation (5)
`require_nonempty` (`params.name` in the error), `validate_email`,
`check_stock(items, inventory)`, `assert_true`, `fail_if` — the
fail-fast vocabulary of the repair loop.

### conversion (5)
`to_str, to_int, to_float, to_bool, to_money` — the way out of any
type-mismatch the validator reports.

### state (2)
`state_get(key)`, `state_set(key, value)` — the engine's key/value
store, seeded per execution and returned in the result.

### events (2)
`emit` (`params.event`, arg `payload`), `log` (`params.level`).

## Adding a primitive (checklist)

1. Implement `func(ctx, args, params) -> value`, raising
   `PrimitiveError(message, hint)` on domain failure.
2. Declare signature + category + desc in `_PRIMITIVES`.
3. Add a unit test in `tests/test_primitives.py`.
4. Document it here. A primitive without a test and docs is not merged.

Future categories (reserved, not built): `file`/`network`/`database`
behind capability gates (Phase 5), `components` (subroutine calls),
`iteration` (graph loops).
