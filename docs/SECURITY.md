# Security posture

Babelagent runs code and calls services you bring, and its REST/MCP interfaces accept untrusted input,
so security is treated as part of "done." The current surface has been through a full audit and four
adversarial red-team rounds (the last found nothing new). This page states what is hardened, how to
deploy safely, and the residual risks no audit removes.

## What is hardened

**Network input (REST service, `babelagent[serve]`).**
- Bearer-token auth compared in constant time (`hmac.compare_digest`). Zero-config on loopback;
  **fail-closed** on any non-loopback bind without a token (`serve()` refuses to start).
- Anti-DNS-rebind **Host-header pinning** on loopback binds (a browser cannot rebind `attacker.com`
  to `127.0.0.1` and drive `/run`). Fails closed on a missing Host.
- Request-body size cap enforced **before** buffering; a body-phase idle/slowloris timeout; a
  concurrency semaphore; `limit_concurrency` + `timeout_keep_alive` on uvicorn.
- Caller-supplied `deadline_s` is validated (finite, positive) and **clamped** to the server ceiling
  (it can only lower the run budget, never raise it), backed by a hard wall-clock guillotine on the run.
- Errors are sanitized: internal exception messages are redacted from the returned trace.

**Outbound requests (HTTP / OpenAPI / A2A adapters).**
- SSRF allowlist: only public global-unicast targets. Blocks loopback/private/link-local/reserved/
  multicast/unspecified, and normalizes IPv4-mapped, IPv4-compatible, NAT64, 6to4, and Teredo IPv6
  so an internal IPv4 cannot be smuggled through an IPv6 literal.
- Redirects are never followed; the guard is re-run at connect time; upstream responses are streamed
  with a size cap so a hostile agent cannot exhaust memory.
- Secrets: API keys and tokens come only from the environment; never hard-coded, never serialized into
  a topology or returned in a response.

**Execution / resources.**
- No `eval`/`exec`/`pickle`/`shell=True` on untrusted input. The OpenAPI path only reads a schema.
- The scheduler bounds concurrency; response serialization is bounded by depth **and** a total-node
  budget (so a wide or shared-reference structure cannot fan out to exponential work).
- Untrusted upstream output cannot inject keyword/positional "flag" arguments into a callable node
  (payload spreads into a callable only when it exactly matches the callable's required parameters).
- Entry-point adapter discovery can be disabled with `BABELAGENT_NO_PLUGINS=1`.

## Deploying safely

- **Front a routable deployment with a reverse proxy** (nginx `client_header_timeout`, an ALB idle
  timeout, etc.). uvicorn has no header-receive timeout, so a slow-headers Slowloris is only fully
  mitigated by a fronting proxy. Always set a token (`BABELAGENT_API_TOKEN`) for non-loopback binds.
- **Front untrusted outbound targets with an egress allowlist / proxy.** The SSRF guard blocks internal
  targets, but a host under attacker DNS control can still rebind between validation and connect; an
  egress allowlist closes that residual.
- **Do not run untrusted, blocking, or CPU-bound *sync* callables on a shared server.** A blocked
  worker thread cannot be force-killed (a Python limitation); use an async agent or an out-of-process
  agent for such work.

## Documented residuals (not eliminated by any audit)

- A blocked/CPU-bound **sync** callable's worker thread cannot be interrupted; the run still reports the
  timeout, but the thread lingers.
- **DNS-rebinding** of an outbound target is not fully closed without an egress allowlist/proxy.
- **Header-phase Slowloris** requires a fronting reverse proxy.
- **Brought agents and entry-point plugins run code** by design; trust your dependency set and the
  agents you plug in. LLM provider SDKs dial trusted first-party endpoints.
- The usual unknowns: third-party dependencies and the kernel/OS.

## Reporting

This project is in local development. Once public, report vulnerabilities privately to the maintainer.
