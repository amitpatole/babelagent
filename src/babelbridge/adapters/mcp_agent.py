"""Adapt a Model Context Protocol (MCP) tool as a graph agent.

Requires the ``[mcp]`` extra. The MCP client is created lazily per run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.agent import Context
from ..core.errors import MissingDependencyError
from ..core.message import Message


@dataclass
class McpRef:
    """A reference to an MCP tool: a stdio server command + a tool name."""

    command: list[str]
    tool: str
    name: str | None = None


class McpAgent:
    """Calls a single MCP tool, passing the part payload as its arguments."""

    def __init__(self, ref: McpRef) -> None:
        self.ref = ref
        self.name = ref.name or f"mcp:{ref.tool}"

    async def run(self, message: Message, ctx: Context) -> Message:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise MissingDependencyError("MCP tool", "mcp") from exc

        args = message.payload if isinstance(message.payload, dict) else {"input": message.payload}
        params = StdioServerParameters(command=self.ref.command[0], args=self.ref.command[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self.ref.tool, args)
        out = _flatten_mcp_result(result)
        return message.with_payload(out, node=self.name)


def _flatten_mcp_result(result: Any) -> Any:
    content = getattr(result, "content", None)
    if not content:
        return result
    texts = [getattr(block, "text", None) for block in content]
    texts = [t for t in texts if t is not None]
    if len(texts) == 1:
        return texts[0]
    return texts or content
