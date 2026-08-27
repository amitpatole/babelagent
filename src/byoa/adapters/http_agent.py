"""Adapt an HTTP / OpenAPI endpoint as a station worker.

The OpenAPI path only *reads* the schema to learn how to call the endpoint — it
never fetches or executes remote code. A basic SSRF guard is applied here;
Phase 4 (security cadence) hardens it further (DNS-rebind, redirect caps).
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

from ..core.agent import Context
from ..core.errors import AdapterError
from ..core.part import Part

_ALLOWED_SCHEMES = {"http", "https"}


def guard_url(url: str, *, allow_private: bool = False) -> str:
    """Validate a URL's scheme and (optionally) block internal targets."""
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
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise AdapterError(
                f"refusing to call internal address {ip} for {parsed.hostname!r} "
                f"(pass allow_private=True to override)"
            )
    return url


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

    async def run(self, part: Part, ctx: Context) -> Part:
        payload = part.payload
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if self.method == "GET":
                resp = await client.get(
                    self.url,
                    params=payload if isinstance(payload, dict) else None,
                    headers=self.headers,
                )
            else:
                resp = await client.request(
                    self.method, self.url, json=payload, headers=self.headers
                )
        resp.raise_for_status()
        try:
            out: Any = resp.json()
        except ValueError:
            out = resp.text
        return part.with_payload(out, station=self.name, http_status=resp.status_code)

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
            resp = httpx.get(url, timeout=30.0)
            resp.raise_for_status()
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
