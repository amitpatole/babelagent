"""Expose a Babelagent graph as an MCP server (behind the ``mcp`` extra).

The mirror image of the MCP *adapter*: where ``adapters/mcp_agent.py`` lets a
graph consume an MCP tool, this lets any MCP client (Claude, Cursor, another
agent) run a whole graph as a tool.
"""

from __future__ import annotations

from typing import Any

from ..core.errors import MissingDependencyError
from .rest import _compiled, _safe


def _load_server_cls():  # type: ignore[no-untyped-def]
    """Return the MCP server class across SDK versions (2.x MCPServer / 1.x FastMCP)."""
    try:
        from mcp.server.mcpserver import MCPServer

        return MCPServer
    except ImportError:
        pass
    try:
        from mcp.server.fastmcp import FastMCP

        return FastMCP
    except ImportError as exc:
        raise MissingDependencyError("MCP server", "mcp") from exc


def build_server(graph: Any, *, name: str = "babelagent"):  # type: ignore[no-untyped-def]
    """Build an MCP server exposing *graph* as callable tools."""
    server_cls = _load_server_cls()
    compiled = _compiled(graph)
    server = server_cls(name)

    @server.tool()
    async def run_graph(payload: str) -> dict[str, Any]:
        """Run the graph on a text payload and return its result."""
        result = await compiled.run(payload)
        return {
            "ok": result.ok,
            "verdict": result.verdict,
            "output": _safe(result.output),
        }

    @server.tool()
    async def graph_topology() -> dict[str, Any]:
        """Return the graph's topology (nodes, edges, barriers)."""
        return compiled.spec()

    return server


def main() -> None:  # pragma: no cover - convenience entry for the demo graph
    from ._demo_assets import build_fixed

    build_server(build_fixed()).run()
