"""Agent-facing API — the machine-readable construction interface.

This is the boundary the AI agent drives; it speaks plain dicts/JSON
(no source code, no MCP/HTTP transport in v0.1 — transport is a drop-in
later, see docs/API.md).  Every method returns structured data an agent
can act on, including validation errors *with repair hints* for the
repair loop.

Example repair loop::

    api = AgentAPI()
    app = api.create_app("order", inputs, nodes, outputs)
    res = api.execute(app, inputs)
    while not res["ok"]:
        patch = api.diagnose(res)          # pinpoint + hint
        app = api.patch(app, patch)        # structured edit
        res = api.execute(app, inputs)
"""

from __future__ import annotations

import copy
import json

from . import __version__
from .debugger import explain, render_graph_text
from .engine import Engine
from .primitives import list_primitives


class AgentAPI:
    def __init__(self):
        self._engine = Engine()
        self._apps: dict[str, dict] = {}  # name -> program dict

    # -- discovery -----------------------------------------------------
    def list_primitives(self) -> list[dict]:
        return list_primitives()

    def describe(self) -> dict:
        return {
            "platform": "agent-minimiser",
            "version": __version__,
            "ir_version": "0.1",
            "primitives": len(list_primitives()),
            "apps": sorted(self._apps),
        }

    # -- construction --------------------------------------------------
    def create_app(self, name: str, inputs: list, nodes: list, outputs: dict,
                   description: str = "") -> dict:
        """Create (or replace) an application from structured parts."""
        program = {"version": "0.1", "name": name, "description": description,
                   "inputs": inputs, "nodes": nodes, "outputs": outputs}
        self._apps[name] = copy.deepcopy(program)
        v = self._engine.validate(program)
        return {"name": name, "valid": v.ok, "errors": v.errors, "program": program}

    def load_app(self, program: dict) -> dict:
        name = program.get("name", "<unnamed>")
        self._apps[name] = copy.deepcopy(program)
        v = self._engine.validate(program)
        return {"name": name, "valid": v.ok, "errors": v.errors, "program": copy.deepcopy(program)}

    def get_app(self, name: str) -> dict | None:
        return copy.deepcopy(self._apps.get(name))

    def patch_app(self, name: str, node_id: str, changes: dict) -> dict:
        """Structured edit: merge ``changes`` into one node (e.g. fix an arg)."""
        program = self._apps.get(name)
        if program is None:
            return {"valid": False, "errors": [{"node": node_id, "message": f"Unknown app {name!r}.", "hint": "create_app first."}]}
        for node in program.get("nodes", []):
            if node["id"] == node_id:
                node.update(copy.deepcopy(changes))
                break
        else:
            return {"valid": False, "errors": [{"node": node_id, "message": f"Unknown node {node_id!r}.", "hint": "List nodes via get_app."}]}
        v = self._engine.validate(program)
        return {"name": name, "valid": v.ok, "errors": v.errors, "program": copy.deepcopy(program)}

    # -- execution -----------------------------------------------------
    def validate(self, program: dict | str) -> dict:
        if isinstance(program, str):
            name = program
            program = self._apps.get(name)
            if program is None:
                return {"valid": False, "errors": [{"node": None, "message": f"Unknown app {name!r}.", "hint": ""}]}
        v = self._engine.validate(program)
        return {"valid": v.ok, "errors": v.errors}

    def execute(self, program: dict | str, inputs: dict | None = None, state: dict | None = None) -> dict:
        if isinstance(program, str):
            program = self._apps[program]
        result = self._engine.execute(program, inputs, state)
        d = result.to_dict()
        d["explains"] = explain(result, inputs, program.get("name", ""))
        d["graph"] = render_graph_text(program)
        return d

    def diagnose(self, execution: dict) -> dict:
        """Extract the repair action from a failed execution dict."""
        if execution.get("ok"):
            return {"node": None, "message": "", "hint": "", "action": "none"}
        err = execution.get("error") or {}
        trace = execution.get("trace") or []
        failed = next((t for t in trace if t["status"] == "error"), None)
        return {
            "node": err.get("node") or (failed or {}).get("id"),
            "message": err.get("message", ""),
            "hint": err.get("hint") or (failed or {}).get("hint", ""),
            "action": "patch_node" if err.get("kind") == "runtime"
                      else ("create_app" if err.get("kind") == "validation" else "fix_inputs"),
        }

    # -- serialization -------------------------------------------------
    def to_json(self, program: dict | str) -> str:
        if isinstance(program, str):
            program = self._apps[program]
        return json.dumps(program, indent=2, sort_keys=True)

    def from_json(self, text: str) -> dict:
        return json.loads(text)
