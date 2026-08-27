"""The MCP server interface: a graph exposed as MCP tools."""

from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from babelagent.io._demo_assets import build_fixed  # noqa: E402
from babelagent.io.mcp import build_server  # noqa: E402


def test_build_server_constructs():
    server = build_server(build_fixed(), name="test-graph")
    assert hasattr(server, "run")


async def test_server_lists_graph_tools():
    server = build_server(build_fixed())
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert {"run_graph", "graph_topology"} <= names
