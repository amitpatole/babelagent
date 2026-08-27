# Changelog

All notable changes to BYOA are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

### Added — core assembly line (Phase 1)
- `Factory` builder with **linear sugar** (`.station(...).station(...)`) that compiles to a
  **DAG core** supporting `after=` dependencies, fan-out, parallel branches, and fan-in `join`.
- Barrier policies for fan-in: `all`, `k_of_n` (with `k`), and `optional`.
- Async `scheduler` with bounded concurrency, per-station + per-run timeouts, reactive readiness,
  and failure propagation (unsatisfiable barriers skip downstream nodes).
- Native, dependency-free quality types: `Verdict` (pass/warn/fail), `Result`, `Check`, and
  `GateMode` (off/warn/strict) for optional per-station gating.
- `Part` / `Product` envelopes; `Blueprint` topology validation (cycle + dangling-dep detection).

### Added — adapters + `adapt()` (Phase 2)
- **`adapt()`** on-the-fly adapter creator: normalizes callables, HTTP/OpenAPI endpoints, MCP tools,
  framework agents (LangChain / CrewAI / AutoGen), and LLM providers into the uniform `Agent` interface.
- `CallableAgent` (sync callables run off the event loop; smart payload→signature binding).
- `HttpAgent` (+ `from_openapi`) with a basic SSRF guard (Phase 4 hardens it further).
- `LLM` provider adapter (Anthropic / OpenAI / Ollama), lazy-imported behind extras; defaults to
  the latest Claude model.
- Extensible registry: `register_adapter(...)` and the `byoa.adapters` entry-point group.

### Added — interfaces (Phase 3)
- `byoa` CLI (Typer): `demo`, `doctor`, `inspect`, `version`.
- Key-free `byoa demo`: a broken station gated to FAIL, then a fixed one producing a PASS product.

[Unreleased]: https://example.invalid/byoa/compare
