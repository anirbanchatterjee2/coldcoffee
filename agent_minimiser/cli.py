"""Command-line driver for the Python prototype.

Examples:
    python -m agent_minimiser.cli list
    python -m agent_minimiser.cli demo
    python -m agent_minimiser.cli run examples/order_processing.json
    python -m agent_minimiser.cli validate examples/order_processing.json
    python -m agent_minimiser.cli explain examples/order_processing.json --inputs examples/order_inputs.json

``run``/``explain`` read an optional inputs JSON file (default: the
bundled sample).  Exit codes: 0 ok, 1 validation/runtime failure,
2 usage/IO error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .agent_api import AgentAPI
from .demo_order import ORDER_PROGRAM, SAMPLE_INPUTS


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    cmd, rest = argv[0], argv[1:]
    api = AgentAPI()
    try:
        if cmd == "list":
            for p in api.list_primitives():
                inputs = ", ".join(f"{i['name']}:{i['type']}" for i in p["inputs"])
                print(f"{p['name']:<15} ({p['category']:<10}) [{inputs}] -> {p['output']}  {p['desc']}")
            return 0

        if cmd == "demo":
            print(api.execute(ORDER_PROGRAM, SAMPLE_INPUTS)["explains"])
            return 0

        if cmd in ("run", "validate", "explain"):
            if not rest:
                print(f"usage: {cmd} <program.json> [--inputs <inputs.json>]", file=sys.stderr)
                return 2
            program = _load_json(Path(rest[0]))
            inputs = SAMPLE_INPUTS
            if "--inputs" in rest:
                inputs = _load_json(Path(rest[rest.index("--inputs") + 1]))
            if cmd == "validate":
                print(json.dumps(api.validate(program), indent=2))
                return 0 if api.validate(program)["valid"] else 1
            result = api.execute(program, inputs)
            print(result["explains"] if cmd == "explain" else json.dumps(result, indent=2))
            return 0 if result["ok"] else 1

        print(f"unknown command: {cmd!r}", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
