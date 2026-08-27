"""Babelbridge core: the dependency-free graph engine that agents exchange messages on."""

from __future__ import annotations

from .agent import Agent, Context, IdentityAgent, is_agent
from .errors import (
    AdapterError,
    BabelbridgeError,
    CycleError,
    GateFailed,
    MissingDependencyError,
    NodeTimeout,
    TopologyError,
)
from .grade import CheckProtocol, GateMode, Grade, Verdict
from .graph import CompiledGraph, Graph
from .message import Message, Result
from .node import BarrierKind, BarrierPolicy, Node
from .scheduler import run_topology
from .topology import Topology

__all__ = [
    "Agent",
    "Context",
    "IdentityAgent",
    "is_agent",
    "BarrierKind",
    "BarrierPolicy",
    "Node",
    "Topology",
    "AdapterError",
    "BabelbridgeError",
    "CycleError",
    "GateFailed",
    "MissingDependencyError",
    "NodeTimeout",
    "TopologyError",
    "Graph",
    "CompiledGraph",
    "Message",
    "Result",
    "run_topology",
    "CheckProtocol",
    "GateMode",
    "Grade",
    "Verdict",
]
