"""Native (dependency-free) quality verdict for optional per-station gating.

BYOA is fully independent of the ``agentsensory`` contract by design. These are
its own light verdict types; an optional ``[agentsensory]`` bridge can map them
onto that contract's ``Report`` for organism users.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from .agent import Context
    from .part import Part


class Verdict(str, Enum):
    """A station's quality judgement."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

    @property
    def rank(self) -> int:
        return {"pass": 0, "warn": 1, "fail": 2}[self.value]

    @classmethod
    def worst(cls, verdicts: list[Verdict]) -> Verdict:
        """The most severe verdict in a set (PASS if empty)."""
        if not verdicts:
            return cls.PASS
        return max(verdicts, key=lambda v: v.rank)


class Result(BaseModel):
    """The outcome of a station ``Check``."""

    verdict: Verdict = Verdict.PASS
    reason: str = ""

    @classmethod
    def passed(cls, reason: str = "") -> Result:
        return cls(verdict=Verdict.PASS, reason=reason)

    @classmethod
    def warn(cls, reason: str = "") -> Result:
        return cls(verdict=Verdict.WARN, reason=reason)

    @classmethod
    def failed(cls, reason: str = "") -> Result:
        return cls(verdict=Verdict.FAIL, reason=reason)


class GateMode(str, Enum):
    """How a station's ``Check`` result affects advancement down the line."""

    OFF = "off"
    """Run the check for its verdict, but never block (advisory only)."""
    WARN = "warn"
    """Block only on FAIL; WARN passes through."""
    STRICT = "strict"
    """Block on WARN or FAIL."""

    def blocks(self, verdict: Verdict) -> bool:
        if self is GateMode.OFF:
            return False
        if self is GateMode.WARN:
            return verdict is Verdict.FAIL
        return verdict in (Verdict.WARN, Verdict.FAIL)


# A Check inspects a Part and returns a Result. It may be sync or async.
if TYPE_CHECKING:
    Check = Callable[["Part", "Context"], Result | Awaitable[Result]]


@runtime_checkable
class CheckProtocol(Protocol):
    """Structural type for a station quality check."""

    def __call__(
        self, part: Part, ctx: Context
    ) -> Result | Awaitable[Result]: ...
