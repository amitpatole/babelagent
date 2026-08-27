"""Adapt a remote Agent2Agent (A2A) agent as a node in the graph.

A2A is a wire protocol for (usually remote) agents to talk over JSON-RPC/HTTP.
Babelagent treats such an agent as *just another Agent*: point at its base URL
and it becomes a node that other agents can hand messages to. Implemented on
httpx (a base dependency), so no extra is required; the same SSRF guard as the
HTTP adapter applies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from ..core.agent import Context
from ..core.errors import AdapterError
from ..core.message import Message
from .http_agent import MAX_RESPONSE_BYTES, _guarded_client, _read_capped, guard_url

# Agent Card discovery paths, newest first (the A2A spec renamed the file).
_CARD_PATHS = ("/.well-known/agent-card.json", "/.well-known/agent.json")


@dataclass
class A2ARef:
    """A reference to a remote A2A agent by base URL (recognized by ``adapt()``)."""

    url: str
    name: str | None = None
    allow_private: bool = False


class A2AAgent:
    """Calls a remote A2A agent via the ``message/send`` JSON-RPC method."""

    def __init__(
        self,
        url: str,
        *,
        name: str | None = None,
        timeout: float = 60.0,
        allow_private: bool = False,
    ) -> None:
        self.url = guard_url(url, allow_private=allow_private)
        self.name = name or f"a2a:{httpx.URL(url).host}"
        self.timeout = timeout
        self.allow_private = allow_private

    async def run(self, message: Message, ctx: Context) -> Message:
        text = message.payload if isinstance(message.payload, str) else str(message.payload)
        request = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": text}],
                    "messageId": uuid.uuid4().hex,
                }
            },
        }
        guard_url(self.url, allow_private=self.allow_private)  # re-validate (TOCTOU)
        async with _guarded_client(allow_private=self.allow_private, timeout=self.timeout) as client:
            async with client.stream("POST", self.url, json=request) as resp:
                resp.raise_for_status()
                raw = await _read_capped(resp)
        try:
            import json

            body = json.loads(raw)
        except ValueError as exc:
            raise AdapterError("A2A response was not valid JSON") from exc
        if not isinstance(body, dict):
            raise AdapterError("A2A response was not a JSON object")
        if body.get("error"):
            raise AdapterError(f"A2A agent returned error: {body['error']}")
        out = _extract_text(body.get("result", body))
        return message.with_payload(out, node=self.name)

    @classmethod
    async def from_card(
        cls, base_url: str, *, allow_private: bool = False, **kwargs: Any
    ) -> A2AAgent:
        """Discover an agent's card to resolve its service URL and name."""
        card = await _fetch_agent_card(base_url, allow_private=allow_private)
        service_url = card.get("url") or base_url
        name = kwargs.pop("name", None) or card.get("name")
        return cls(service_url, name=name, allow_private=allow_private, **kwargs)


def _extract_text(result: Any) -> Any:
    """Pull text out of an A2A Message or Task result, tolerant of shape drift."""
    if not isinstance(result, dict):
        return result
    # A direct Message: {"parts": [...]}
    if "parts" in result:
        return _join_parts(result["parts"])
    # A Task: prefer artifacts, then the status message.
    texts: list[str] = []
    for artifact in result.get("artifacts") or []:
        if isinstance(artifact, dict):
            texts.append(_join_parts(artifact.get("parts") or []))
    status = result.get("status") or {}
    status_msg = status.get("message") if isinstance(status, dict) else None
    if isinstance(status_msg, dict):
        texts.append(_join_parts(status_msg.get("parts") or []))
    joined = "\n".join(t for t in texts if t)
    return joined or result


def _join_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    out: list[str] = []
    for part in parts:
        if isinstance(part, dict) and "text" in part:
            out.append(str(part["text"]))
    return "".join(out)


async def _fetch_agent_card(base_url: str, *, allow_private: bool) -> dict[str, Any]:
    base = base_url.rstrip("/")
    async with _guarded_client(allow_private=allow_private, timeout=15.0) as client:
        for path in _CARD_PATHS:
            url = guard_url(base + path, allow_private=allow_private)
            try:
                async with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        continue
                    raw = await _read_capped(resp, cap=MAX_RESPONSE_BYTES)
            except httpx.HTTPError:
                continue
            try:
                import json

                return json.loads(raw)
            except ValueError:
                continue
    raise AdapterError(f"no A2A agent card found under {base_url!r}")
