# Roadmap & Status

Living status board for the project brief's 6 phases. "Done" means
tests exist and pass (`python -m pytest`), not merely "written."

## Phase 1 — Research and Architecture ✅ DONE

- [x] Problem statement and design principles (`docs/ARCHITECTURE.md`)
- [x] Overlap/novelty/hardest-problems analysis (`docs/ARCHITECTURE.md`)
- [x] IR schema + execution semantics (`docs/IR_SPEC.md`)
- [x] Primitive library design (`docs/PRIMITIVES.md`)

## Phase 2 — Minimal Execution Engine ✅ DONE

- [x] IR (`agent_minimiser/ir.py`) + type system (`types.py`)
- [x] Primitive registry — 55 primitives (`primitives.py`)
- [x] Static validation, 6 check classes (`ir.py`)
- [x] Deterministic execution engine + traces (`engine.py`)
- [x] Test suite — 24 tests (`tests/`)
- [x] Working demo: order processing (`demo_order.py`, `examples/`)

## Phase 3 — Agent Integration 🔶 PARTIAL (next priority)

- [x] In-process `AgentAPI`: create/load/validate/execute/patch/diagnose (`agent_api.py`)
- [x] JSON-file CLI (`cli.py`) as transport stand-in
- [x] Repair loop proven in `test_agent_api_repair_loop`
- [ ] MCP/HTTP transport over the same payloads
- [ ] Persistent app store + versioning/rollback
- [ ] Component/subroutine composition (call a subgraph as a node)
- [ ] More real-world demo apps (error paths, stateful flows)

## Phase 4 — Human Interface 🔶 PARTIAL

- [x] `explain()` narrative + text graph (`debugger.py`)
- [ ] Web explorer: view IR, traces, state, history
- [ ] Graphviz/SVG execution-graph visualizer
- [ ] Human intervention hooks (approve/edit-and-resume)

## Phase 5 — Advanced Runtime ⬜ NOT STARTED

- [ ] Concurrency + execution-plan optimization (parallel DAG scheduling)
- [ ] Persistent state + durable execution
- [ ] Capability-gated OS/file/network/DB primitives + quotas
- [ ] Rust core (only if profiling justifies it)
- [ ] Distributed execution evaluation

## Phase 6 — Benchmarking 🔶 PARTIAL

- [x] Harness + first honest result (`benchmark.py`, `docs/BENCHMARK.md`)
- [ ] Modify/repair token metrics under agent runs
- [ ] Multi-app + larger-program crossover study
- [ ] Human-comprehension study (IR+explain vs reading Python)

## Decision log

- **2026-11-08 — Python prototype, modular monolith, linear SSA schedule.**
  Graph-parallel execution deferred until the loop/guard semantics are
  proven; a straight-line env is easier to validate, trace, and
  benchmark. JSON as the wire format (universal, diffable, zero-dep).
- **2026-11-08 — `money` as float-backed but distinct.** Exact-Decimal
  money is the right long-term call but overkill before the token
  economics are known; the type distinction keeps the door open.
- **2026-11-08 — No OS capabilities in v0.1.** The capability seam is
  reserved in the registry, but nothing shipped touches disk, net, or
  env. Smallest secure surface first.
