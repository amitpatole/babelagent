"""Building and running the graph: ``Graph`` assembles it, ``CompiledGraph`` runs it."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from .agent import Agent, Context, IdentityAgent, is_agent
from .grade import GateMode
from .message import Message, Result
from .node import BarrierKind, BarrierPolicy, Node
from .scheduler import DEFAULT_CONCURRENCY, run_topology
from .topology import Topology

# Grace added to the run deadline before the hard guillotine fires.
_GUILLOTINE_GRACE_S = 1.0

_BARRIER_ALIASES = {
    "all": BarrierKind.ALL,
    "k_of_n": BarrierKind.K_OF_N,
    "any": BarrierKind.K_OF_N,  # any == k_of_n with k=1
    "optional": BarrierKind.OPTIONAL,
}


def _coerce_agent(agent: Any, name: str) -> Agent:
    """Accept an Agent as-is; otherwise adapt it on the fly."""
    if is_agent(agent):
        return agent
    from ..adapters.auto import adapt  # lazy: keeps core import-independent

    return adapt(agent, name=name)


def _coerce_barrier(barrier: str | BarrierKind, k: int | None) -> BarrierPolicy:
    if isinstance(barrier, BarrierKind):
        kind = barrier
    else:
        try:
            kind = _BARRIER_ALIASES[barrier]
        except KeyError as exc:
            raise ValueError(
                f"unknown barrier {barrier!r}; use one of {sorted(_BARRIER_ALIASES)}"
            ) from exc
    if kind is BarrierKind.K_OF_N and k is None:
        k = 1
    return BarrierPolicy(kind=kind, k=k)


class Graph:
    """Assembles a graph of communicating agents.

    Two styles, mixable:

    * **Linear** ``Graph().node("a", A).node("b", B)`` chains each node after
      the previous one, so A hands its message to B.
    * **DAG** pass ``after=[...]`` to wire explicit dependencies, and
      ``barrier`` / ``k`` to control fan-in (agent-to-agent) join semantics.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._last: str | None = None

    def node(
        self,
        name: str,
        agent: Any,
        *,
        after: list[str] | None = None,
        check: Any = None,
        gate: GateMode | str = GateMode.WARN,
        timeout_s: float | None = None,
        barrier: str | BarrierKind = "all",
        k: int | None = None,
        resource: str | None = None,
    ) -> Graph:
        if name in self._nodes:
            raise ValueError(f"duplicate node name {name!r}")
        if after is None:
            after = [self._last] if self._last is not None else []
        gate_mode = gate if isinstance(gate, GateMode) else GateMode(gate)
        self._nodes[name] = Node(
            name=name,
            agent=_coerce_agent(agent, name),
            check=check,
            gate=gate_mode,
            timeout_s=timeout_s,
            after=list(after),
            barrier=_coerce_barrier(barrier, k),
            resource=resource,
        )
        self._last = name
        return self

    def join(
        self,
        name: str,
        *,
        after: list[str],
        agent: Any = None,
        barrier: str | BarrierKind = "all",
        k: int | None = None,
        **kwargs: Any,
    ) -> Graph:
        """Explicit fan-in node. Defaults to a pass-through :class:`IdentityAgent`.

        A join ALWAYS hands its agent a dict keyed by the (surviving) upstream
        node names, even for a single upstream, so the input shape is stable.
        """
        self.node(
            name,
            agent if agent is not None else IdentityAgent(name),
            after=after,
            barrier=barrier,
            k=k,
            **kwargs,
        )
        self._nodes[name].join = True  # mark as an explicit fan-in
        return self

    def compile(self) -> CompiledGraph:
        topo = Topology(nodes=dict(self._nodes)).validate()
        return CompiledGraph(topo)

    async def run(self, payload: Any = None, **kwargs: Any) -> Result:
        """Convenience: compile and run in one call."""
        return await self.compile().run(payload, **kwargs)


class CompiledGraph:
    """A compiled, validated graph ready to exchange messages between agents."""

    def __init__(self, topology: Topology) -> None:
        self.topology = topology

    async def run(
        self,
        payload: Any = None,
        *,
        context: Context | None = None,
        deadline_s: float | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        resource_limits: dict[str, int] | None = None,
    ) -> Result:
        message = payload if isinstance(payload, Message) else Message(payload=payload)
        if context is None:
            deadline = time.monotonic() + deadline_s if deadline_s is not None else None
            context = Context(run_id=uuid.uuid4().hex, deadline=deadline)
        run = run_topology(
            self.topology, message, context,
            concurrency=concurrency, resource_limits=resource_limits,
        )
        if deadline_s is None:
            return await run
        # Hard wall-clock guillotine: per-node cancellation can be defeated by an
        # agent that swallows CancelledError, so bound the whole run and abandon
        # (rather than await) any stuck node tasks. Orphaned tasks from truly
        # hostile async agents may linger until they yield — documented residual.
        try:
            return await asyncio.wait_for(run, deadline_s + _GUILLOTINE_GRACE_S)
        except TimeoutError:
            return Result(
                output=None,
                ok=False,
                verdict="fail",
                trace=[{"node": "<run>", "state": "failed", "verdict": None,
                        "reason": "run exceeded hard deadline", "elapsed_ms": 0,
                        "errored": False}],
            )

    def spec(self) -> dict[str, Any]:
        """JSON-serializable topology (for ``babelagent inspect``)."""
        return self.topology.topo_spec()
