"""A key-free demo: a broken node gated to FAIL, then a fixed one to PASS.

No network, no API key. Proves the graph, the agents, and the quality gate end
to end.
"""

from __future__ import annotations

from ..core.agent import Context
from ..core.grade import Grade
from ..core.graph import Graph
from ..core.message import Message

DEMO_TEXT = (
    "Different agents speak different dialects, and Babelagent gives them one "
    "shared tongue so they can hand work to each other and still be checked."
)


def nonempty_check(message: Message, ctx: Context) -> Grade:
    """Gate: a node's output must be a non-empty string."""
    payload = message.payload
    if isinstance(payload, str) and payload.strip():
        return Grade.passed("output has content")
    return Grade.failed("output is empty")


def broken_summarize(text: str) -> str:
    """The bug: forgets to actually produce a summary."""
    return ""


def fixed_summarize(text: str) -> str:
    """The fix: a real (trivial) extractive summary."""
    words = text.split()
    head = " ".join(words[:8])
    return f"[{len(words)} words] {head}" + ("…" if len(words) > 8 else "")


def build_broken() -> Graph:
    return Graph().node("summarize", broken_summarize, check=nonempty_check, gate="warn")


def build_fixed() -> Graph:
    return Graph().node("summarize", fixed_summarize, check=nonempty_check, gate="warn")
