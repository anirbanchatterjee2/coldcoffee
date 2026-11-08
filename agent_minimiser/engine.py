"""Execution engine — validates, schedules, executes, and traces IR programs.

The engine is deliberately model-independent: it takes a plain IR dict,
validates it statically, resolves inputs, runs each node in order,
and returns a structured result with a per-node trace.  Concurrency,
JIT, and persistence are future-work (see docs/ARCHITECTURE.md); v0.1
executes deterministically in order, which is also the execution plan
(alpha-version topological order).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .ir import validate_program
from .primitives import REGISTRY, Context, PrimitiveError


@dataclass
class NodeTrace:
    id: str
    op: str
    status: str  # "ok" | "skipped" | "error"
    inputs: dict
    output: Any = None
    error: str = ""
    hint: str = ""
    desc: str = ""
    duration_ms: float = 0.0


@dataclass
class ExecutionResult:
    ok: bool
    outputs: dict
    trace: list[NodeTrace] = field(default_factory=list)
    error: dict | None = None
    events: list = field(default_factory=list)
    state: dict = field(default_factory=dict)
    duration_ms: float = 0.0
    program_name: str = ""
    validation_errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "program": self.program_name,
            "outputs": self.outputs,
            "error": self.error,
            "validation_errors": self.validation_errors,
            "events": self.events,
            "state": self.state,
            "duration_ms": round(self.duration_ms, 3),
            "trace": [
                {"id": t.id, "op": t.op, "status": t.status, "inputs": t.inputs,
                 "output": t.output, "error": t.error, "hint": t.hint,
                 "desc": t.desc, "duration_ms": round(t.duration_ms, 3)}
                for t in self.trace
            ],
        }


class Engine:
    """Deterministic single-threaded executor (v0.1)."""

    def validate(self, program: dict):
        return validate_program(program)

    def execute(self, program: dict, inputs: dict | None = None, state: dict | None = None) -> ExecutionResult:
        inputs = dict(inputs or {})
        t0 = time.perf_counter()

        v = validate_program(program)
        if not v.ok:
            return ExecutionResult(
                ok=False, outputs={}, error={"kind": "validation", "message": "Program failed static validation."},
                validation_errors=v.errors, duration_ms=(time.perf_counter() - t0) * 1000,
                program_name=program.get("name", "<unnamed>"),
            )

        # Resolve declared inputs: supplied wins, else default, else None.
        env: dict[str, Any] = {}
        for spec in program.get("inputs", []):
            name = spec["name"]
            if name in inputs:
                env[name] = inputs[name]
            elif "default" in spec:
                env[name] = spec["default"]
            elif spec.get("required", True):
                return ExecutionResult(
                    ok=False, outputs={}, error={"kind": "input", "message": f"Missing required input '{name}'.",
                                                  "node": None, "hint": f"Provide '{name}' in the inputs payload."},
                    duration_ms=(time.perf_counter() - t0) * 1000, program_name=program.get("name", ""),
                )
            else:
                env[name] = None

        ctx = Context(state=dict(state or {}))
        trace: list[NodeTrace] = []

        def resolve(arg) -> Any:
            if "const" in arg:
                return arg["const"]
            if "input" in arg:
                return env.get(arg["input"])
            return env.get(arg["ref"])

        for node in program.get("nodes", []):
            nid = node["id"]
            op = node["op"]
            prim = REGISTRY[op]
            desc = node.get("desc", "")
            nt0 = time.perf_counter()

            resolved = {k: resolve(a) for k, a in node.get("args", {}).items()}

            # Conditional execution (guard).  Skipped nodes produce
            # params.on_skip (default null) without calling the primitive.
            if "guard" in node:
                g = resolve(node["guard"])
                if not g:
                    out = node.get("params", {}).get("on_skip")
                    env[nid] = out
                    trace.append(NodeTrace(nid, op, "skipped", resolved, out,
                                           desc=desc, duration_ms=(time.perf_counter() - nt0) * 1000))
                    continue

            try:
                out = prim.func(ctx, resolved, node.get("params", {}))
                env[nid] = out
                trace.append(NodeTrace(nid, op, "ok", resolved, out,
                                       desc=desc, duration_ms=(time.perf_counter() - nt0) * 1000))
            except PrimitiveError as e:
                hint = getattr(e, "hint", "") or ""
                trace.append(NodeTrace(nid, op, "error", resolved, None,
                                       error=str(e), hint=hint, desc=desc,
                                       duration_ms=(time.perf_counter() - nt0) * 1000))
                return ExecutionResult(
                    ok=False, outputs={}, trace=trace,
                    error={"kind": "runtime", "node": nid, "op": op, "message": str(e), "hint": hint},
                    events=ctx.events, state=ctx.state,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    program_name=program.get("name", ""),
                )

        outputs = {name: resolve(arg) for name, arg in program.get("outputs", {}).items()}
        return ExecutionResult(
            ok=True, outputs=outputs, trace=trace, events=ctx.events, state=ctx.state,
            duration_ms=(time.perf_counter() - t0) * 1000,
            program_name=program.get("name", ""),
        )
