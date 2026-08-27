"""The uniform interface every brought agent is normalized to.

This one shape is the shared language of the graph: every agent, whatever
framework or protocol it came from, speaks it, so any agent can hand work to
any other (agent-to-agent).
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .message import Message


@dataclass
class Context:
    """Run-scoped context threaded through every node in the graph.

    ``state`` is a shared blackboard for the run. ``deadline`` (a
    ``time.monotonic()`` value) bounds the whole run; individual nodes may also
    carry their own timeout.
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
    """A participant in the graph.

    Anything a user brings, a callable, an HTTP/OpenAPI endpoint, an MCP tool, a
    framework agent, or an LLM, is adapted to this single async interface so it
    can exchange messages with every other agent.
    """

    name: str

    async def run(self, message: Message, ctx: Context) -> Message: ...


def is_agent(obj: object) -> bool:
    """True if *obj* already conforms to the :class:`Agent` protocol.

    Checks the shape strictly (a ``name``, and an async ``run`` that accepts a
    message and a context) so a random object that merely happens to have a
    ``.name`` and a ``.run`` is NOT silently accepted and then failed with a
    cryptic TypeError deep inside a run — it gets adapted or rejected up front.
    """
    run = getattr(obj, "run", None)
    if not hasattr(obj, "name") or not callable(run):
        return False
    if not inspect.iscoroutinefunction(run):
        return False
    try:
        inspect.signature(run).bind("message", "ctx")  # accepts (message, ctx)?
    except TypeError:
        return False
    return True


class IdentityAgent:
    """Pass-through participant: forwards its input message unchanged.

    Handy as the default agent for an explicit fan-in / join node.
    """

    def __init__(self, name: str = "identity") -> None:
        self.name = name

    async def run(self, message: Message, ctx: Context) -> Message:
        return message
