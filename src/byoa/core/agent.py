"""The uniform worker interface every brought agent is normalized to."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .part import Part


@dataclass
class Context:
    """Run-scoped context threaded through every station on the line.

    ``state`` is a shared blackboard for the run. ``deadline`` (a
    ``time.monotonic()`` value) bounds the whole run; individual stations may
    also carry their own timeout.
    """

    run_id: str
    state: dict[str, Any] = field(default_factory=dict)
    deadline: float | None = None

    def remaining(self) -> float | None:
        """Seconds left before the run deadline, or ``None`` if unbounded."""
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - time.monotonic())

    def expired(self) -> bool:
        rem = self.remaining()
        return rem is not None and rem <= 0.0


@runtime_checkable
class Agent(Protocol):
    """A worker on the assembly line.

    Anything a user brings — a callable, an HTTP/OpenAPI endpoint, an MCP tool,
    a framework agent, or an LLM — is adapted to this single async interface.
    """

    name: str

    async def run(self, part: Part, ctx: Context) -> Part: ...


def is_agent(obj: object) -> bool:
    """True if *obj* already conforms to the :class:`Agent` protocol."""
    return (
        hasattr(obj, "name")
        and hasattr(obj, "run")
        and callable(getattr(obj, "run", None))
    )


class IdentityAgent:
    """Pass-through worker — forwards its input part unchanged.

    Handy as the default agent for an explicit fan-in / join node.
    """

    def __init__(self, name: str = "identity") -> None:
        self.name = name

    async def run(self, part: Part, ctx: Context) -> Part:
        return part
