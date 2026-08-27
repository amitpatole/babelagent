"""Shared helpers for adapters: signature binding and I/O schema inference."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def bind_payload(payload: Any, sig: inspect.Signature | None) -> tuple[tuple, dict]:
    """Decide how to pass a message's *payload* into a callable.

    Deterministic rules:

    * 0 or 1 parameter  → ``fn(payload)``
    * dict payload whose keys EXACTLY match the callable's *required* params
      → ``fn(**payload)``
    * list/tuple payload with a multi-arg callable  → ``fn(*payload)``
    * otherwise                                     → ``fn(payload)``

    Security note: a payload can come from an untrusted upstream node (e.g. a
    remote A2A/HTTP agent's output). To prevent that output from injecting
    keyword arguments into optional / keyword-only "flag" parameters
    (``admin=True``, ``dry_run=False``, ...) or wholesale into ``**kwargs``, the
    dict-spread fires ONLY when the payload keys are exactly the callable's
    required parameters. Anything else falls back to a single positional arg.
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

    if len(params) <= 1:
        return (payload,), {}

    if isinstance(payload, dict):
        required = {
            p.name
            for p in params
            if p.default is inspect.Parameter.empty
            and p.kind is not inspect.Parameter.POSITIONAL_ONLY
        }
        if required and set(payload) == required:
            return (), dict(payload)

    if isinstance(payload, (list, tuple)):
        # Same discipline for positional splat: only when the item count exactly
        # fills the required positional params (and there is no ``*args`` to soak
        # up extras), so an untrusted list cannot positionally set a flag arg.
        req_positional = [
            p
            for p in params
            if p.default is inspect.Parameter.empty
            and p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        has_var_positional = any(
            p.kind is inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()
        )
        if not has_var_positional and len(payload) == len(req_positional):
            return tuple(payload), {}

    return (payload,), {}


def infer_io_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Best-effort JSON-schema hints for a callable's inputs and output.

    Never raises; returns ``{}`` for anything it cannot introspect. Used purely
    for ``babelagent inspect`` / documentation, never for execution.
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
