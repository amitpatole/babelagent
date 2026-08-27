# Changelog

All notable changes to Babelbridge are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

### Renamed
- Project renamed from the working title **BYOA** to **Babelbridge** (import + distribution name
  `babelbridge`). The framing is now a neutral communication layer that lets heterogeneous agents talk
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
- Extensible registry: `register_adapter(...)` and the `babelbridge.adapters` entry-point group.

### Added — interfaces
- `babelbridge` CLI (Typer): `demo`, `doctor`, `inspect`, `version`.
- Key-free `babelbridge demo`: a broken agent gated to FAIL, then a fixed one producing a PASS result.

[Unreleased]: https://example.invalid/babelbridge/compare
