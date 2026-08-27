"""A node: one participant in the graph — an agent, its wiring, and an optional gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .agent import Agent
from .errors import TopologyError
from .grade import GateMode


class BarrierKind(str, Enum):
    """When a node with multiple upstreams becomes ready to run."""

    ALL = "all"
    """Every upstream must succeed."""
    K_OF_N = "k_of_n"
    """At least ``k`` upstreams must succeed."""
    OPTIONAL = "optional"
    """Proceed once settled if at least one upstream succeeded; skip the node if
    none did (there would be nothing to hand it)."""


@dataclass
class BarrierPolicy:
    kind: BarrierKind = BarrierKind.ALL
    k: int | None = None

    def __post_init__(self) -> None:
        if self.kind is BarrierKind.K_OF_N and (self.k is None or self.k < 1):
            raise TopologyError("k_of_n barrier requires k >= 1")


@dataclass
class Node:
    """A node in the graph: an agent, its upstream dependencies, and its gate.

    Wraps a single :class:`Agent`, an optional quality ``check`` whose grade can
    gate the exchange (per ``gate`` mode), an optional per-node ``timeout_s``,
    the ``after`` list of upstream node names, and the fan-in ``barrier``.
    """

    name: str
    agent: Agent
    check: Any | None = None  # grade.Check (sync or async); Any keeps runtime light
    gate: GateMode = GateMode.WARN
    timeout_s: float | None = None
    after: list[str] = field(default_factory=list)
    barrier: BarrierPolicy = field(default_factory=BarrierPolicy)
    join: bool = False  # explicit fan-in: always receives a dict keyed by upstream
