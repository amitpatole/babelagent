"""Serve a Babelagent graph over HTTP (behind the ``serve`` extra).

Hardened from birth (the security cadence tightens this further):

* Bearer-token auth, compared in constant time. Zero-config on loopback;
  REQUIRED (fail closed) on any non-loopback bind.
* Request-body size cap enforced before the body is buffered.
* A concurrency semaphore bounds in-flight runs (DoS bound).
* Every run is deadline-bounded.
* Errors are sanitized; internal details never leak to the caller.
"""

# NOTE: no `from __future__ import annotations` here. FastAPI resolves endpoint
# type hints via get_type_hints against module globals; the fastapi types are
# imported lazily inside build_app (to keep them behind the `serve` extra), so
# the annotations must be real objects at definition time, not strings.

import hmac
import ipaddress
import math
from typing import Any

from ..config import Settings, load_settings
from ..core.errors import MissingDependencyError
from ..core.graph import CompiledGraph, Graph


def _compiled(graph: Any) -> CompiledGraph:
    if isinstance(graph, CompiledGraph):
        return graph
    if isinstance(graph, Graph):
        return graph.compile()
    raise TypeError("build_app needs a Graph or CompiledGraph")


def _is_loopback(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


_MAX_SAFE_DEPTH = 64


def _safe(value: Any, _depth: int = 0) -> Any:
    """Keep JSON-friendly values as-is; stringify anything else.

    Depth-bounded so an adversarially deep (or cyclic) agent output cannot
    exhaust the stack when it is serialized for the response.
    """
    if _depth >= _MAX_SAFE_DEPTH:
        return "...(truncated: max depth)"
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v, _depth + 1) for v in value]
    return str(value)


def _public_trace(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Redact internal exception text from a trace before returning it to a caller.

    Gate reasons (author-written grade text) are kept; raw exception messages
    (which may carry internal paths, upstream URLs, or SDK error detail) are
    replaced with a generic marker. See scheduler's ``errored`` flag.
    """
    out = []
    for rec in trace:
        rec = dict(rec)
        if rec.pop("errored", False):
            rec["reason"] = "error"
        out.append(rec)
    return out


def build_app(graph: Any, *, settings: Settings | None = None):  # type: ignore[no-untyped-def]
    """Build a FastAPI app that serves *graph* over HTTP."""
    try:
        import anyio
        from fastapi import Depends, FastAPI, Header, HTTPException, Request
    except ImportError as exc:  # pragma: no cover - exercised via missing extra
        raise MissingDependencyError("REST service", "serve") from exc

    settings = settings or load_settings()
    compiled = _compiled(graph)
    token = settings.api_token
    limiter = anyio.Semaphore(max(1, settings.max_concurrency))

    app = FastAPI(title="Babelagent", docs_url=None, redoc_url=None)

    async def require_auth(authorization: str | None = Header(default=None)) -> None:
        if not token:
            return  # zero-config on loopback; serve() forbids tokenless non-loopback
        expected = f"Bearer {token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="unauthorized")

    async def _read_capped(request: Request) -> bytes:
        cap = settings.max_body_bytes
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > cap:
                    raise HTTPException(status_code=413, detail="request too large")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="bad content-length") from exc
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > cap:
                raise HTTPException(status_code=413, detail="request too large")
        return bytes(body)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "service": "babelagent"}

    @app.get("/graph", dependencies=[Depends(require_auth)])
    async def graph_spec() -> dict[str, Any]:
        return compiled.spec()

    @app.post("/run", dependencies=[Depends(require_auth)])
    async def run(request: Request) -> dict[str, Any]:
        import json

        raw = await _read_capped(request)
        try:
            body = json.loads(raw or b"{}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid JSON") from exc
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be a JSON object")
        payload = body.get("payload")
        # A caller may lower the deadline but never raise it above the server
        # ceiling; reject non-finite / non-positive values (inf/nan/negative
        # would defeat the per-run timeout entirely).
        try:
            deadline = float(body.get("deadline_s", settings.request_timeout_s))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="invalid deadline_s") from None
        if not math.isfinite(deadline) or deadline <= 0:
            raise HTTPException(status_code=400, detail="deadline_s must be finite and positive")
        deadline = min(deadline, settings.request_timeout_s)

        async with limiter:
            try:
                result = await compiled.run(payload, deadline_s=deadline)
            except HTTPException:
                raise
            except Exception:  # noqa: BLE001 — never leak internals to the caller
                raise HTTPException(status_code=500, detail="internal error") from None
        return {
            "ok": result.ok,
            "verdict": result.verdict,
            "output": _safe(result.output),
            "trace": _public_trace(result.trace),
        }

    return app


def serve(
    graph: Any,
    *,
    settings: Settings | None = None,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Run the REST service. Fails closed if bound non-loopback without a token."""
    try:
        import uvicorn
    except ImportError as exc:
        raise MissingDependencyError("REST service", "serve") from exc

    settings = settings or load_settings()
    host = host or settings.host
    port = port or settings.port
    if not _is_loopback(host) and not settings.api_token:
        raise RuntimeError(
            f"refusing to bind {host!r} without an API token; set BABELAGENT_API_TOKEN "
            f"(or bind 127.0.0.1 for zero-config local use)"
        )
    uvicorn.run(build_app(graph, settings=settings), host=host, port=port)


def main() -> None:  # pragma: no cover - convenience entry for the demo graph
    from ._demo_assets import build_fixed

    serve(build_fixed())
