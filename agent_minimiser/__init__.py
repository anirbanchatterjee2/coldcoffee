"""Agent Minimiser — agent-native software construction and execution platform.

Public API:
- ``build_order_program()`` / ``ORDER_PROGRAM``: reference demo IR program.
- ``Engine``, ``validate_program``, ``REGISTRY``, ``AgentAPI``, ``explain``.
"""

from .engine import Engine, ExecutionResult
from .ir import validate_program
from .primitives import REGISTRY, list_primitives

__version__ = "0.1.0"

from .agent_api import AgentAPI
from .debugger import explain, render_graph_text
from .demo_order import ORDER_PROGRAM, build_order_program, SAMPLE_INPUTS

__all__ = [
    "Engine",
    "ExecutionResult",
    "validate_program",
    "REGISTRY",
    "list_primitives",
    "AgentAPI",
    "explain",
    "render_graph_text",
    "ORDER_PROGRAM",
    "build_order_program",
    "SAMPLE_INPUTS",
    "__version__",
]
