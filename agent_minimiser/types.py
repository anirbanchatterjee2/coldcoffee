"""Type system for Agent Minimiser IR (Phase 2 minimal slice).

Types are deliberately small: a closed set of nominal types with
numeric promotion and an `any` escape hatch.  A richer structural type
system (generics, unions, records) is a future-work item; see
``docs/IR_SPEC.md``.
"""

from __future__ import annotations

# Closed universe of v0.1 types.
TYPES = (
    "str",
    "int",
    "float",
    "money",
    "bool",
    "void",
    "any",
    "list",
    "map",
)

NUMERIC = {"int", "float", "money"}

# Numeric promotion order: int < float < money is *not* a safe lattice in
# general (money is not float), so promotion is only allowed to `float`
# and to `any`.  Money stays exact.
NUMERIC_PROMOTION = {"int": {"int", "float", "any"}, "float": {"float", "any"}, "money": {"money", "any"}}


def are_compatible(provided: str, required: str) -> bool:
    """Return True if a value of type ``provided`` satisfies ``required``.

    v0.1 policy: all numeric types (int/float/money) are mutually
    compatible at validation time — they share float runtime semantics
    and rejecting ``money -> float`` would make ordinary programs
    unexpressible.  Exact-Decimal money is tracked as future work.
    """
    if required == "any" or provided == "any":
        return True
    if provided == required:
        return True
    if provided in NUMERIC and required in NUMERIC:
        return True
    return False


def python_type_of(value) -> str:
    """Map a Python runtime value to an IR type name (for trace/debug)."""
    if value is None:
        return "void"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    return "any"


def check_literal(value, ir_type: str) -> bool:
    """Best-effort literal-vs-declared-type check (used by the validator)."""
    if ir_type == "any" or value is None and ir_type == "void":
        return True
    if ir_type == "str":
        return isinstance(value, str)
    if ir_type == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if ir_type in ("float", "money"):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if ir_type == "bool":
        return isinstance(value, bool)
    if ir_type == "list":
        return isinstance(value, list)
    if ir_type == "map":
        return isinstance(value, dict)
    return True  # unknown annotated types are not rejected in v0.1
