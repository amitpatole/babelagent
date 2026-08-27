"""Wrap any Python callable as an :class:`~babelagent.core.agent.Agent`."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from ..core.agent import Context
from ..core.message import Message
from .base import bind_payload, infer_io_schema


class CallableAgent:
    """Adapts a plain callable into a graph agent.

    Sync callables run in a worker thread so they never block the event loop.
    The callable's return value becomes the next message's payload (unless it
    already returns a :class:`Message`).

    Timeout caveat (residual): a node ``timeout_s`` / run ``deadline_s`` cancels
    the awaiting coroutine, but Python cannot force-kill the worker thread, so a
    *blocked* sync callable keeps running until it returns on its own (the run
    still reports the timeout). For untrusted or possibly-blocking work, prefer
    an async agent or an out-of-process agent, which can be interrupted.
    """

    def __init__(self, fn: Callable[..., Any], *, name: str | None = None) -> None:
        if not callable(fn):
            raise TypeError(f"CallableAgent needs a callable, got {type(fn).__name__}")
        self.fn = fn
        self.name = name or getattr(fn, "__name__", None) or type(fn).__name__
        dunder_call = getattr(type(fn), "__call__", None)  # noqa: B004 — async detection, not a callability test
        self._is_async = inspect.iscoroutinefunction(fn) or inspect.iscoroutinefunction(
            dunder_call
        )
        try:
            self._sig: inspect.Signature | None = inspect.signature(fn)
        except (TypeError, ValueError):
            self._sig = None
        self.io_schema = infer_io_schema(fn)

    async def run(self, message: Message, ctx: Context) -> Message:
        args, kwargs = bind_payload(message.payload, self._sig)
        if self._is_async:
            out = await self.fn(*args, **kwargs)
        else:
            out = await asyncio.to_thread(self.fn, *args, **kwargs)
        # A plain function may itself RETURN a coroutine/awaitable (e.g. it wraps
        # an async client). Await it so the payload is the value, not a coroutine.
        if inspect.isawaitable(out):
            out = await out
        if isinstance(out, Message):
            return out
        return message.with_payload(out, node=self.name)
