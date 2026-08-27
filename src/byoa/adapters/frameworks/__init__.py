"""Adapters for third-party agent frameworks (LangChain, CrewAI, AutoGen).

Detection is by the wrapped object's module/attributes, so importing this
package never imports the frameworks themselves.
"""

from __future__ import annotations

from typing import Any

from ...core.agent import Context
from ...core.part import Part


def looks_like_langchain(obj: Any) -> bool:
    mod = type(obj).__module__ or ""
    return mod.startswith(("langchain", "langgraph")) and hasattr(obj, "invoke")


def looks_like_crewai(obj: Any) -> bool:
    mod = type(obj).__module__ or ""
    return mod.startswith("crewai") and hasattr(obj, "kickoff")


def looks_like_autogen(obj: Any) -> bool:
    mod = type(obj).__module__ or ""
    return mod.startswith(("autogen", "pyautogen")) and (
        hasattr(obj, "generate_reply") or hasattr(obj, "run")
    )


class LangChainAgent:
    """Wraps a LangChain / LangGraph Runnable (anything with ``.invoke``)."""

    def __init__(self, runnable: Any, *, name: str | None = None) -> None:
        self.runnable = runnable
        self.name = name or type(runnable).__name__

    async def run(self, part: Part, ctx: Context) -> Part:
        if hasattr(self.runnable, "ainvoke"):
            out = await self.runnable.ainvoke(part.payload)
        else:
            import asyncio

            out = await asyncio.to_thread(self.runnable.invoke, part.payload)
        out = getattr(out, "content", out)
        return part.with_payload(out, station=self.name)


class CrewAgent:
    """Wraps a CrewAI Crew (anything with ``.kickoff``)."""

    def __init__(self, crew: Any, *, name: str | None = None) -> None:
        self.crew = crew
        self.name = name or type(crew).__name__

    async def run(self, part: Part, ctx: Context) -> Part:
        import asyncio

        inputs = part.payload if isinstance(part.payload, dict) else {"input": part.payload}
        out = await asyncio.to_thread(self.crew.kickoff, inputs)
        out = getattr(out, "raw", out)
        return part.with_payload(out, station=self.name)


class AutoGenAgent:
    """Wraps an AutoGen agent (``.generate_reply`` / ``.run``)."""

    def __init__(self, agent: Any, *, name: str | None = None) -> None:
        self.agent = agent
        self.name = name or type(agent).__name__

    async def run(self, part: Part, ctx: Context) -> Part:
        import asyncio

        if hasattr(self.agent, "generate_reply"):
            msg = [{"role": "user", "content": str(part.payload)}]
            out = await asyncio.to_thread(self.agent.generate_reply, msg)
        else:
            out = await asyncio.to_thread(self.agent.run, part.payload)
        return part.with_payload(out, station=self.name)
