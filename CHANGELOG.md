# Changelog

All notable changes to Babelagent are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

### Fixed (code-review follow-ups)
- **Join input shape is now stable (behavioural contract).** A node with one declared upstream always
  receives its message unwrapped; a node with **two or more** declared upstreams always receives a dict
  keyed by the surviving upstream names — even under `k_of_n` when only one survived. Previously the
  type flipped between a bare value and a dict depending on which sibling flaked. `Result.output`
  follows the same rule (by declared-terminal count). Pinned by tests both ways.
- **Cancellation no longer orphans tasks.** `execute()` now cancels and awaits in-flight node tasks in
  a `finally`, so a cancelled run or a disconnected REST client delivers `CancelledError` to
  cooperative agents instead of leaking them.
- Corrected the scheduler's concurrency comment (the semaphore bounds concurrent *execution*, not task
  creation) and documented that the run guillotine is opt-in for direct library calls (always on for
  REST). Documented that entry-point adapter plugins run code and take dispatch priority
  (`BABELAGENT_NO_PLUGINS=1` to disable).

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

[Unreleased]: https://example.invalid/babelagent/compare
