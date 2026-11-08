"""Semantic debugger — explains *what happened* in human terms.

Every executed program gets three human-facing views:
  1. ``explain`` — a step-by-step markdown narrative (what, why, inputs,
     outputs, state changes, failure + repair hint).
  2. ``render_graph_text`` — an indented data-flow sketch for the explorer.
  3. The machine trace itself (``ExecutionResult.to_dict``).

The debugger never inspects Python source: its only inputs are the IR
and the engine trace, which is the humanness contract of the platform.
"""

from __future__ import annotations


def _short(value, limit: int = 80) -> str:
    s = repr(value)
    return s if len(s) <= limit else s[: limit] + "…"


def explain(result, inputs: dict | None = None, name: str = "") -> str:
    """Render a human-readable execution narrative as markdown."""
    name = name or getattr(result, "program_name", "") or "program"
    lines: list[str] = [f"## Execution of `{name}`"]
    lines.append(f"- **Status:** {'succeeded' if result.ok else 'failed'} "
                 f"({result.duration_ms:.1f} ms)")
    if inputs:
        lines.append("- **Inputs:** " + ", ".join(f"`{k}`={_short(v)}" for k, v in inputs.items()))

    if getattr(result, "validation_errors", None):
        lines.append("\n**Static validation found problems:**")
        for e in result.validation_errors:
            lines.append(f"- `{e['node']}`: {e['message']}" + (f" — _{e['hint']}_" if e.get("hint") else ""))

    lines.append("\n**Steps:**")
    if not result.trace:
        lines.append("- _(no nodes executed)_")
    for t in result.trace:
        why = f" — {t.desc}" if t.desc else ""
        if t.status == "skipped":
            lines.append(f"- `{t.id}` (`{t.op}`) — **skipped** (guard false){why}")
        elif t.status == "ok":
            lines.append(f"- `{t.id}` (`{t.op}`) — produced {_short(t.output)}{why}")
        else:
            lines.append(f"- `{t.id}` (`{t.op}`) — **failed**: {t.error}{why}")

    if result.events:
        lines.append("\n**Events:** " + ", ".join(str(e) for e in result.events))
    if result.state:
        lines.append("\n**State after execution:** " + ", ".join(f"`{k}`={_short(v)}" for k, v in result.state.items()))

    if result.ok:
        lines.append("\n**Outputs:** " + ", ".join(f"`{k}`={_short(v)}" for k, v in result.outputs.items()))
    else:
        err = result.error or {}
        lines.append(f"\n**Failure:** {err.get('message', 'unknown')} "
                     f"(node `{err.get('node')}`)")
        if err.get("hint"):
            lines.append(f"**What to change:** {err['hint']}")
        lines.append("_No outputs were produced. Fix the failing node and retry — "
                     "no downstream nodes ran._")

    # Repair-loop helper: the exact patch-sized feedback an agent needs.
    if result.error and result.error.get("hint"):
        lines.append(f"\nRepair hint for the agent: {result.error['hint']}")
    return "\n".join(lines)


def render_graph_text(program: dict) -> str:
    """Indented text sketch of data flow (explorer view; graphviz is future work)."""
    lines = [f"{program.get('name', '<unnamed>')} (IR v{program.get('version', '?')})"]
    lines.append("inputs: " + (", ".join(i["name"] for i in program.get("inputs", [])) or "(none)"))
    for n in program.get("nodes", []):
        deps = []
        for k, a in n.get("args", {}).items():
            if isinstance(a, dict) and len(a) == 1:
                deps.append(f"{k}={next(iter(a.values()))}")
        guard = " [guarded]" if "guard" in n else ""
        lines.append(f"  {n['id']}: {n['op']}({', '.join(deps) or '—'}){guard}")
        if n.get("desc"):
            lines.append(f"      _{n['desc']}_")
    lines.append("outputs: " + (", ".join(program.get("outputs", {}).keys()) or "(none)"))
    return "\n".join(lines)
