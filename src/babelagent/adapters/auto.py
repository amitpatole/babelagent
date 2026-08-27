"""``adapt()`` — the on-the-fly adapter creator.

Hand it anything a user brought (a callable, an HTTP/OpenAPI URL, an MCP ref, a
framework agent, or an already-conforming Agent) and it returns a uniform
:class:`~babelagent.core.agent.Agent`. Extensible: third parties register their
own matchers via :func:`register_adapter` or the ``babelagent.adapters``
entry-point group.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..core.agent import Agent, is_agent
from ..core.errors import AdapterError

# A matcher decides whether it can handle *obj*; a builder turns it into an Agent.
Matcher = Callable[[Any], bool]
Builder = Callable[..., Agent]


@dataclass
class _Registration:
    name: str
    matches: Matcher
    build: Builder


_REGISTRY: list[_Registration] = []
_ENTRYPOINTS_LOADED = False


def register_adapter(name: str, matches: Matcher, build: Builder) -> None:
    """Register a custom adapter. Later registrations take precedence."""
    _REGISTRY.insert(0, _Registration(name=name, matches=matches, build=build))


def _load_entrypoint_adapters() -> None:
    global _ENTRYPOINTS_LOADED
    if _ENTRYPOINTS_LOADED:
        return
    _ENTRYPOINTS_LOADED = True
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="babelagent.adapters")
    except Exception:  # noqa: BLE001 — discovery is best-effort
        return
    for ep in eps:
        try:
            obj = ep.load()
        except Exception:  # noqa: BLE001 — a broken plugin must not break adapt()
            continue
        if hasattr(obj, "matches") and hasattr(obj, "build"):
            register_adapter(ep.name, obj.matches, obj.build)


def _string_looks_http(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _string_looks_openapi(value: str) -> bool:
    low = value.lower()
    return low.endswith(".json") or "openapi" in low or "swagger" in low


def adapt(obj: Any, *, name: str | None = None, **hints: Any) -> Agent:
    """Return an :class:`Agent` for *obj*, inferring the right adapter.

    Resolution order: already-an-Agent → custom/entry-point registrations →
    MCP ref → framework agent → HTTP/OpenAPI → plain callable.
    """
    _load_entrypoint_adapters()

    if is_agent(obj):
        return obj  # type: ignore[return-value]

    # Custom + entry-point adapters get first crack (most specific wins).
    for reg in _REGISTRY:
        try:
            if reg.matches(obj):
                return reg.build(obj, name=name, **hints)
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(f"adapter {reg.name!r} failed on object: {exc}") from exc

    # MCP reference.
    from .mcp_agent import McpAgent, McpRef

    if isinstance(obj, McpRef):
        return McpAgent(obj)

    # Framework agents (detected without importing the frameworks).
    from . import frameworks as fw

    if fw.looks_like_langchain(obj):
        return fw.LangChainAgent(obj, name=name)
    if fw.looks_like_crewai(obj):
        return fw.CrewAgent(obj, name=name)
    if fw.looks_like_autogen(obj):
        return fw.AutoGenAgent(obj, name=name)

    # HTTP / OpenAPI endpoints.
    from .http_agent import HttpAgent

    if isinstance(obj, str) and _string_looks_http(obj):
        if _string_looks_openapi(obj):
            return HttpAgent.from_openapi(obj, name=name, **hints)
        return HttpAgent(obj, name=name, **hints)
    if isinstance(obj, dict) and ("openapi" in obj or "swagger" in obj):
        return HttpAgent.from_openapi(obj, name=name, **hints)

    # Plain callable — the universal fallback.
    if callable(obj):
        from .callable_agent import CallableAgent

        return CallableAgent(obj, name=name)

    raise AdapterError(
        f"don't know how to adapt {type(obj).__name__}; bring an Agent, a callable, "
        f"an http(s) URL, an McpRef, a framework agent, or register a custom adapter "
        f"with babelagent.register_adapter(...)."
    )
