# Changelog

All notable changes to Babelagent are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [0.1.2] — 2026-08-27

### Changed
- **`.join()` always hands its agent a dict** keyed by the (surviving) upstream node names, even for a
  single upstream, since a join is an explicit fan-in. A plain `.node()` keeps the prior rule (one
  upstream unwrapped, two or more keyed). This makes a join agent's input shape fully stable.

## [0.1.1] — 2026-08-27

### Fixed — behavioural contracts (external code review + a 4-way adversarial repo review)
- **Join / result input shape is stable.** One declared upstream → unwrapped; two or more → a dict
  keyed by node name. The type never flips based on which branch survived. Pinned both ways.
- **`verdict` no longer hides a tolerated crash.** A run where a non-terminal branch raised but a
  `k_of_n`/`optional` barrier absorbed it now reports `verdict="warn"` (with `ok=True`), never a clean
  `pass`. The crashed node is in `result.trace`.
- **`optional` barrier skips when no upstream survives** (instead of running the node with `{}`/`None`).
- **Cancellation no longer orphans tasks** — in-flight nodes are cancelled (and briefly awaited) when a
  run is cancelled or a REST client disconnects; the cleanup is time-bounded so a cancellation-
  swallowing agent can't defeat the guillotine.
- **Deterministic trace order** for siblings completing in the same event-loop wake; **uniform trace
  record schema** (skipped/timeout rows carry the same keys) so REST/MCP clients never `KeyError`.
- **Duplicate dependency and empty graph are rejected** at compile with a clear `TopologyError`.
- **`is_agent` is strict** (an async `run(message, ctx)`), so a wrong-shaped object is adapted or
  rejected up front rather than failing cryptically mid-run.
- **`bind_payload`** falls back to a single positional arg for callables with required positional-only
  params (no broken `**kwargs` spread).
- **A sync callable that returns a coroutine is awaited** (its result becomes the payload).
- **`HttpAgent.from_openapi`**: falls back to a GET when a spec has no write operation, rejects
  templated paths (`/items/{id}`) with a clear error, and guards a malformed `servers` entry.
- **A2A**: handles a list JSON-RPC result and de-dups an answer echoed in both an artifact and the
  status message.
- **`Settings`** rejects nonsensical values (non-positive timeout/body/concurrency, out-of-range port).
- `LLM` is now importable from the top level; the unwired `inspect <file>` argument was removed.
- Corrected the scheduler concurrency comment; documented the opt-in guillotine, the plugin dispatch
  priority (`BABELAGENT_NO_PLUGINS=1`), the join/tolerated-branch contract, and the `adapt()` A2A step.
- +30 tests (107 total).

## [0.1.0] — 2026-08-27

### Security
- Completed the full security cadence over the REST / MCP / A2A / HTTP surface: a 3-surface audit and
  **four adversarial red-team rounds** (final round found nothing new). Fixed and regression-pinned:
  attacker-controlled `deadline_s` (DoS), SSRF (allowlist + NAT64/6to4/Teredo normalization, no
  redirects, response caps, connect-time re-guard), keyword/positional argument injection from
  untrusted upstream output, `_safe` depth+width DoS, trace exception-message leakage, REST DNS-rebind
  (Host pinning), slowloris (body + connection limits), and a hard wall-clock guillotine defeating
  cancellation-swallowing agents. See `docs/SECURITY.md` for the posture, deployment guidance, and the
  documented residuals. 22 security regression tests in `tests/security/`.

### Renamed
- Project renamed from the working title **BYOA** to **Babelagent** (import + distribution name
  `babelagent`). The framing is now a neutral communication layer that lets heterogeneous agents talk
  to each other (agent-to-agent), not a factory/assembly line.
- API vocabulary re-themed: `Factory` → `Graph`, `Line` → `CompiledGraph`, `Blueprint` → `Topology`,
  `Station` → `Node` (merged with the old graph-node wrapper), `Part` → `Message`, `Product` →
  `Result`, check outcome `Result` → `Grade`; `.station()` → `.node()`.

### Added — core graph engine
- `Graph` builder with **linear chaining** (`.node(...).node(...)`) that compiles to a **DAG core**
  supporting `after=` dependencies, fan-out, parallel branches, and fan-in `join`.
- Barrier policies for fan-in: `all`, `k_of_n` (with `k`), and `optional`.
- Async scheduler with bounded concurrency, per-node + per-run timeouts, reactive readiness, and
  failure propagation (unsatisfiable barriers skip downstream nodes).
- Native, dependency-free quality types: `Verdict` (pass/warn/fail), `Grade`, `Check`, and `GateMode`
  (off/warn/strict) for optional per-node gating.
- `Message` / `Result` envelopes; `Topology` validation (cycle + dangling-dep detection).

### Added — adapters + `adapt()`
- **`adapt()`** on-the-fly adapter creator: normalizes callables, HTTP/OpenAPI endpoints, MCP tools,
  framework agents (LangChain / CrewAI / AutoGen), and LLM providers into the uniform `Agent` interface.
- `CallableAgent`, `HttpAgent` (+ `from_openapi`, basic SSRF guard), `LLM` provider adapter (lazy,
  behind extras, defaults to the latest Claude model).
- Extensible registry: `register_adapter(...)` and the `babelagent.adapters` entry-point group.

### Added — A2A adapter
- **`A2AAgent` / `A2ARef`**: consume a remote Agent2Agent (A2A) agent as a node via the
  `message/send` JSON-RPC method, with Agent Card discovery. Built on httpx (base wheel, no extra),
  SSRF-guarded. `adapt(A2ARef(url))` wires a remote agent into the graph. This is the "consume the
  protocols, don't compete with them" position: a remote A2A agent becomes just another `Agent`.

### Added — interfaces
- `babelagent` CLI (Typer): `demo`, `doctor`, `inspect`, `serve`, `mcp`, `version`.
- **REST service** (`babelagent.io.rest`, `serve` extra): serve a graph over HTTP. Hardened from
  birth — constant-time bearer auth, zero-config on loopback but fail-closed (refuses to bind a
  non-loopback host without a token), request-body size cap enforced before buffering, a concurrency
  semaphore, deadline-bounded runs, and sanitized errors. Endpoints: `GET /health`, `GET /graph`,
  `POST /run`.
- **MCP server** (`babelagent.io.mcp`, `mcp` extra): expose a graph as MCP tools (`run_graph`,
  `graph_topology`) so any MCP client can run a whole graph. Works across MCP SDK 2.x (`MCPServer`)
  and 1.x (`FastMCP`).
- Key-free `babelagent demo`: a broken agent gated to FAIL, then a fixed one producing a PASS result.

[0.1.2]: https://github.com/amitpatole/babelagent/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/amitpatole/babelagent/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/amitpatole/babelagent/releases/tag/v0.1.0
