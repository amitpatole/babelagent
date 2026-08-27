"""Shared helpers for adapters: signature binding and I/O schema inference."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def bind_payload(payload: Any, sig: inspect.Signature | None) -> tuple[tuple, dict]:
    """Decide how to pass a part's *payload* into a callable.

    Deterministic rules:

    * 0 or 1 parameter  → ``fn(payload)``
    * dict payload whose keys the callable accepts → ``fn(**payload)``
    * list/tuple payload with a multi-arg callable  → ``fn(*payload)``
    * otherwise                                     → ``fn(payload)``
    """
    if sig is None:
        return (payload,), {}

    params = [
        p
        for p in sig.parameters.values()
        if p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
    ]
    has_var_kw = any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )

    if len(params) <= 1:
        return (payload,), {}

    if isinstance(payload, dict):
        accepted = {p.name for p in params}
        if has_var_kw or set(payload) <= accepted:
            return (), dict(payload)

    if isinstance(payload, (list, tuple)):
        return tuple(payload), {}

    return (payload,), {}


def infer_io_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Best-effort JSON-schema hints for a callable's inputs and output.

    Never raises — returns ``{}`` for anything it can't introspect. Used purely
    for ``byoa inspect`` / documentation, never for execution.
    """
    schema: dict[str, Any] = {"inputs": {}, "output": None}
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return {}

    try:
        from pydantic import TypeAdapter

        for pname, p in sig.parameters.items():
            if p.annotation is inspect.Parameter.empty:
                continue
            try:
                schema["inputs"][pname] = TypeAdapter(p.annotation).json_schema()
            except Exception:  # noqa: BLE001 — schema hints are best-effort only
                schema["inputs"][pname] = {"type": "unknown"}
        if sig.return_annotation is not inspect.Signature.empty:
            try:
                schema["output"] = TypeAdapter(sig.return_annotation).json_schema()
            except Exception:  # noqa: BLE001
                schema["output"] = {"type": "unknown"}
    except Exception:  # noqa: BLE001 — pydantic missing or annotation unresolvable
        return schema
    return schema
