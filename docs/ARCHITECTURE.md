# Agent Minimiser — Architecture Document

Status: **Phase 2 complete (minimal vertical slice).** Phase 1 (research +
design) and Phase 2 (minimal engine) are implemented and tested. Phase 3
(agent API) is partially implemented. Phases 4–6 are designed but not yet
built. Every claim below is tagged **IMPLEMENTED**, **PARTIAL**, or
**FUTURE** so implemented and proposed capabilities are never conflated.

## The thesis

An AI agent's intent can be compiled to a *compact, typed, composable,
verifiable machine representation* and executed by a model-independent
engine, instead of the agent generating conventional source code (Python,
Java, …) which a toolchain then parses, type-checks, and interprets.

The differentiator is **not** that one IR node is shorter than one line
of Python — our first benchmark proves it isn't (see `docs/BENCHMARK.md`).
The differentiator is **total cost of construct → validate → execute →
repair → reuse**: pre-verified primitives are never re-emitted, static
validation fails fast with repair hints, and humans debug semantics
instead of stack traces.

## Feasibility verdict

Feasible as a *narrow vertical slice*, which is what we have built.
The concept is an evolution, not a rupture: it combines three proven
ideas — (1) dataflow/SSA graphs as the machine representation,
(2) a capability-secure primitive catalogue (cf. Unix syscalls, WebAssembly
host functions), (3) structured agent/tool APIs (cf. function calling).
Nothing here requires new hardware or new mathematics; the engineering
risk is in the edges (types, error recovery, versioning), not the core.

## What overlaps with existing technology (and what we borrow)

| Existing technology | Overlap | What we borrow | How we differ |
|---|---|---|---|
| Python/Java interpreters | Execute programs from parseable text | Deterministic, total semantics | Our artifact is structured data, never parsed text; there is no syntax layer to learn |
| WASM / JVM bytecode | Compact machine representation, verified before execution | Verify-before-run; host-function catalogue | Bytecode targets humans-compiled code; our IR targets *agent-composed* behaviour with per-node semantics for debugging |
| Dataflow / SSA graphs (TensorFlow, compiler IRs like MLIR) | Typed DAG execution | Topological scheduling, SSA env | We keep a *linear* v0.1 schedule for debuggability; graph parallelism is future work |
| Function/tool calling (LLM APIs) | Agents invoke typed operations | Structured request/response | Tool calling executes one call; we execute a *whole program graph* with validation + trace |
| Unix capabilities / libpreopen | OS integration from a sandbox | Least-privilege primitives | v0.1 ships no OS capabilities yet (FUTURE); the seam is designed for them |

## What is genuinely novel

1. **The artifact is the graph, not the text.** There is no source file,
   no grammar, no formatter, no linter for a language. The agent emits
   data; the engine executes data. This is the correct level for a
   machine consumer.
2. **Verification *is* the API.** Validation errors carry repair hints
   (`{"node", "message", "hint"}`) designed as the agent's next
   observation — the repair loop is a first-class protocol, not an
   afterthought bolted onto stack traces.
3. **Debuggability triple.** Every program is simultaneously a machine
   graph, a trace, and a markdown narrative (`explain`). Humans never
   must read the machine form to understand behaviour.
4. **Primitives as pre-verified reuse.** Email validation, stock checking,
   money rounding are correct *once* in the registry; agents compose
   rather than re-derive them (every re-derivation is a chance to be
   wrong, and a token cost paid repeatedly).

## Hardest technical challenges (ranked)

1. **A type system expressive enough to catch real errors without
   rejecting real programs.** v0.1 uses a closed 9-type lattice; richer
   records/generics/unions are the known-hard next step. Over-strictness
   breaks the builder; under-strictness ships bugs.
2. **Error recovery UX as data.** A hint the agent can act on must name
   the node, the expectation, and the fix. This is harder than the
   error itself and is where most of the engineering value lives.
3. **Control flow without syntax.** Loops, branches, subroutines, and
   error containment in a flat dataflow list require care to stay
   compact *and* legible. v0.1 covers branching via `select` + node
   guards; general loops are FUTURE (see `docs/IR_SPEC.md`).
4. **The token-economics honesty problem.** Any summary that doesn't
   benchmark is marketing. `docs/BENCHMARK.md` reports the uncomfortable
   first result and the conditions under which IR would win (larger
   programs, reuse, repair iterations, multi-app fleets).
5. **State, concurrency, and OS capabilities.** The seam exists
   (`state_get/set`, `emit`, capability-gated primitives); the hard
   part — isolation, quotas, persistence, scheduling — is Phase 5, and
   we deliberately did not build it early (per project constraint).

## Smallest architecture that proves the thesis

A **modular monolith in Python** (no services, no build system, no
network): five modules forming a pipeline

```
AgentAPI → IR dict → validate_program → Engine (trace) → explain()
                primitive registry (pure, verified, typed)
```

plus a JSON-file CLI as the transport stand-in. That is the whole of
v0.1: ~1,500 lines, 24 tests, 1 demo, 1 benchmark. If the thesis were
wrong, this is where it would fall over — it doesn't.

## Component map (all seven project components)

| Project component | v0.1 status | Where | Notes |
|---|---|---|---|
| 1. Agent Interface | PARTIAL (in-process dict API + JSON CLI) | `agent_minimiser/agent_api.py`, `cli.py` | MCP/HTTP transport = FUTURE (designed seam: every method already returns plain JSON-able data) |
| 2. IR | IMPLEMENTED (v0.1) | `ir.py`, `docs/IR_SPEC.md` | Linear SSA list + guards; versioned `"0.1"` |
| 3. Validation/Verification | IMPLEMENTED (static; runtime via primitive errors) | `ir.py` + `engine.py` | 6 check classes; no formal proofs in v0.1 (FUTURE) |
| 4. Execution Engine | IMPLEMENTED (deterministic interpreter) | `engine.py` | JIT/parallel/graph scheduling = FUTURE |
| 5. Primitive Library | IMPLEMENTED (55 primitives, 9 categories) | `primitives.py`, `docs/PRIMITIVES.md` | File/network/DB primitives = FUTURE (capability seam reserved) |
| 6. Semantic Debugger | PARTIAL (narrative + text graph) | `debugger.py` | Web explorer / graphviz = FUTURE |
| 7. Application Management | PARTIAL (in-memory registry, patch, rollback-by-replace) | `agent_api.py` | Persistent store, versioning, deploy = FUTURE |

OS integration (component D of the brief) is **FUTURE by design**: v0.1
runs above the OS as an ordinary Python process with zero capabilities —
the safest possible boundary — and the primitive registry reserves a
`capability` field for the Phase 5 design.

## Why Python for the prototype (and Rust later)

Per the brief: Python for experimentation, orchestration, and agent
integration; Rust when profiling proves the interpreter is hot. Python's
dataclasses, stdlib-only execution, and zero-install startup made the
thesis testable in one sitting. The engine boundary (`Engine.execute`
takes plain dicts) is deliberately language-agnostic, so a Rust or
TypeScript executor can be dropped in without changing the IR or API.
