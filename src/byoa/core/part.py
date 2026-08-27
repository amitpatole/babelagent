"""The unit that travels down the assembly line: ``Part``, and the finished ``Product``."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Part(BaseModel):
    """A part on the conveyor belt — the typed envelope passed between stations.

    ``payload`` is the data itself (anything). ``meta`` carries provenance and
    per-station annotations that accumulate as the part moves down the line.
    ``content_type`` is an optional, informational schema hint.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    payload: Any = None
    meta: dict[str, Any] = Field(default_factory=dict)
    content_type: str | None = None

    def with_payload(self, payload: Any, **meta: Any) -> Part:
        """Return a copy carrying a new payload and merged metadata."""
        new_meta = {**self.meta, **meta}
        return Part(payload=payload, meta=new_meta, content_type=self.content_type)

    def annotate(self, **meta: Any) -> Part:
        """Return a copy with additional metadata merged in."""
        return Part(payload=self.payload, meta={**self.meta, **meta}, content_type=self.content_type)


class Product(BaseModel):
    """What the assembly line produces: the final output plus a run trace."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output: Any = None
    ok: bool = True
    verdict: str = "pass"
    trace: list[dict[str, Any]] = Field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok
