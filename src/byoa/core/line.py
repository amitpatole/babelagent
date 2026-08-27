"""The factory floor: ``Factory`` assembles a line, ``Line`` runs it."""

from __future__ import annotations

import time
import uuid
from typing import Any

from .agent import Agent, Context, IdentityAgent, is_agent
from .blueprint import BarrierKind, BarrierPolicy, Blueprint, Node
from .part import Part, Product
from .scheduler import DEFAULT_CONCURRENCY, run_blueprint
from .station import Station
from .verdict import GateMode

_BARRIER_ALIASES = {
    "all": BarrierKind.ALL,
    "k_of_n": BarrierKind.K_OF_N,
    "any": BarrierKind.K_OF_N,  # any == k_of_n with k=1
    "optional": BarrierKind.OPTIONAL,
}


def _coerce_agent(agent: Any, name: str) -> Agent:
    """Accept an Agent as-is; otherwise adapt it on the fly (Phase-2 adapters)."""
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


class Factory:
    """Assembles an assembly line.

    Two styles, mixable:

    * **Linear sugar** — ``Factory().station("a", A).station("b", B)`` chains
      each station after the previous one.
    * **DAG** — pass ``after=[...]`` to wire explicit dependencies, and
      ``barrier`` / ``k`` to control fan-in join semantics.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._last: str | None = None

    def station(
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
    ) -> Factory:
        if name in self._nodes:
            raise ValueError(f"duplicate station name {name!r}")
        if after is None:
            after = [self._last] if self._last is not None else []
        gate_mode = gate if isinstance(gate, GateMode) else GateMode(gate)
        st = Station(
            name=name,
            agent=_coerce_agent(agent, name),
            check=check,
            gate=gate_mode,
            timeout_s=timeout_s,
        )
        self._nodes[name] = Node(
            station=st, after=list(after), barrier=_coerce_barrier(barrier, k)
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
    ) -> Factory:
        """Explicit fan-in node. Defaults to a pass-through :class:`IdentityAgent`."""
        return self.station(
            name,
            agent if agent is not None else IdentityAgent(name),
            after=after,
            barrier=barrier,
            k=k,
            **kwargs,
        )

    def compile(self) -> Line:
        bp = Blueprint(nodes=dict(self._nodes)).validate()
        return Line(bp)

    async def run(self, payload: Any = None, **kwargs: Any) -> Product:
        """Convenience: compile and run in one call."""
        return await self.compile().run(payload, **kwargs)


class Line:
    """A compiled, validated assembly line ready to run parts."""

    def __init__(self, blueprint: Blueprint) -> None:
        self.blueprint = blueprint

    async def run(
        self,
        payload: Any = None,
        *,
        context: Context | None = None,
        deadline_s: float | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> Product:
        part = payload if isinstance(payload, Part) else Part(payload=payload)
        if context is None:
            deadline = time.monotonic() + deadline_s if deadline_s is not None else None
            context = Context(run_id=uuid.uuid4().hex, deadline=deadline)
        return await run_blueprint(
            self.blueprint, part, context, concurrency=concurrency
        )

    def spec(self) -> dict[str, Any]:
        """JSON-serializable topology (for ``byoa inspect``)."""
        return self.blueprint.topo_spec()
