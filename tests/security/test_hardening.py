"""Regression tests pinning the security-cadence fixes. Each maps to a finding."""

from __future__ import annotations

import httpx
import pytest

from babelagent import Graph, Message
from babelagent.adapters import a2a_agent, http_agent
from babelagent.adapters.http_agent import HttpAgent, _read_capped, guard_url
from babelagent.core.agent import Context
from babelagent.core.errors import AdapterError

# --- SSRF: guard_url allowlist (network #2/#4, code F5) ---------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",   # cloud metadata (link-local)
        "http://[::ffff:169.254.169.254]/",           # IPv4-mapped IPv6 bypass
        "http://127.0.0.1/",                          # loopback
        "http://10.0.0.5/",                           # private
        "http://0.0.0.0/",                            # unspecified
        "http://[::1]/",                              # ipv6 loopback
        "http://224.0.0.1/",                          # multicast
        "http://[64:ff9b::a9fe:a9fe]/",               # NAT64 -> 169.254.169.254 (round-1 R1-1)
        "http://[64:ff9b::7f00:1]/",                  # NAT64 -> 127.0.0.1
        "http://[2002:a9fe:a9fe::]/",                 # 6to4 -> 169.254.169.254
        "http://[::a9fe:a9fe]/",                      # IPv4-compatible -> 169.254.169.254
        "http://[64:ff9b::0a00:5]/",                  # NAT64 -> 10.0.0.5 (private)
    ],
)
def test_guard_url_blocks_internal(url):
    with pytest.raises(AdapterError):
        guard_url(url)


def test_guard_url_allows_public():
    assert guard_url("http://8.8.8.8/") == "http://8.8.8.8/"


def test_guard_url_rejects_bad_scheme():
    with pytest.raises(AdapterError, match="scheme"):
        guard_url("file:///etc/passwd")


# --- SSRF: redirects are not followed (network #3) --------------------------

async def test_redirect_not_followed(monkeypatch):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(
        http_agent.httpx, "AsyncClient",
        lambda *a, **k: real(*a, transport=transport, **{x: y for x, y in k.items() if x != "transport"}),
    )
    agent = HttpAgent("http://svc.internal.example/", allow_private=True)
    # The redirect is not followed, so the request fails instead of silently
    # dialing the internal target. The security property: the target of the
    # redirect is never requested.
    with pytest.raises(httpx.HTTPStatusError):
        await agent.run(Message(payload={"x": 1}), Context(run_id="t"))
    assert len(calls) == 1
    assert "169.254.169.254" not in "".join(calls)


# --- Upstream response size cap (network #5) --------------------------------

async def test_read_capped_rejects_oversize():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 500)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        async with client.stream("GET", "http://svc/") as resp:
            with pytest.raises(AdapterError, match="size cap"):
                await _read_capped(resp, cap=100)


def test_a2a_reuses_capped_reader():
    # The A2A adapter imports the shared capped reader (no divergent path).
    assert a2a_agent._read_capped is _read_capped


# --- _safe depth guard (network trace note, code F2) ------------------------

def test_safe_bounds_deep_nesting():
    from babelagent.io.rest import _safe

    d: dict = {}
    for _ in range(5000):
        d = {"x": d}
    out = _safe(d)  # must not raise RecursionError
    s = repr(out)
    assert "truncated" in s


# --- Trace redaction: exception text never leaks over REST (network trace) --

def test_rest_trace_redacts_exception_message():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from babelagent.config import Settings
    from babelagent.io.rest import build_app

    def boom(_):
        raise RuntimeError("SENSITIVE_INTERNAL_PATH=/etc/secret")

    app = build_app(Graph().node("boom", boom), settings=Settings())
    client = TestClient(app, base_url="http://127.0.0.1")
    r = client.post("/run", json={"payload": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    text = r.text
    assert "SENSITIVE_INTERNAL_PATH" not in text
    assert "RuntimeError" not in text
    boom_rec = next(rec for rec in body["trace"] if rec["node"] == "boom")
    assert boom_rec["reason"] == "error"
    assert "errored" not in boom_rec  # stripped from the public trace


def test_library_trace_keeps_detail_for_local_debug():
    import asyncio

    def boom(_):
        raise RuntimeError("local-detail-ok")

    result = asyncio.run(Graph().node("boom", boom).run("x"))
    rec = result.trace[0]
    # Full detail retained for the trusted, in-process caller.
    assert "local-detail-ok" in rec["reason"] and rec["errored"] is True


# --- REST deadline_s clamp (network #1) -------------------------------------

@pytest.mark.parametrize("bad", ["inf", "nan", "-1", "-inf", "0"])
def test_rest_rejects_bad_deadline(bad):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from babelagent.config import Settings
    from babelagent.io.rest import build_app

    client = TestClient(build_app(Graph().node("id", lambda x: x), settings=Settings()), base_url="http://127.0.0.1")
    r = client.post("/run", json={"payload": "x", "deadline_s": bad})
    assert r.status_code == 400


def test_rest_clamps_huge_deadline():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from babelagent.config import Settings
    from babelagent.io.rest import build_app

    client = TestClient(
        build_app(Graph().node("id", lambda x: x), settings=Settings(request_timeout_s=5.0)),
        base_url="http://127.0.0.1",
    )
    r = client.post("/run", json={"payload": "hi", "deadline_s": 1e18})
    assert r.status_code == 200  # accepted but clamped to the server ceiling
    assert r.json()["output"] == "hi"


# --- Plugin discovery opt-out (code F4) -------------------------------------

def test_plugin_discovery_opt_out(monkeypatch):
    import babelagent.adapters.auto as auto

    monkeypatch.setenv("BABELAGENT_NO_PLUGINS", "1")
    monkeypatch.setattr(auto, "_ENTRYPOINTS_LOADED", False)
    loaded: list[str] = []
    monkeypatch.setattr(auto, "register_adapter", lambda *a, **k: loaded.append(a[0]))
    auto._load_entrypoint_adapters()
    assert loaded == []  # discovery skipped, no plugin code enumerated


# --- Round 1: bind_payload kwargs-injection (R1-2) --------------------------

def test_bind_payload_blocks_kwarg_injection():
    import inspect

    from babelagent.adapters.base import bind_payload

    def transfer(amount, to, *, admin=False):
        return (amount, to, admin)

    sig = inspect.signature(transfer)
    # Malicious upstream output tries to flip the admin flag -> must NOT spread.
    args, kwargs = bind_payload({"amount": 1, "to": "x", "admin": True}, sig)
    assert kwargs == {}
    assert args == ({"amount": 1, "to": "x", "admin": True},)
    # Legit dict matching exactly the required params still spreads.
    args2, kwargs2 = bind_payload({"amount": 1, "to": "x"}, sig)
    assert args2 == () and kwargs2 == {"amount": 1, "to": "x"}


def test_bind_payload_never_spreads_into_var_kw():
    import inspect

    from babelagent.adapters.base import bind_payload

    def sink(a, **kwargs):
        return kwargs

    sig = inspect.signature(sink)
    args, kwargs = bind_payload({"a": 1, "evil": "x"}, sig)
    # a single positional; nothing injected wholesale into **kwargs
    assert kwargs == {} and args == ({"a": 1, "evil": "x"},)


# --- Round 1: _safe bounds wide / shared-reference output (R1-3) ------------

def test_safe_bounds_wide_shared_output():
    from babelagent.io.rest import _safe

    level = [1, 2, 3]
    for _ in range(40):  # 2**40 visits without a budget -> would hang
        level = [level, level]
    out = _safe(level)  # must return promptly via the node budget
    assert "truncated" in repr(out)


# --- Round 1: REST Host check defeats browser DNS-rebind (R1-4) --------------

def test_rest_rejects_foreign_host():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from babelagent.config import Settings
    from babelagent.io.rest import build_app

    app = build_app(Graph().node("id", lambda x: x), settings=Settings())
    client = TestClient(app, base_url="http://attacker.example")
    assert client.get("/health").status_code == 200          # health is open
    assert client.post("/run", json={"payload": "x"}).status_code == 403  # rebind blocked
