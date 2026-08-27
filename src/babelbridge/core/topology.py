"""The graph topology: nodes, dependency edges, and barrier policies.

A ``Topology`` is the DAG the scheduler executes. Its shape is JSON-serializable
for inspection (``topo_spec``); the live agents themselves are not serialized
(they are brought at build time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import CycleError, TopologyError
from .node import BarrierKind, Node


@dataclass
class Topology:
    """A compiled, validated graph of communicating agents."""

    nodes: dict[str, Node] = field(default_factory=dict)

    def validate(self) -> Topology:
        """Check for dangling dependencies and cycles; raise on either."""
        for name, node in self.nodes.items():
            for dep in node.after:
                if dep not in self.nodes:
                    raise TopologyError(f"node {name!r} depends on unknown node {dep!r}")
                if dep == name:
                    raise CycleError(f"node {name!r} depends on itself")
            if node.barrier.kind is BarrierKind.K_OF_N:
                k = node.barrier.k or 0
                if k > len(node.after):
                    raise TopologyError(
                        f"node {name!r} needs k={k} but has only "
                        f"{len(node.after)} upstream(s)"
                    )
        self._assert_acyclic()
        return self

    def _assert_acyclic(self) -> None:
        # Kahn's algorithm: if we cannot remove every node, there is a cycle.
        indeg = {name: len(node.after) for name, node in self.nodes.items()}
        ready = [n for n, d in indeg.items() if d == 0]
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
            raise CycleError(f"graph has a cycle involving: {', '.join(stuck)}")

    def roots(self) -> list[str]:
        return [n for n, node in self.nodes.items() if not node.after]

    def terminals(self) -> list[str]:
        """Nodes that no other node depends on (the graph's outputs)."""
        depended: set[str] = set()
        for node in self.nodes.values():
            depended.update(node.after)
        return [n for n in self.nodes if n not in depended]

    def topo_spec(self) -> dict[str, Any]:
        """A JSON-serializable description of the topology (for inspection)."""
        return {
            "nodes": [
                {
                    "name": name,
                    "agent": getattr(node.agent, "name", type(node.agent).__name__),
                    "after": list(node.after),
                    "barrier": node.barrier.kind.value,
                    "k": node.barrier.k,
                    "gate": node.gate.value,
                    "has_check": node.check is not None,
                }
                for name, node in self.nodes.items()
            ],
            "roots": self.roots(),
            "terminals": self.terminals(),
        }
