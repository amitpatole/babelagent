"""The A2A adapter: parsing, adapt() recognition, and a mocked round-trip."""

from __future__ import annotations

import httpx
import pytest

from babelagent import Message, adapt
from babelagent.adapters import a2a_agent
from babelagent.adapters.a2a_agent import A2AAgent, A2ARef, _extract_text
from babelagent.core.agent import Context


def test_extract_text_from_message():
    result = {"parts": [{"kind": "text", "text": "hello "}, {"kind": "text", "text": "world"}]}
    assert _extract_text(result) == "hello world"


def test_extract_text_from_task_artifacts():
    result = {
        "status": {"state": "completed"},
        "artifacts": [{"parts": [{"kind": "text", "text": "answer"}]}],
    }
    assert _extract_text(result) == "answer"


def test_extract_text_from_status_message():
    result = {"status": {"message": {"parts": [{"kind": "text", "text": "via status"}]}}}
    assert _extract_text(result) == "via status"


def test_adapt_recognizes_a2a_ref():
    agent = adapt(A2ARef("http://localhost:9999", name="remote", allow_private=True))
    assert isinstance(agent, A2AAgent)
    assert agent.name == "remote"


async def test_a2a_run_roundtrip(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b"message/send" in body
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "result": {"parts": [{"kind": "text", "text": "pong"}]},
            },
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=transport, **kwargs)

    monkeypatch.setattr(a2a_agent.httpx, "AsyncClient", fake_client)

    agent = A2AAgent("http://localhost:9999", allow_private=True)
    out = await agent.run(Message(payload="ping"), Context(run_id="t"))
    assert out.payload == "pong"


async def test_a2a_error_response_raises(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "1", "error": {"message": "boom"}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        a2a_agent.httpx,
        "AsyncClient",
        lambda *a, **k: real_client(*a, transport=transport, **{x: y for x, y in k.items() if x != "transport"}),
    )
    agent = A2AAgent("http://localhost:9999", allow_private=True)
    from babelagent.core.errors import AdapterError

    with pytest.raises(AdapterError, match="boom"):
        await agent.run(Message(payload="ping"), Context(run_id="t"))
