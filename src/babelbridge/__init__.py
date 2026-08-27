"""Babelbridge — one common tongue for agents that were never meant to talk.

A neutral layer that lets heterogeneous agents (plain callables, HTTP/OpenAPI
endpoints, MCP tools, framework agents, or LLMs) exchange messages and
collaborate on a task, agent-to-agent, under one shared interface.

    from babelbridge import Graph, adapt

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
    BabelbridgeError,
    CycleError,
    MissingDependencyError,
    TopologyError,
)

__version__ = "0.1.0"

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
    "BabelbridgeError",
    "AdapterError",
    "CycleError",
    "TopologyError",
    "MissingDependencyError",
]

# adapt() and the registry live in the adapters package; expose lazily so that
# importing babelbridge never eagerly pulls optional adapter dependencies.
_LAZY = {"adapt", "register_adapter"}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        from . import adapters

        return getattr(adapters, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
