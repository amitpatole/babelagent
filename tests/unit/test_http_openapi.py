"""Review fixes for HttpAgent.from_openapi (GET fallback, templated path, servers)."""

from __future__ import annotations

import pytest

from babelagent.adapters.http_agent import HttpAgent
from babelagent.core.errors import AdapterError


def test_from_openapi_falls_back_to_get_only_spec():
    spec = {
        "servers": [{"url": "https://svc.internal"}],
        "paths": {"/items": {"get": {"operationId": "listItems"}}},
    }
    agent = HttpAgent.from_openapi(spec, allow_private=True)
    assert agent.method == "GET"


def test_from_openapi_rejects_templated_path():
    spec = {
        "servers": [{"url": "https://svc.internal"}],
        "paths": {"/items/{id}": {"post": {"operationId": "getItem"}}},
    }
    with pytest.raises(AdapterError, match="templated"):
        HttpAgent.from_openapi(spec, allow_private=True)


def test_from_openapi_malformed_servers_entry():
    spec = {"servers": ["https://x"], "paths": {"/a": {"post": {}}}}
    with pytest.raises(AdapterError, match="server URL"):
        HttpAgent.from_openapi(spec, allow_private=True)
