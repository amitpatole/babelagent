"""BYOA core: the dependency-free assembly-line engine."""

from __future__ import annotations

from .agent import Agent, Context, IdentityAgent, is_agent
from .blueprint import BarrierKind, BarrierPolicy, Blueprint, Node
from .errors import (
    AdapterError,
    BlueprintError,
    ByoaError,
    CycleError,
    GateFailed,
    MissingDependencyError,
    StationTimeout,
)
from .line import Factory, Line
from .part import Part, Product
from .scheduler import run_blueprint
from .station import Station
from .verdict import CheckProtocol, GateMode, Result, Verdict

__all__ = [
    "Agent",
    "Context",
    "IdentityAgent",
    "is_agent",
    "BarrierKind",
    "BarrierPolicy",
    "Blueprint",
    "Node",
    "AdapterError",
    "BlueprintError",
    "ByoaError",
    "CycleError",
    "GateFailed",
    "MissingDependencyError",
    "StationTimeout",
    "Factory",
    "Line",
    "Part",
    "Product",
    "run_blueprint",
    "Station",
    "CheckProtocol",
    "GateMode",
    "Result",
    "Verdict",
]
