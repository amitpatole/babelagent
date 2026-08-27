"""A key-free demo line: a broken station gated to FAIL, then a fixed one to PASS.

No network, no API key — proves the factory + gate + assembly line end to end.
"""

from __future__ import annotations

from ..core.agent import Context
from ..core.line import Factory
from ..core.part import Part
from ..core.verdict import Result

DEMO_TEXT = (
    "The assembly line turns raw material into a finished product, "
    "one station at a time, and checks the work as it goes."
)


def nonempty_check(part: Part, ctx: Context) -> Result:
    """Gate: a station's output must be a non-empty string."""
    payload = part.payload
    if isinstance(payload, str) and payload.strip():
        return Result.passed("output has content")
    return Result.failed("output is empty")


def broken_summarize(text: str) -> str:
    """The bug: forgets to actually produce a summary."""
    return ""


def fixed_summarize(text: str) -> str:
    """The fix: a real (trivial) extractive summary."""
    words = text.split()
    head = " ".join(words[:8])
    return f"[{len(words)} words] {head}" + ("…" if len(words) > 8 else "")


def build_broken() -> Factory:
    return Factory().station("summarize", broken_summarize, check=nonempty_check, gate="warn")


def build_fixed() -> Factory:
    return Factory().station("summarize", fixed_summarize, check=nonempty_check, gate="warn")
