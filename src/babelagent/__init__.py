"""Babelagent — the Babel that lets AI agents understand each other.

A neutral layer that gives heterogeneous agents (plain callables, HTTP/OpenAPI
endpoints, MCP tools, framework agents, or LLMs) one shared tongue, so they can
exchange messages and collaborate on a task, agent-to-agent, and be graded at
each hop.

    from babelagent import Graph, adapt

    graph = Graph().node("shout", str.upper)
    result = await graph.run("hello")   # result.output == "HELLO"
"""

from __future__ import annotations

from typing import Any

from .core import (
    Agent,
    BarrierKind,
    BarrierPolicy,
    CompiledGraph,
    Context,
    GateMode,
    Grade,
    Graph,
    IdentityAgent,
    Message,
    Node,
    Result,
    Topology,
    Verdict,
    is_agent,
)
from .core.errors import (
    AdapterError,
    BabelagentError,
    CycleError,
    MissingDependencyError,
    TopologyError,
)

__version__ = "0.1.1"

__all__ = [
    "__version__",
    "Graph",
    "CompiledGraph",
    "Message",
    "Result",
    "Context",
    "Agent",
    "IdentityAgent",
    "is_agent",
    "Node",
    "Topology",
    "BarrierKind",
    "BarrierPolicy",
    "GateMode",
    "Grade",
    "Verdict",
    "adapt",
    "register_adapter",
    "A2ARef",
    "McpRef",
    "LLM",
    "BabelagentError",
    "AdapterError",
    "CycleError",
    "TopologyError",
    "MissingDependencyError",
]

# adapt(), the adapter refs, and LLM live in the adapters package; expose them
# lazily so importing babelagent never eagerly pulls optional adapter deps.
_LAZY = {"adapt", "register_adapter", "A2ARef", "McpRef", "LLM"}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        from . import adapters

        return getattr(adapters, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
