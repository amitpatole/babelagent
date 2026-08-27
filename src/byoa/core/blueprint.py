"""The line topology: nodes, dependency edges, and barrier policies.

A ``Blueprint`` is the DAG the scheduler executes. Its *topology* is JSON-
serializable for inspection (``topo_spec``); the live agents themselves are not
serialized (they are brought at build time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import BlueprintError, CycleError
from .station import Station


class BarrierKind(str, Enum):
    """When a node with multiple upstreams becomes ready to run."""

    ALL = "all"
    """Every upstream must succeed."""
    K_OF_N = "k_of_n"
    """At least ``k`` upstreams must succeed."""
    OPTIONAL = "optional"
    """Proceed once all upstreams have settled, regardless of pass/fail."""


@dataclass
class BarrierPolicy:
    kind: BarrierKind = BarrierKind.ALL
    k: int | None = None

    def __post_init__(self) -> None:
        if self.kind is BarrierKind.K_OF_N:
            if self.k is None or self.k < 1:
                raise BlueprintError("k_of_n barrier requires k >= 1")


@dataclass
class Node:
    """A node in the line: a station plus its upstream dependencies + barrier."""

    station: Station
    after: list[str] = field(default_factory=list)
    barrier: BarrierPolicy = field(default_factory=BarrierPolicy)


@dataclass
class Blueprint:
    """A compiled, validated assembly line topology."""

    nodes: dict[str, Node] = field(default_factory=dict)

    def validate(self) -> Blueprint:
        """Check for dangling dependencies and cycles; raise on either."""
        for name, node in self.nodes.items():
            for dep in node.after:
                if dep not in self.nodes:
                    raise BlueprintError(
                        f"station {name!r} depends on unknown station {dep!r}"
                    )
                if dep == name:
                    raise CycleError(f"station {name!r} depends on itself")
            if node.barrier.kind is BarrierKind.K_OF_N:
                k = node.barrier.k or 0
                if k > len(node.after):
                    raise BlueprintError(
                        f"station {name!r} needs k={k} but has only "
                        f"{len(node.after)} upstream(s)"
                    )
        self._assert_acyclic()
        return self

    def _assert_acyclic(self) -> None:
        # Kahn's algorithm — if we can't remove every node, there's a cycle.
        indeg = {name: len(node.after) for name, node in self.nodes.items()}
        ready = [n for n, d in indeg.items() if d == 0]
        # successors map
        succ: dict[str, list[str]] = {n: [] for n in self.nodes}
        for name, node in self.nodes.items():
            for dep in node.after:
                succ[dep].append(name)
        removed = 0
        while ready:
            cur = ready.pop()
            removed += 1
            for nxt in succ[cur]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
        if removed != len(self.nodes):
            stuck = sorted(n for n, d in indeg.items() if d > 0)
            raise CycleError(f"assembly line has a cycle involving: {', '.join(stuck)}")

    def roots(self) -> list[str]:
        return [n for n, node in self.nodes.items() if not node.after]

    def terminals(self) -> list[str]:
        """Nodes that no other node depends on (the line's outputs)."""
        depended: set[str] = set()
        for node in self.nodes.values():
            depended.update(node.after)
        return [n for n in self.nodes if n not in depended]

    def topo_spec(self) -> dict[str, Any]:
        """A JSON-serializable description of the topology (for inspection)."""
        return {
            "stations": [
                {
                    "name": name,
                    "agent": getattr(node.station.agent, "name", type(node.station.agent).__name__),
                    "after": list(node.after),
                    "barrier": node.barrier.kind.value,
                    "k": node.barrier.k,
                    "gate": node.station.gate.value,
                    "has_check": node.station.check is not None,
                }
                for name, node in self.nodes.items()
            ],
            "roots": self.roots(),
            "terminals": self.terminals(),
        }
