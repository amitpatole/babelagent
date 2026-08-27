"""Babelagent adapters: normalize anything a user brings into a uniform Agent."""

from __future__ import annotations

from .a2a_agent import A2AAgent, A2ARef
from .auto import adapt, register_adapter
from .callable_agent import CallableAgent
from .http_agent import HttpAgent
from .llm_agent import LLM
from .mcp_agent import McpAgent, McpRef

__all__ = [
    "adapt",
    "register_adapter",
    "A2AAgent",
    "A2ARef",
    "CallableAgent",
    "HttpAgent",
    "LLM",
    "McpAgent",
    "McpRef",
]
