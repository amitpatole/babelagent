"""What flows between agents: a ``Message``, and the final ``Result``."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    """The envelope passed from one agent to the next.

    ``payload`` is the data itself (anything). ``meta`` carries provenance and
    annotations that accumulate as the message travels between agents.
    ``content_type`` is an optional, informational schema hint.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    payload: Any = None
    meta: dict[str, Any] = Field(default_factory=dict)
    content_type: str | None = None

    def with_payload(self, payload: Any, **meta: Any) -> Message:
        """Return a copy carrying a new payload and merged metadata."""
        new_meta = {**self.meta, **meta}
        return Message(payload=payload, meta=new_meta, content_type=self.content_type)

    def annotate(self, **meta: Any) -> Message:
        """Return a copy with additional metadata merged in."""
        return Message(
            payload=self.payload, meta={**self.meta, **meta}, content_type=self.content_type
        )


class Result(BaseModel):
    """What a run returns: the final output plus a full trace of the exchange."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output: Any = None
    ok: bool = True
    verdict: str = "pass"
    trace: list[dict[str, Any]] = Field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok
