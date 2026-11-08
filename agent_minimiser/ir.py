"""Intermediate Representation (IR) schema and static validator.

A program is a JSON-serializable dict::

    {
      "version": "0.1",
      "name": "order_processing",
      "description": "...",
      "inputs":  [{"name": "order_id", "type": "str", "required": true}],
      "nodes":   [{"id": "n_subtotal", "op": "sum_line_total",
                   "args": {"items": {"input": "items"}}, "out": "subtotal",
                   "desc": "Sum price*qty"}],
      "outputs": {"confirmation": {"ref": "n_msg"}, "total": {"ref": "n_total"}}
    }

Arg kinds (exactly one key per arg):
  - ``{"input": "<input-name>"}``  – read a program input
  - ``{"ref": "<node-id>"}``       – read a prior node's output
  - ``{"const": <literal>}``       – embed a literal (numbers, strings,
                                     bools, null, small lists/maps)

An optional node field ``guard`` (an Arg evaluating to bool) adds
conditional execution: when the guard is false the node is *skipped* and
its output is ``params.on_skip`` (default null).  Together with the
``select`` primitive this covers v0.1 control flow (see docs/IR_SPEC.md
for the graph/guard roadmap).

Validation is static and total: unknown ops, dangling refs, duplicate
ids, missing required args, and type mismatches are reported *before*
any execution, each with a repair hint for the agent repair loop.
Outputs of ``select``/untyped primitives are inferred loosely (any), so
v0.1 errs toward shipping an executable program over rejecting one.
"""

from __future__ import annotations

from .primitives import REGISTRY
from .types import TYPES, are_compatible, check_literal

ARG_KINDS = ("input", "ref", "const")


class ValidationResult:
    def __init__(self, errors: list[dict] | None = None):
        self.errors: list[dict] = errors or []

    @property
    def ok(self) -> bool:
        return not self.errors

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"ValidationResult(ok={self.ok}, errors={self.errors})"


def _err(node: str | None, message: str, hint: str = "") -> dict:
    return {"node": node, "message": message, "hint": hint}


def _arg_kind(arg) -> str | None:
    if not isinstance(arg, dict) or len(arg) != 1:
        return None
    kind = next(iter(arg))
    return kind if kind in ARG_KINDS else None


def validate_program(program: dict) -> ValidationResult:
    """Statically validate ``program``; never executes user code."""
    errors: list[dict] = []

    if not isinstance(program, dict):
        return ValidationResult([_err(None, "Program must be a JSON object.", "Emit the full program dict per docs/IR_SPEC.md.")])

    if program.get("version") != "0.1":
        errors.append(_err(None, f"Unsupported IR version: {program.get('version')!r}.", "Set \"version\": \"0.1\"."))

    inputs = program.get("inputs", [])
    nodes = program.get("nodes", [])
    outputs = program.get("outputs", {})

    if not isinstance(inputs, list) or not isinstance(nodes, list) or not isinstance(outputs, dict):
        errors.append(_err(None, "inputs/nodes must be lists, outputs must be a map.", "Use the AgentAPI: create_app(name, inputs, nodes, outputs)."))
        return ValidationResult(errors)

    # --- inputs -----------------------------------------------------------
    input_types: dict[str, str] = {}
    for inp in inputs:
        if not isinstance(inp, dict) or "name" not in inp:
            errors.append(_err(None, f"Malformed input: {inp!r}.", "Each input needs {name, type}."))
            continue
        name = inp["name"]
        if name in input_types:
            errors.append(_err(None, f"Duplicate input name: {name!r}.", "Input names must be unique."))
        t = inp.get("type", "any")
        if t not in TYPES:
            errors.append(_err(inp["name"], f"Unknown input type {t!r}.", f"Use one of {', '.join(TYPES)}."))
        input_types[name] = t if t in TYPES else "any"

    # --- nodes ------------------------------------------------------------
    output_types: dict[str, str] = {}  # node id -> output type (for downstream checks)
    seen_ids: set[str] = set()

    def resolve_type(arg) -> str | None:
        """Best-effort static type of an Arg, or None if indeterminate."""
        kind = _arg_kind(arg)
        if kind == "input":
            return input_types.get(arg["input"])
        if kind == "ref":
            return output_types.get(arg["ref"])
        if kind == "const":
            v = arg["const"]
            from .types import python_type_of
            return python_type_of(v)
        return None

    for node in nodes:
        if not isinstance(node, dict) or "id" not in node or "op" not in node:
            errors.append(_err(None, f"Malformed node: {node!r}.", "Each node needs {id, op, args}."))
            continue
        nid = node["id"]
        if nid in seen_ids:
            errors.append(_err(nid, f"Duplicate node id: {nid!r}.", "Node ids must be unique."))
        seen_ids.add(nid)

        prim = REGISTRY.get(node["op"])
        if prim is None:
            errors.append(_err(nid, f"Unknown op: {node['op']!r}.",
                               f"Valid ops (see list_primitives): {', '.join(sorted(list(REGISTRY))[:12])}…"))
            output_types[nid] = "any"
            continue
        output_types[nid] = prim.output

        args = node.get("args", {})
        if not isinstance(args, dict):
            errors.append(_err(nid, "args must be a map.", "Map each param name to an Arg."))
            continue

        # Required params present and well-formed.
        declared = {n: (t, req) for n, t, req in prim.inputs}
        for pname, (ptype, required) in declared.items():
            if required and pname not in args:
                errors.append(_err(nid, f"Missing required arg '{pname}' for op {node['op']!r}.",
                                   f"Spec: {', '.join(f'{n}:{t}' for n, t, _ in prim.inputs)}."))
            elif pname in args:
                kind = _arg_kind(args[pname])
                if kind is None:
                    errors.append(_err(nid, f"Arg '{pname}' must be exactly one of input/ref/const.",
                                       'e.g. "qty": {"input": "items"} or "limit": {"const": 3}'))
                elif kind == "input" and args[pname]["input"] not in input_types:
                    errors.append(_err(nid, f"Arg '{pname}' references unknown input {args[pname]['input']!r}.",
                                       f"Known inputs: {', '.join(input_types) or '(none)'}"))
                elif kind == "ref" and args[pname]["ref"] not in seen_ids:
                    errors.append(_err(nid, f"Arg '{pname}' references unknown/future node {args[pname]['ref']!r}.",
                                       "Nodes execute in order; only prior nodes may be referenced."))
                else:
                    # Type compatibility (best-effort; skip if indeterminate).
                    got = resolve_type(args[pname])
                    if got is not None and not are_compatible(got, ptype):
                        errors.append(_err(nid, f"Arg '{pname}' has type {got!r}, expected {ptype!r}.",
                                           "Convert with to_str/to_int/to_float or fix the producing node."))
                    if kind == "const":
                        decl = inp_types_for(declared.get(pname), args)
                        if decl is not None and not check_literal(args[pname]["const"], decl):
                            errors.append(_err(nid, f"Literal for '{pname}' doesn't match {decl!r}.",
                                               "Fix the literal or the op choice."))

        # Unknown extra args: warn-grade only for variadic ops, else hint.
        for extra in args:
            if extra not in declared and node["op"] not in ("dict_build", "list_build", "template", "emit",
                                                             "get_field", "map_lookup"):
                errors.append(_err(nid, f"Unknown arg '{extra}' for op {node['op']!r}.",
                                   f"Spec: {', '.join(f'{n}:{t}' for n, t, _ in prim.inputs)}"))

        # Guard, if present, must be a bool-producing Arg.
        if "guard" in node:
            if _arg_kind(node["guard"]) is None:
                errors.append(_err(nid, "guard must be exactly one of input/ref/const.", "e.g. \"guard\": {\"ref\": \"n_lt\"}"))
            else:
                gt = resolve_type(node["guard"])
                if gt is not None and not are_compatible(gt, "bool"):
                    errors.append(_err(nid, f"guard has type {gt!r}, expected bool.", "Produce the guard with a comparison op."))

    # --- outputs ----------------------------------------------------------
    if not isinstance(outputs, dict):
        errors.append(_err(None, "outputs must be a map of name->Arg.", 'e.g. {"total": {"ref": "n_total"}}'))
    else:
        for oname, oarg in outputs.items():
            kind = _arg_kind(oarg)
            if kind is None:
                errors.append(_err(None, f"Output {oname!r} must be exactly one of input/ref/const.", "Map each output name to an Arg."))
            elif kind == "input" and oarg["input"] not in input_types:
                errors.append(_err(None, f"Output {oname!r} references unknown input {oarg['input']!r}.", "Fix the input name."))
            elif kind == "ref" and oarg["ref"] not in seen_ids:
                errors.append(_err(None, f"Output {oname!r} references unknown node {oarg['ref']!r}.", "Fix the ref or add the node."))

    # Earliest-definition check (shadows impossible since ids unique, but
    # input/node name collisions confuse the resolver — flag them).
    for inp_name in input_types:
        if inp_name in seen_ids:
            errors.append(_err(inp_name, f"Node id {inp_name!r} collides with an input name.", "Rename the node or input."))

    return ValidationResult(errors)


def inp_types_for(declared_pair, args):
    return declared_pair[0] if declared_pair else None
