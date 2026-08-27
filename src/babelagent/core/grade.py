"""Native, dependency-free quality types for optional per-node gating.

Babelagent owns its own light verdict types rather than importing an external
contract, so the base install stays dependency-free.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from .agent import Context
    from .message import Message


class Verdict(str, Enum):
    """A node's quality judgement."""

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


class Grade(BaseModel):
    """The outcome of a node ``Check``: a verdict plus a human reason."""

    verdict: Verdict = Verdict.PASS
    reason: str = ""

    @classmethod
    def passed(cls, reason: str = "") -> Grade:
        return cls(verdict=Verdict.PASS, reason=reason)

    @classmethod
    def warn(cls, reason: str = "") -> Grade:
        return cls(verdict=Verdict.WARN, reason=reason)

    @classmethod
    def failed(cls, reason: str = "") -> Grade:
        return cls(verdict=Verdict.FAIL, reason=reason)


class GateMode(str, Enum):
    """How a node's ``Check`` grade affects the exchange."""

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


# A Check inspects a Message and returns a Grade. It may be sync or async.
if TYPE_CHECKING:
    Check = Callable[["Message", "Context"], Grade | Awaitable[Grade]]


@runtime_checkable
class CheckProtocol(Protocol):
    """Structural type for a node quality check."""

    def __call__(self, message: Message, ctx: Context) -> Grade | Awaitable[Grade]: ...
