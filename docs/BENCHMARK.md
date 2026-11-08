# Benchmark Report — IR vs conventional Python (v0.1)

Methodology is in `agent_minimiser/benchmark.py`; rerun it any time:

```
python -m agent_minimiser.benchmark
```

## Headline result (honest)

For this **16-node demo**, the IR payload is ~**2.1× larger** than the
equivalent Python file:

| Metric | IR (`order_processing.json`) | Python (`order_processing.py`) |
|---|---|---|
| Characters | 3,249 | 1,523 |
| Approx. tokens (chars/4) | 812 | 380 |
| Lines | 36 | 37 |
| Execution (1 run) | 0.40 ms | 0.58 ms |
| Behaviour match | ✅ same total + message | ✅ same total + message |

**No token-savings claim is made.** For a program this small, JSON's
explicitness (every arg spelled out as `{ref}/{input}/{const}`) costs
more than Python's terse syntax. Anyone telling you otherwise without
measuring is selling something.

## Where the IR does win on this demo

- **Validation before execution, with repair hints.** The IR fails
  *before* running with `{"node": "n_email", "hint": "…"}`; the Python
  baseline raises `ValueError` at runtime with no node context. Our
  test suite proves the repair loop (break → diagnose → patch → rerun)
  is a 4-call protocol; the Python equivalent is "read the traceback,
  edit text, rerun, re-validate by hand."
- **Trace = debuggability artifact.** Every IR run already records all
  16 node I/Os. The Python baseline records nothing unless the author
  adds logging — i.e., more code, more tokens.
- **Deterministic, model-independent execution.** The engine, not the
  model, decides semantics. Python semantics depend on whatever the
  model happened to generate.

## Where the IR should win at scale (hypotheses to test, not claims)

1. **Larger programs.** Python boilerplate (imports, defs, error
   scaffolding) grows super-linearly with features; IR node cost grows
   linearly. Crossover is expected well before "enterprise app" size.
2. **Reuse.** Editing an IR graph is a `patch_app` of one node;
   editing Python is re-emitting the file. Modify-cost, not
   create-cost, is where agents actually spend tokens.
3. **Fleets.** The 55-primitive registry is paid for once and reused
   across every app the agent builds. Python re-derives it per file.
4. **Repair iterations.** Each structured hint replaces a
   traceback-reading + guess-edit cycle — the metric to watch is
   *repairs to working*, not first-try tokens.

## Metrics still to measure (Phase 6)

Tokens to *modify* (not just construct), repair-iteration counts under
realistic agent runs, time from spec to executing, memory, error
classes only the IR can catch, and human time-to-understand with vs
without `explain`. Until those exist, the thesis is **"promising
mechanics, unproven economics"** — and the benchmark harness is the
instrument that will prove or disprove it.
