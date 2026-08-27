"""Adapt an HTTP / OpenAPI endpoint as a graph agent.

The OpenAPI path only reads the schema to learn how to call the endpoint. It
never fetches or executes remote code.

SSRF posture: outbound URLs are validated with an allowlist (public
global-unicast only, IPv4-mapped IPv6 normalized), redirects are never
followed, the guard is re-run immediately before each request (TOCTOU window
shrunk), and responses are size-capped. A residual sub-millisecond DNS-rebind
race between our resolution and httpx's connect remains (documented).
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from ..core.agent import Context
from ..core.errors import AdapterError
from ..core.message import Message

_ALLOWED_SCHEMES = {"http", "https"}

# Cap on a single upstream response body (a remote/untrusted agent must not be
# able to exhaust memory by returning a multi-GB body).
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def _blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True if *ip* must not be dialed (SSRF): anything not public unicast."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:169.254.169.254 -> evaluate as the IPv4
    return (not ip.is_global) or ip.is_multicast


def guard_url(url: str, *, allow_private: bool = False) -> str:
    """Validate a URL's scheme and (unless ``allow_private``) block internal targets."""
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise AdapterError(f"unsupported URL scheme {parsed.scheme!r}; use http/https")
    if not parsed.hostname:
        raise AdapterError(f"URL has no host: {url!r}")
    if allow_private:
        return url
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise AdapterError(f"cannot resolve host {parsed.hostname!r}: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _blocked_ip(ip):
            raise AdapterError(
                f"refusing to call non-public address {ip} for {parsed.hostname!r} "
                f"(pass allow_private=True to override)"
            )
    return url


async def _read_capped(resp: httpx.Response, cap: int = MAX_RESPONSE_BYTES) -> bytes:
    """Stream a response body, aborting if it exceeds *cap* bytes."""
    body = bytearray()
    async for chunk in resp.aiter_bytes():
        body.extend(chunk)
        if len(body) > cap:
            raise AdapterError(f"upstream response exceeds size cap ({cap} bytes)")
    return bytes(body)


def _decode_body(raw: bytes) -> Any:
    """JSON-decode a response body, falling back to text."""
    import json

    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode("utf-8", "replace")


class HttpAgent:
    """POSTs a part's payload as JSON to an endpoint and returns the response."""

    def __init__(
        self,
        url: str,
        *,
        name: str | None = None,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        allow_private: bool = False,
    ) -> None:
        self.url = guard_url(url, allow_private=allow_private)
        self.name = name or urlparse(url).path.strip("/").replace("/", ".") or urlparse(url).hostname or "http"
        self.method = method.upper()
        self.headers = headers or {}
        self.timeout = timeout
        self.allow_private = allow_private

    async def run(self, message: Message, ctx: Context) -> Message:
        payload = message.payload
        # Re-validate immediately before the request (shrinks the TOCTOU window
        # between construction and use).
        guard_url(self.url, allow_private=self.allow_private)
        params = payload if (self.method == "GET" and isinstance(payload, dict)) else None
        json_body = None if self.method == "GET" else payload
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            async with client.stream(
                self.method, self.url, params=params, json=json_body, headers=self.headers
            ) as resp:
                resp.raise_for_status()
                raw = await _read_capped(resp)
                status = resp.status_code
        out: Any = _decode_body(raw)
        return message.with_payload(out, node=self.name, http_status=status)

    @classmethod
    def from_openapi(
        cls,
        spec: Any,
        *,
        operation_id: str | None = None,
        base_url: str | None = None,
        allow_private: bool = False,
        **kwargs: Any,
    ) -> HttpAgent:
        """Build an :class:`HttpAgent` from an OpenAPI document.

        *spec* may be a parsed dict or a URL/path to a JSON document. Picks the
        operation by ``operation_id`` if given, else the first write operation.
        """
        doc = _load_openapi(spec, allow_private=allow_private)
        servers = doc.get("servers") or []
        resolved_base = base_url or (servers[0].get("url") if servers else None)
        if not resolved_base:
            raise AdapterError("OpenAPI spec has no server URL; pass base_url=")

        method, path, op_id = _select_operation(doc, operation_id)
        full_url = resolved_base.rstrip("/") + "/" + path.lstrip("/")
        return cls(
            full_url,
            name=kwargs.pop("name", op_id),
            method=method,
            allow_private=allow_private,
            **kwargs,
        )


def _load_openapi(spec: Any, *, allow_private: bool) -> dict[str, Any]:
    if isinstance(spec, dict):
        return spec
    if isinstance(spec, str):
        if spec.startswith(("http://", "https://")):
            url = guard_url(spec, allow_private=allow_private)
            resp = httpx.get(url, timeout=30.0, follow_redirects=False)
            resp.raise_for_status()
            if len(resp.content) > MAX_RESPONSE_BYTES:
                raise AdapterError("OpenAPI document exceeds size cap")
            return resp.json()
        import json

        with open(spec, encoding="utf-8") as fh:
            return json.load(fh)
    raise AdapterError(f"cannot load OpenAPI spec from {type(spec).__name__}")


def _select_operation(
    doc: dict[str, Any], operation_id: str | None
) -> tuple[str, str, str]:
    paths = doc.get("paths") or {}
    write_methods = ("post", "put", "patch")
    first_write: tuple[str, str, str] | None = None
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() not in (*write_methods, "get") or not isinstance(op, dict):
                continue
            op_id = op.get("operationId") or f"{method}:{path}"
            if operation_id and op_id == operation_id:
                return method.upper(), path, op_id
            if first_write is None and method.lower() in write_methods:
                first_write = (method.upper(), path, op_id)
    if operation_id:
        raise AdapterError(f"operationId {operation_id!r} not found in OpenAPI spec")
    if first_write:
        return first_write
    raise AdapterError("OpenAPI spec has no usable POST/PUT/PATCH operation")
