"""The on-the-fly adapter creator: adapt()."""

from __future__ import annotations

import pytest

from babelbridge import Message, adapt, register_adapter
from babelbridge.core.agent import Context, is_agent
from babelbridge.core.errors import AdapterError


async def _run(agent, payload):
    return await agent.run(Message(payload=payload), Context(run_id="t"))


async def test_adapt_sync_callable():
    agent = adapt(str.upper)
    assert is_agent(agent)
    out = await _run(agent, "hello")
    assert out.payload == "HELLO"


async def test_adapt_async_callable():
    async def double(n):
        return n * 2

    agent = adapt(double)
    out = await _run(agent, 21)
    assert out.payload == 42


async def test_adapt_multiarg_dict_payload():
    def combine(first, second):
        return f"{first}+{second}"

    agent = adapt(combine)
    out = await _run(agent, {"first": "a", "second": "b"})
    assert out.payload == "a+b"


def test_adapt_already_agent_passthrough():
    from babelbridge.core.agent import IdentityAgent

    ident = IdentityAgent("keep")
    assert adapt(ident) is ident


def test_adapt_unknown_raises():
    with pytest.raises(AdapterError, match="don't know how to adapt"):
        adapt(12345)


async def test_register_custom_adapter():
    class Shouter:
        def __init__(self, tag):
            self.name = "shouter"
            self.tag = tag

        async def run(self, message, ctx):
            return message.with_payload(f"{self.tag}!{message.payload}")

    register_adapter(
        "shout",
        matches=lambda o: isinstance(o, str) and o.startswith("shout:"),
        build=lambda o, **kw: Shouter(o.split(":", 1)[1]),
    )
    agent = adapt("shout:hey")
    out = await _run(agent, "world")
    assert out.payload == "hey!world"


async def test_graph_auto_adapts_callable():
    from babelbridge import Graph

    result = await Graph().node("up", str.upper).run("hi")
    assert result.output == "HI"
