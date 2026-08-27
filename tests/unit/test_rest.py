"""The hardened REST interface: run, auth, and the body cap."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from babelagent.config import Settings  # noqa: E402
from babelagent.io._demo_assets import build_fixed  # noqa: E402
from babelagent.io.rest import build_app  # noqa: E402


def _client(**settings_kwargs) -> TestClient:
    app = build_app(build_fixed(), settings=Settings(**settings_kwargs))
    return TestClient(app)


def test_health_no_auth():
    r = _client().get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_run_produces_result():
    r = _client().post("/run", json={"payload": "hello there friend"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["verdict"] == "pass"
    assert isinstance(body["output"], str)


def test_auth_required_when_token_set():
    client = _client(api_token="secret")
    assert client.post("/run", json={"payload": "x"}).status_code == 401
    ok = client.post(
        "/run", json={"payload": "hello there"}, headers={"Authorization": "Bearer secret"}
    )
    assert ok.status_code == 200


def test_wrong_token_rejected():
    client = _client(api_token="secret")
    r = client.post(
        "/run", json={"payload": "x"}, headers={"Authorization": "Bearer nope"}
    )
    assert r.status_code == 401


def test_body_cap_enforced():
    client = _client(max_body_bytes=64)
    big = {"payload": "x" * 500}
    r = client.post("/run", json=big)
    assert r.status_code == 413


def test_invalid_json_rejected():
    r = _client().post("/run", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 400
