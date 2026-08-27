"""BYOA — Bring Your Own Agent.

A factory with an assembly line: bring any agent (callable, HTTP/OpenAPI
endpoint, MCP tool, framework agent, or LLM), plug it onto a station, and run
the line to produce what you want.

    from byoa import Factory, adapt

    line = Factory().station("shout", str.upper)
    product = await line.run("hello")   # product.output == "HELLO"
"""

from __future__ import annotations

from typing import Any

from .core import (
    Agent,
    BarrierKind,
    BarrierPolicy,
    Blueprint,
    Context,
    Factory,
    GateMode,
    IdentityAgent,
    Line,
    Part,
    Product,
    Result,
    Station,
    Verdict,
    is_agent,
)
from .core.errors import (
    AdapterError,
    BlueprintError,
    ByoaError,
    CycleError,
    MissingDependencyError,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Factory",
    "Line",
    "Part",
    "Product",
    "Context",
    "Agent",
    "IdentityAgent",
    "is_agent",
    "Station",
    "Blueprint",
    "BarrierKind",
    "BarrierPolicy",
    "GateMode",
    "Result",
    "Verdict",
    "adapt",
    "register_adapter",
    "ByoaError",
    "AdapterError",
    "BlueprintError",
    "CycleError",
    "MissingDependencyError",
]

# adapt() and the registry live in the adapters package; expose lazily so that
# importing byoa never eagerly pulls optional adapter dependencies.
_LAZY = {"adapt", "register_adapter"}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        from . import adapters

        return getattr(adapters, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
